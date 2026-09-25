"""
llm.py  (DAY 3 deliverable)
------------------------------
Combines the Day-1 classifier output, Day-2 severity output and Day-3 RAG
context into one prompt, sends it to a coding LLM, and parses back a
structured result: root_cause, explanation, fix, corrected_code.

Two backends are supported (pick with LLM_BACKEND env var):
  - "ollama" : a local model served by Ollama (default, e.g. codellama, qwen2.5-coder)
  - "api"    : any hosted API model reachable at LLM_API_URL, using an
               OpenAI-compatible chat-completions request shape.

NOTE ON THIS SANDBOX: calling a live Ollama server or a hosted LLM API
needs network access this sandbox does not have, so the network call
itself isn't executed here. The prompt-building and JSON-parsing logic
IS tested below with a mocked response — see the __main__ block and
tests/test_day3_pipeline.py.

Usage:
    from backend.ai.llm import CodingLLM
    llm = CodingLLM()
    result = llm.generate(
        language="python", code="...", error="...", stack_trace="",
        bug_type="Type Error", bug_confidence=0.94,
        severity="MEDIUM", rag_hits=[...],
    )
    # -> {"root_cause": "...", "explanation": "...", "fix": "...", "corrected_code": "..."}
"""

import json
import os
import re

import requests

LLM_BACKEND = os.environ.get("LLM_BACKEND", "mock")  # "mock" (no setup needed), "ollama", or "api"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")

LLM_API_URL = os.environ.get("LLM_API_URL", "")       # e.g. https://api.openai.com/v1/chat/completions
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_API_MODEL = os.environ.get("LLM_API_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = (
    "You are an expert software debugging assistant. You are given a buggy "
    "code snippet, its error message, a predicted bug type, a predicted "
    "severity, and similar known bugs retrieved from a knowledge base. "
    "Using this context, explain the root cause and produce a corrected "
    "version of the code.\n\n"
    "The code may be in Python, JavaScript, TypeScript, Java, C, C++, C#, Go, "
    "Rust or PHP. The buggy code is shown with 1-based line numbers removed - "
    "count lines yourself starting at 1.\n\n"
    "Respond with ONLY a valid JSON object, no markdown fences, no extra "
    "text, in exactly this shape:\n"
    "{\n"
    '  "root_cause": "<one or two sentences>",\n'
    '  "explanation": "<a short paragraph explaining the bug in plain language>",\n'
    '  "error_lines": [{"line": <1-based line number of the buggy line>, "reason": "<why THIS line is wrong, one sentence>"}],\n'
    '  "fix": "<one or two sentences describing the recommended fix>",\n'
    '  "corrected_code": "<the fully corrected code snippet>"\n'
    "}"
)


def build_prompt(language, code, error, stack_trace, bug_type, bug_confidence, severity, rag_hits):
    """Combines classifier + severity + RAG context into the user prompt."""
    rag_section = "No similar known bugs were found in the knowledge base."
    if rag_hits:
        lines = []
        for hit in rag_hits:
            lines.append(
                f"- [{hit['bug_type']}] error pattern: \"{hit['error_pattern']}\" "
                f"(similarity: {hit['score']})\n"
                f"  root cause: {hit['root_cause']}\n"
                f"  known fix: {hit['fix']}"
            )
        rag_section = "\n".join(lines)

    stack_section = f"\nStack trace:\n{stack_trace}" if stack_trace else ""
    numbered = "\n".join(f"{i:>3} | {row}" for i, row in enumerate(code.splitlines(), start=1))

    prompt = f"""Language: {language}

Buggy code (line numbers shown on the left are NOT part of the code):
{numbered}

Error message:
{error}{stack_section}

Predicted bug type: {bug_type} (confidence: {bug_confidence})
Predicted severity: {severity}

Similar known bugs retrieved from the knowledge base:
{rag_section}

Using all of the above, identify the root cause and provide corrected code.
Respond with the JSON object only."""
    return prompt


