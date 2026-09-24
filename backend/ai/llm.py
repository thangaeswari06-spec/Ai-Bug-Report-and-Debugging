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
        from the top RAG match, so the pipeline still returns something
        useful with zero setup. Set LLM_BACKEND=ollama or =api and
        configure a real model for genuine LLM-generated fixes.
        """
        if rag_hits:
            top = rag_hits[0]
            return json.dumps(
                {
                    "root_cause": top["root_cause"],
                    "explanation": (
                        f"This matches a known '{top['bug_type']}' pattern from the knowledge base "
                        f"(similarity {top['score']}). No live coding LLM is configured, so this is "
                        f"the closest known fix rather than a freshly generated one."
                    ),
                    "fix": top["fix"],
                    "corrected_code": code,
                    "error_lines": [],
                }
            )
        return json.dumps(
            {
                "root_cause": "No similar known bug found and no live LLM is configured.",
                "explanation": "Set LLM_BACKEND=ollama or LLM_BACKEND=api with a real model to get a generated fix.",
                "fix": "",
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
