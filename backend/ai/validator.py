"""
validator.py
------------
Validates code before it is shown to the user. Supports all 10 languages.

Strategy per language (first available tool wins, otherwise a safe fallback):

  python      ast.parse (+ optional controlled execution against expected output)
  javascript  node --check
  typescript  node --check with type-stripping (Node 22.6+), else bracket check
  c / c++     gcc / g++ -fsyntax-only
  php         php -l
  go          gofmt -e
  rust        rustc --emit=metadata   (syntax + type check)
  java        javac                    (needs a JDK)
  c#          csc / mcs                (Mono or .NET SDK)
  fallback    string/comment-aware bracket balance check

`valid` is True / False, or None when no tool for that language is installed
(so the UI can honestly say "skipped" instead of pretending it passed).
Every result may include `line` - the first offending line, which the
locator uses to highlight the exact line in the UI.
"""

import ast
import os
import re
import shutil
import subprocess
import sys
import tempfile

from backend.utils.languages import normalize_language

TOOL_TIMEOUT = 20  # compilers can be slow on a cold start


def _run(cmd, cwd=None, timeout=TOOL_TIMEOUT):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=cwd)


def _first_line_number(text: str, patterns) -> int | None:
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return int(m.group(1))
    return None


def _result(valid, stage, message, line=None):
    return {"valid": valid, "stage": stage, "message": message, "line": line}


_MISSING_TERMINATOR = re.compile(r"expected [^\n]*[;,)][^\n]* before|expected ';'|';' expected|expected ‘;’", re.I)


def _blame_previous_line(code: str, res: dict) -> dict:
    """
    C-family compilers report a missing ';' on the line AFTER the one that is
    actually wrong. Move the blame to the previous non-empty line.
    """
    line = res.get("line")
    if res.get("valid") is False and line and _MISSING_TERMINATOR.search(res.get("message", "")):
        rows = code.splitlines()
        i = line - 2
        while i >= 0 and not rows[i].strip():
            i -= 1
        if i >= 0:
            res["line"] = i + 1
    return res


# ------------------------------------------------------------------ python
def _validate_python(code, expected_output=None, test_input=None):
    try:
        ast.parse(code)
    except SyntaxError as e:
        return _result(False, "syntax", f"SyntaxError: {e.msg} (line {e.lineno})", e.lineno)

    if expected_output is None:
        return _result(True, "syntax", "Syntax OK.")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        tmp = f.name
    py_bin = sys.executable or shutil.which("python3") or "python"
    try:
        proc = subprocess.run([py_bin, tmp], input=test_input or "", capture_output=True, text=True, timeout=5)
        if proc.returncode != 0:
            return _result(False, "execution", f"Runtime error: {proc.stderr.strip()[:500]}")
        actual = proc.stdout.strip()
        if expected_output.strip() != actual:
            return _result(False, "test", f"Test failed. Expected: {expected_output.strip()!r}, got: {actual!r}")
        return _result(True, "test", "Syntax OK and test passed.")
    except subprocess.TimeoutExpired:
        return _result(False, "execution", "Execution timed out (possible infinite loop).")
    finally:
        os.unlink(tmp)