def _extract_json(text: str) -> dict:
    """LLMs sometimes wrap JSON in markdown fences or add stray text; strip that safely."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```(json)?", "", cleaned).strip()
    cleaned = re.sub(r"```$", "", cleaned).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fall back to grabbing the first {...} block in the text.
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


import re as _re

# ---------------------------------------------------------------------------
# Rule-based mock fix helpers
# ---------------------------------------------------------------------------

def _mock_apply_fix(code: str, rag_hit: dict) -> str:
    """
    Attempt to patch `code` based on the RAG hit's bug_type / fix text so
    the diff view shows a real change.  Covers the most common patterns in
    the default knowledge base.  Falls back to returning code unchanged when
    no rule fires (validator will then flag it as 'fix failed validation',
    which is honest).
    """
    bug = (rag_hit.get("bug_type") or "").lower()
    fix_hint = (rag_hit.get("fix") or "").lower()
    err_pat = (rag_hit.get("error_pattern") or "").lower()

    lines = code.splitlines()

    # ---- Zero-division guard (Python / JS / TS) ---------------------------
    if "zero" in bug or "division" in bug or "zerodivision" in err_pat:
        new_lines = []
        for i, ln in enumerate(lines):
            new_lines.append(ln)
            # Insert guard before the first return / division line
            if _re.search(r"/\s*\w+|÷", ln) and "if" not in ln and "#" not in ln and i + 1 < len(lines):
                # already has a guard on the previous non-empty line?
                prev = new_lines[-2].strip() if len(new_lines) >= 2 else ""
                if not prev.startswith("if"):
                    # extract denominator variable
                    m = _re.search(r"/\s*(\w+)", ln)
                    if m:
                        denom = m.group(1)
                        indent = len(ln) - len(ln.lstrip())
                        guard = " " * indent + f"if {denom} == 0:\n" + " " * indent + f"    raise ValueError('{denom} must not be zero')"
                        new_lines.insert(-1, guard)
        return "\n".join(new_lines)

    # ---- Missing semicolon (C / C++ / Java / PHP) -------------------------
    if "semicolon" in bug or "';'" in err_pat or "expected ';'" in err_pat or "semicol" in fix_hint:
        new_lines = []
        for ln in lines:
            stripped = ln.rstrip()
            # Skip blank, preprocessor, block openers/closers, and control-flow lines
            if (stripped and
                not stripped.lstrip().startswith(("#", "//", "/*", "*", "import", "package")) and
                not stripped.rstrip().endswith(("{", "}", ";", ":")) and
                not _re.match(r"\s*(if|else|for|while|switch|do|case|default)\b", stripped)):
                stripped += ";"
            new_lines.append(stripped)
        return "\n".join(new_lines)

    # ---- SQL injection / string concat (Python) ----------------------------
    if "sql" in bug or "injection" in bug or "parameterized" in fix_hint or "parameteris" in fix_hint:
        # Replace string concatenation in execute() calls with %s placeholders
        patched = _re.sub(
            r"execute\s*\(\s*(['\"].*?['\"])\s*\+\s*(\w+)\s*\)",
            lambda m: f"execute({m.group(1).rstrip(m.group(1)[-1])} WHERE id = %s', ({m.group(2)},))",
            code,
        )
        if patched != code:
            return patched

    # ---- Null / undefined property access (JS / TS) -----------------------
    if "null" in bug or "undefined" in bug or "cannot read propert" in err_pat:
        # Add optional chaining (?.) to member accesses
        patched = _re.sub(r"(\w+)\.(\w+)\.(\w+)", r"\1?.\2?.\3", code)
        if patched != code:
            return patched

    # ---- Off-by-one / index out of range -----------------------------------
    if "index" in bug and ("range" in bug or "bounds" in bug):
        # Replace arr[i] where i could be len/length with arr[i-1]
        patched = _re.sub(r"\[(\s*len\s*\(\s*\w+\s*\)\s*)\]", r"[\1 - 1]", code)
        patched = _re.sub(r"\[(\s*\w+\.length\s*)\]", r"[\1 - 1]", patched)
        if patched != code:
            return patched

    # ---- Unclosed parenthesis / bracket ------------------------------------
    if "unclosed" in bug or "paren" in bug or "bracket" in bug or "never closed" in err_pat:
        # Count and balance brackets
        opens = sum(code.count(c) for c in "([{")
        closes = sum(code.count(c) for c in ")]}")
        if opens > closes:
            closing = ")" * (code.count("(") - code.count(")"))
            closing += "]" * (code.count("[") - code.count("]"))
            closing += "}" * (code.count("{") - code.count("}"))
            return code.rstrip() + closing
        return code

    # ---- No rule fired — return original so validator shows honest status --
    return code


def _mock_detect_error_lines(code: str, rag_hit: dict) -> list:
    """
    Heuristically identify the most likely offending line(s) from the code
    based on the RAG hit's error_pattern / bug_type.
    Returns a list of {line, text, reason} dicts (same format as LLM output).
    """
    bug = (rag_hit.get("bug_type") or "").lower()
    err_pat = (rag_hit.get("error_pattern") or "").lower()
    reason = rag_hit.get("root_cause", "Potential bug location based on error pattern.")
    lines = code.splitlines()
    hits = []

    patterns = []
    if "zero" in bug or "division" in bug:
        patterns.append(_re.compile(r"/\s*\w+"))
    if "semicolon" in bug or "';'" in err_pat:
        patterns.append(_re.compile(r"\w.*[^;{}\s]$"))
    if "sql" in bug or "injection" in bug:
        patterns.append(_re.compile(r"execute\s*\(.*\+"))
    if "null" in bug or "undefined" in bug:
        patterns.append(_re.compile(r"\w+\.\w+\.\w+"))
    if "index" in bug:
        patterns.append(_re.compile(r"\[.*len\b|\.length\b"))

    for i, ln in enumerate(lines, start=1):
        stripped = ln.lstrip()
        if stripped.startswith(("//", "#", "/*", "*")):
            continue
        for pat in patterns:
            if pat.search(ln):
                hits.append({"line": i, "text": ln, "reason": reason})
                break
        if hits:
            break  # return first match only for brevity

    return hits


class CodingLLM:
    def __init__(self, backend: str = LLM_BACKEND):
        self.backend = backend

    def _call_ollama(self, prompt: str) -> str:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
            "stream": False,
            "format": "json",
        }
        resp = requests.post(OLLAMA_URL, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["response"]

    def _call_api(self, prompt: str) -> str:
        if not LLM_API_URL or not LLM_API_KEY:
            raise RuntimeError("LLM_API_URL and LLM_API_KEY must be set to use the 'api' backend.")
        headers = {
            "Authorization": f"Bearer {LLM_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": LLM_API_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        resp = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=120)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def _call_mock(self, prompt: str, rag_hits: list, code: str) -> str:
        """
        No real LLM configured — best-effort demo response built directly
        from the top RAG match.  We now attempt to apply a rule-based patch
        to the code so the Fix/diff tab shows a real change instead of
        "No code changes were suggested."

        Set LLM_BACKEND=ollama or =api for genuine LLM-generated fixes.
        """
        if rag_hits:
            top = rag_hits[0]
            corrected = _mock_apply_fix(code, top)
            error_lines = _mock_detect_error_lines(code, top)
            return json.dumps(
                {
                    "root_cause": top["root_cause"],
                    "explanation": (
                        f"This matches a known '{top['bug_type']}' pattern from the knowledge base "
                        f"(similarity {top['score']}). No live coding LLM is configured, so this is "
                        f"the closest known fix rather than a freshly generated one."
                    ),
                    "fix": top["fix"],
                    "corrected_code": corrected,
                    "error_lines": error_lines,
                }
            )
        return json.dumps(
            {
                "root_cause": "No similar known bug found and no live LLM is configured.",
                "explanation": (
                    "Set LLM_BACKEND=ollama or LLM_BACKEND=api with a real model to get a "
                    "generated fix. Alternatively, paste the exact error message for a better "
                    "RAG match from the knowledge base."
                ),
                "fix": "Configure a real LLM backend (see .env LLM_BACKEND setting) for automatic code fixes.",
                "corrected_code": code,
                "error_lines": [],
            }
        )

    def generate(
        self,
        language: str,
        code: str,
        error: str,
        bug_type: str,
        bug_confidence: float,
        severity: str,
        rag_hits: list,
        stack_trace: str = "",
    ) -> dict:
        prompt = build_prompt(
            language, code, error, stack_trace, bug_type, bug_confidence, severity, rag_hits
        )

        if self.backend == "ollama":
            raw = self._call_ollama(prompt)
        elif self.backend == "api":
            raw = self._call_api(prompt)
        elif self.backend == "mock":
            raw = self._call_mock(prompt, rag_hits, code)
        else:
            raise ValueError(f"Unknown LLM_BACKEND: {self.backend}")

        try:
            parsed = _extract_json(raw)
        except (json.JSONDecodeError, AttributeError):
            # Bounded fallback: return the raw text so the caller (Day 4
            # validator) can still show something instead of crashing.
            parsed = {
                "root_cause": "Could not parse a structured response from the LLM.",
                "explanation": raw[:500],
                "fix": "",
                "corrected_code": "",
            }

        # Guarantee every key exists so callers never KeyError.
        for key in ("root_cause", "explanation", "fix", "corrected_code"):
            parsed.setdefault(key, "")
        if not isinstance(parsed.get("error_lines"), list):
            parsed["error_lines"] = []
        return parsed


if __name__ == "__main__":
    # Demonstrates prompt-building + JSON parsing without needing a live
    # LLM server (network isn't available in this sandbox). Swap this
    # mocked response for a real self._call_ollama(...)/_call_api(...)
    # call once you run this on a machine with Ollama or an API key set up.
    from backend.ai.rag import RAGRetriever

    rag = RAGRetriever()
    code = "cursor.execute('SELECT * FROM users WHERE id = ' + user_id)"
    error = "psycopg2.errors.SyntaxError: syntax error at or near ..."
    hits = rag.retrieve(language="python", code=code, error=error, top_k=2)

    prompt = build_prompt(
        language="python",
        code=code,
        error=error,
        stack_trace="",
        bug_type="Database Error",
        bug_confidence=0.94,
        severity="CRITICAL",
        rag_hits=hits,
    )
    print("---- PROMPT SENT TO LLM ----")
    print(prompt)

    mocked_llm_response = json.dumps(
        {
            "root_cause": "Raw string concatenation is used to build the SQL query, allowing malformed/unsafe SQL.",
            "explanation": "The user_id is concatenated directly into the SQL string instead of being passed as a bound parameter, which breaks if user_id contains quotes or special characters and opens the door to SQL injection.",
            "fix": "Use a parameterized query so the database driver handles escaping safely.",
            "corrected_code": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
        }
    )
    parsed = _extract_json(mocked_llm_response)
    print("\n---- PARSED LLM OUTPUT ----")
    print(json.dumps(parsed, indent=2))
