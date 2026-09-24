"""
locator.py
----------
Answers the question "WHICH line is broken, and WHY?".

Four independent signals are combined, strongest first:

  1. AI      - the LLM's own `error_lines` [{line, reason}] (when it provides them)
  2. trace   - line numbers parsed out of the error message / stack trace
               (the innermost frame = where it fails; the others = "caller" lines)
               (Python, JS/TS, Java, C/C++, C#, Go, Rust, PHP formats)
  3. syntax  - a real parser/compiler pass over the ORIGINAL code
               (python ast, node --check, gcc/g++ -fsyntax-only, php -l ...)
  4. diff    - lines of the original that the corrected code had to change

Every returned location is clamped to the real code length, so a stack
frame pointing into a library file can never highlight a random line.
"""

import difflib
import re

# Patterns are tried in order; group 1 is the line number.
_LANG_PATTERNS = {
    "python": [r'File "[^"]+", line (\d+)', r"\bline (\d+)\b"],
    "javascript": [r"[\w./\\-]+\.(?:js|mjs|cjs|jsx):(\d+)(?::\d+)?", r"<anonymous>:(\d+):\d+", r"\bline (\d+)\b"],
    "typescript": [r"[\w./\\-]+\.tsx?\((\d+),\d+\)", r"[\w./\\-]+\.tsx?:(\d+)(?::\d+)?", r"\bline (\d+)\b"],
    "java": [r"[\w$]+\.java:(\d+)", r"\bline (\d+)\b"],
    "c": [r"[\w./\\-]+\.[ch]:(\d+):\d+", r"\bline (\d+)\b"],
    "cpp": [r"[\w./\\-]+\.(?:cpp|cc|cxx|hpp|h):(\d+):\d+", r"\bline (\d+)\b"],
    "csharp": [r"\.cs\((\d+),\d+\)", r"\.cs:line (\d+)", r"\bline (\d+)\b"],
    "go": [r"[\w./\\-]+\.go:(\d+)(?::\d+)?", r"\bline (\d+)\b"],
    "rust": [r"-->\s*[\w./\\-]+\.rs:(\d+):\d+", r"[\w./\\-]+\.rs:(\d+):\d+", r"\bline (\d+)\b"],
    "php": [r"on line (\d+)", r"\.php:(\d+)", r"\bline (\d+)\b"],
}
_GENERIC = [r"\bline[ :]+(\d+)\b", r"[\w./\\-]+\.\w{1,4}:(\d+)(?::\d+)?"]

# Frames that live in libraries/runtimes, not in the user's snippet.
_LIBRARY_HINTS = ("site-packages", "node_modules", "/usr/lib", "/usr/local/lib", "<frozen", "internal/", "node:", "java.base", "/rustc/")


def _headline(error: str) -> str:
    for line in (error or "").splitlines():
        line = line.strip()
        if line:
            return line[:200]
    return ""


def parse_trace_lines(language: str, error: str, stack_trace: str, max_line: int) -> list[int]:
    text = f"{error}\n{stack_trace}"
    patterns = _LANG_PATTERNS.get(language, []) + _GENERIC
    found: list[int] = []
    for raw_line in text.splitlines():
        if any(h in raw_line for h in _LIBRARY_HINTS):
            continue
        for pat in patterns:
            m = re.search(pat, raw_line)
            if m:
                n = int(m.group(1))
                if 1 <= n <= max_line and n not in found:
                    found.append(n)
                break
    return found


def diff_lines(original: str, corrected: str) -> list[int]:
    if not corrected or not original or corrected.strip() == original.strip():
        return []
    a, b = original.splitlines(), corrected.splitlines()
    changed = []
    for tag, i1, i2, _, _ in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag in ("replace", "delete"):
            changed += [i + 1 for i in range(i1, i2) if a[i].strip()]
    return changed


def locate_errors(language, code, error, stack_trace, root_cause, corrected_code, llm_lines, syntax_result) -> list[dict]:
    lines = code.splitlines()
    total = len(lines)
    if total == 0:
        return []

    locations: dict[int, dict] = {}

    def add(n, source, reason):
        if not isinstance(n, int) or not (1 <= n <= total):
            return
        if n in locations:  # keep the first (strongest) source, but remember corroboration
            if source not in locations[n]["sources"]:
                locations[n]["sources"].append(source)
            return
        locations[n] = {"line": n, "text": lines[n - 1].rstrip()[:300], "reason": reason, "source": source, "sources": [source]}

    # 1. LLM-provided lines
    for item in llm_lines or []:
        try:
            add(int(item.get("line")), "ai", str(item.get("reason") or root_cause)[:400])
        except (TypeError, ValueError, AttributeError):
            continue

    head = _headline(error)

    # 2. stack trace / error message.
    #    Python prints the innermost (failing) frame LAST; most other languages print it FIRST.
    trace = parse_trace_lines(language, error, stack_trace, total)
    if language == "python":
        trace.reverse()
    for rank, n in enumerate(trace):
        if rank == 0:
            add(n, "trace", f"The error is raised here: {head}" if head else "The error is raised on this line.")
        else:
            add(n, "caller", f"This line calls the code that fails (the error itself is raised on line {trace[0]}).")

    # 3. real parser / compiler pass over the original code
    if syntax_result and syntax_result.get("valid") is False and syntax_result.get("line"):
        add(int(syntax_result["line"]), "syntax", f"Syntax check failed: {syntax_result.get('message', '')}"[:300])

    # 4. what the fix had to change
    for n in diff_lines(code, corrected_code)[:8]:
        add(n, "diff", root_cause or "This line had to change to fix the bug.")

    ordered = sorted(locations.values(), key=lambda d: d["line"])
    return ordered[:6]