# ------------------------------------------------- tool-based syntax checks
def _with_tempfile(code, suffix, fn):
    d = tempfile.mkdtemp(prefix="bf_")
    try:
        path = os.path.join(d, "main" + suffix)
        with open(path, "w", encoding="utf-8") as f:
            f.write(code)
        return fn(path, d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def _check_with(code, suffix, cmd_builder, label, line_patterns, required_tool):
    if not shutil.which(required_tool):
        return None

    def go(path, d):
        try:
            proc = _run(cmd_builder(path, d), cwd=d)
        except subprocess.TimeoutExpired:
            return _result(False, "syntax", f"{label} check timed out.")
        out = (proc.stderr or proc.stdout).strip()
        if proc.returncode == 0:
            return _result(True, "syntax", f"Syntax OK ({label}).")
        msg = out.replace(path, "main" + suffix)[:500]
        return _result(False, "syntax", msg, _first_line_number(msg, line_patterns))

    return _with_tempfile(code, suffix, go)


def _validate_javascript(code):
    return _check_with(code, ".js", lambda p, d: ["node", "--check", p], "node --check",
                       [r"main\.js:(\d+)", r":(\d+)\n"], "node")


def _validate_typescript(code):
    """Uses the TypeScript compiler (`npm i -g typescript`). Node's own --check cannot read types."""
    if not shutil.which("tsc"):
        return None

    def go(path, d):
        try:
            proc = _run(["tsc", "--noEmit", "--target", "es2020", "--lib", "es2020,dom", "--skipLibCheck",
                         "--pretty", "false", path], cwd=d)
        except subprocess.TimeoutExpired:
            return _result(False, "syntax", "tsc check timed out.")
        # Missing Node typings (require/process/module) are environment noise, not user bugs.
        errors = [ln for ln in proc.stdout.splitlines()
                  if "error TS" in ln and not re.search(r"TS2580|TS2591|TS2307|TS2304.*'(require|process|module|Buffer)'", ln)]
        if not errors:
            return _result(True, "syntax", "Syntax and types OK (tsc).")
        msg = "\n".join(errors[:4]).replace(path, "main.ts")[:500]
        return _result(False, "syntax", msg, _first_line_number(msg, [r"main\.ts\((\d+),\d+\)"]))

    return _with_tempfile(code, ".ts", go)


def _fallback_c_syntax(code: str) -> dict | None:
    lines = code.splitlines()
    in_block = 0
    for idx, raw in enumerate(lines):
        line = raw.strip()
        if "//" in line:
            line = line.split("//")[0].strip()
        if not line or line.startswith("#"):
            continue
        in_block += line.count("{") - line.count("}")
        if in_block > 0:
            if not line.endswith((";", "{", "}", ":", ",", "\\")):
                if not re.match(r"^(if|else|for|while|switch|case|default|do)\b", line):
                    next_idx = idx + 1
                    while next_idx < len(lines) and not lines[next_idx].strip():
                        next_idx += 1
                    if next_idx < len(lines):
                        nxt = lines[next_idx].strip()
                        if not nxt.startswith((";", ",", ")", "}")):
                            first_token = nxt.split()[0].rstrip(";({")
                            return _result(False, "syntax", f"error: expected ';' before '{first_token}'", next_idx + 1)
    return None


def _validate_c(code):
    res = _check_with(code, ".c", lambda p, d: ["gcc", "-fsyntax-only", "-w", p], "gcc",
                      [r"main\.c:(\d+):\d+: error"], "gcc")
    if res is None:
        return _fallback_c_syntax(code)
    return res


def _validate_cpp(code):
    return _check_with(code, ".cpp", lambda p, d: ["g++", "-std=c++17", "-fsyntax-only", "-w", p], "g++",
                       [r"main\.cpp:(\d+):\d+: error"], "g++")


def _validate_php(code):
    if not code.lstrip().startswith("<?"):
        code = "<?php\n" + code
    return _check_with(code, ".php", lambda p, d: ["php", "-l", p], "php -l", [r"on line (\d+)"], "php")


def _validate_go(code):
    return _check_with(code, ".go", lambda p, d: ["gofmt", "-e", p], "gofmt", [r"main\.go:(\d+):\d+"], "gofmt")


def _validate_rust(code):
    return _check_with(code, ".rs",
                       lambda p, d: ["rustc", "--edition", "2021", "--emit=metadata", "-o", os.path.join(d, "out.rmeta"), p],
                       "rustc", [r"-->\s*main\.rs:(\d+):\d+"], "rustc")


def _validate_java(code):
    return _check_with(code, ".java", lambda p, d: ["javac", "-Xlint:none", p], "javac",
                       [r"main\.java:(\d+): error"], "javac")


def _validate_csharp(code):
    tool = "csc" if shutil.which("csc") else "mcs"
    return _check_with(code, ".cs", lambda p, d: [tool, "-out:" + os.path.join(d, "out.exe"), p], tool,
                       [r"main\.cs\((\d+),\d+\)"], tool)


# ---------------------------------------------------------------- fallback
def _validate_generic(code):
    """Bracket balance that ignores strings and comments (so 'a ) b' in a string is fine)."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    closers = set(pairs.values())
    stack = []  # (expected_closer, line)
    i, n, line = 0, len(code), 1
    while i < n:
        ch = code[i]
        nxt = code[i + 1] if i + 1 < n else ""
        if ch == "\n":
            line += 1
        elif ch == "/" and nxt == "/" or ch == "#":
            while i < n and code[i] != "\n":
                i += 1
            continue
        elif ch == "/" and nxt == "*":
            end = code.find("*/", i + 2)
            end = n if end == -1 else end + 2
            line += code.count("\n", i, end)
            i = end
            continue
        elif ch in ("'", '"', "`"):
            j = i + 1
            while j < n and code[j] != ch:
                if code[j] == "\\":
                    j += 1
                if j < n and code[j] == "\n" and ch != "`":
                    break
                j += 1
            line += code.count("\n", i, min(j, n))
            i = j + 1
            continue
        elif ch in pairs:
            stack.append((pairs[ch], line))
        elif ch in closers:
            if not stack or stack[-1][0] != ch:
                return _result(False, "syntax", f"Unbalanced '{ch}' on line {line}.", line)
            stack.pop()
        i += 1
    if stack:
        closer, opened = stack[-1]
        return _result(False, "syntax", f"Unclosed bracket opened on line {opened} (expected '{closer}').", opened)
    return _result(None, "syntax", "No compiler for this language is installed here; only a bracket-balance check passed.")


_TOOL_VALIDATORS = {
    "javascript": _validate_javascript,
    "typescript": _validate_typescript,
    "c": _validate_c,
    "cpp": _validate_cpp,
    "php": _validate_php,
    "go": _validate_go,
    "rust": _validate_rust,
    "java": _validate_java,
    "csharp": _validate_csharp,
}


def validate_code(language: str, code: str, expected_output: str = None, test_input: str = None) -> dict:
    language = normalize_language(language)
    if not code or not code.strip():
        return _result(False, "syntax", "No code was provided to validate.")

    if language == "python":
        return _validate_python(code, expected_output, test_input)

    fn = _TOOL_VALIDATORS.get(language)
    if fn:
        res = fn(code)
        if res is not None:
            return _blame_previous_line(code, res)
    return _validate_generic(code)


if __name__ == "__main__":
    print(validate_code("python", "def add(a, b):\n    return a + b"))
    print(validate_code("python", "def add(a, b\n    return a + b"))
    print(validate_code("c", "int main(void) { return 0 }"))
