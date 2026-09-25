"""
runner.py
---------
Compiles and runs practice submissions in a throw-away temp directory.

SECURITY NOTE - read this before deploying:
  This runner applies a timeout, CPU / file-size / memory limits, a clean
  environment and a private working directory. That is fine for a learning
  project on your own machine, but it is NOT a full sandbox: submitted code
  can still touch the network and read files the server user can read.
  For a public deployment run this inside Docker/gVisor/Firecracker or use a
  judge service such as Judge0 or Piston instead.

PISTON FALLBACK:
  When a language's local toolchain (gcc, rustc, etc.) is not installed,
  the runner automatically falls back to the free Piston API
  (https://emkc.org/api/v2/piston/execute).  No API key required.
  Set PISTON_ENABLED=false in the environment to disable this fallback.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import json as _json

from backend.config import RUN_TIMEOUT_SECONDS

MAX_OUTPUT = 10_000
IS_POSIX = os.name == "posix"

# Set PISTON_ENABLED=false to disable the free-API fallback
PISTON_ENABLED = os.environ.get("PISTON_ENABLED", "true").lower() not in ("false", "0", "no")
PISTON_URL = os.environ.get("PISTON_URL", "https://emkc.org/api/v2/piston/execute")

# Piston language/version mapping
_PISTON_LANG = {
    "python":     ("python",  "3.10.0"),
    "javascript": ("javascript", "18.15.0"),
    "typescript": ("typescript", "5.0.3"),
    "java":       ("java",    "15.0.2"),
    "c":          ("c",       "10.2.0"),
    "cpp":        ("c++",     "10.2.0"),
    "csharp":     ("csharp",  "6.12.0"),
    "go":         ("go",      "1.16.2"),
    "rust":       ("rust",    "1.50.0"),
    "php":        ("php",     "8.2.3"),
}


# language -> (source filename, executables that must exist)
_SPEC = {
    "python": ("main.py", [sys.executable or "python"]),
    "javascript": ("main.js", ["node"]),
    "typescript": ("main.ts", ["node"]),
    "java": ("Main.java", ["javac", "java"]),
    "c": ("main.c", ["gcc"]),
    "cpp": ("main.cpp", ["g++"]),
    "csharp": ("Program.cs", []),  # mono (mcs+mono) or dotnet - checked below
    "go": ("main.go", ["go"]),
    "rust": ("main.rs", ["rustc"]),
    "php": ("main.php", ["php"]),
}
# runtimes with big virtual-memory footprints break under RLIMIT_AS
_NO_MEM_LIMIT = {"javascript", "typescript", "java", "go", "csharp", "rust"}


def _node_supports_ts() -> bool:
    if not shutil.which("node"):
        return False
    try:
        out = subprocess.run(["node", "-v"], capture_output=True, text=True, timeout=5).stdout.strip().lstrip("v")
        major, minor = (int(x) for x in out.split(".")[:2])
        return (major, minor) >= (22, 6)
    except Exception:
        return False


def is_available(language: str) -> bool:
    if language not in _SPEC:
        return False
    # If local toolchain is installed, use it
    local = False
    if language == "python":
        local = bool(sys.executable or shutil.which("python3") or shutil.which("python"))
    elif language == "csharp":
        local = bool(shutil.which("dotnet") or (shutil.which("mcs") and shutil.which("mono")))
    elif language == "typescript":
        local = _node_supports_ts()
    else:
        local = all(shutil.which(t) for t in _SPEC[language][1])
    if local:
        return True
    # Fall back: Piston API covers this language
    return PISTON_ENABLED and language in _PISTON_LANG


def available_languages() -> dict:
    return {lang: is_available(lang) for lang in _SPEC}


def _limits(language: str):
    def apply():
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (RUN_TIMEOUT_SECONDS + 2, RUN_TIMEOUT_SECONDS + 2))
        resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))
        if language not in _NO_MEM_LIMIT:
            resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
        os.setsid()
    return apply if IS_POSIX else None


def _env(workdir):
    env = {"PATH": os.environ.get("PATH", ""), "HOME": workdir, "TMPDIR": workdir, "LANG": "C.UTF-8"}
    for k in ("SYSTEMROOT", "GOCACHE", "GOPATH", "DOTNET_ROOT", "JAVA_HOME"):  # needed on some platforms
        if k in os.environ:
            env[k] = os.environ[k]
    if shutil.which("go") and "GOCACHE" not in env:
        env["GOCACHE"] = os.path.join(tempfile.gettempdir(), "bf_gocache")  # shared cache keeps `go build` fast
    env["DOTNET_CLI_TELEMETRY_OPTOUT"] = "1"
    return env


def _trim(text: str) -> str:
    return text if len(text) <= MAX_OUTPUT else text[:MAX_OUTPUT] + "\n...[output truncated]"


def _exec(cmd, stdin, workdir, language, timeout):
    try:
        proc = subprocess.run(
            cmd, input=stdin, capture_output=True, text=True, timeout=timeout,
            cwd=workdir, env=_env(workdir), preexec_fn=_limits(language),
        )
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "stdout": "", "stderr": f"Time limit exceeded ({timeout}s). Possible infinite loop."}
    return {
        "status": "ok" if proc.returncode == 0 else "runtime_error",
        "stdout": _trim(proc.stdout), "stderr": _trim(proc.stderr), "returncode": proc.returncode,
    }


def _prepare(language: str, code: str, workdir: str):
    """Writes source + compiles. Returns (run_cmd, None) or (None, error_dict)."""
    filename = _SPEC[language][0]
    path = os.path.join(workdir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)

    def compile_(cmd):
        res = _exec(cmd, "", workdir, language, 60)
        if res["status"] != "ok":
            msg = (res["stderr"] or res["stdout"]).replace(workdir + os.sep, "")
            return {"status": "compile_error", "stdout": "", "stderr": _trim(msg)}
        return None

    if language == "python":
        py_bin = sys.executable or shutil.which("python3") or "python"
        return [py_bin, filename], None
    if language == "javascript":
        return ["node", filename], None
    if language == "typescript":
        return ["node", "--experimental-strip-types", "--no-warnings", filename], None
    if language == "php":
        return ["php", filename], None
    if language == "c":
        err = compile_(["gcc", "-O2", "-o", "prog", filename, "-lm"])
        return (["./prog"], None) if not err else (None, err)
    if language == "cpp":
        err = compile_(["g++", "-std=c++17", "-O2", "-o", "prog", filename])
        return (["./prog"], None) if not err else (None, err)
    if language == "java":
        err = compile_(["javac", "-d", ".", filename])
        return (["java", "-Xmx256m", "Main"], None) if not err else (None, err)
    if language == "go":
        err = compile_(["go", "build", "-o", "prog", filename])
        return (["./prog"], None) if not err else (None, err)
    if language == "rust":
        err = compile_(["rustc", "--edition", "2021", "-O", "-o", "prog", filename])
        return (["./prog"], None) if not err else (None, err)
    if language == "csharp":
        if shutil.which("mcs") and shutil.which("mono"):
            err = compile_(["mcs", "-out:prog.exe", filename])
            return (["mono", "prog.exe"], None) if not err else (None, err)
        with open(os.path.join(workdir, "app.csproj"), "w") as f:
            f.write('<Project Sdk="Microsoft.NET.Sdk"><PropertyGroup><OutputType>Exe</OutputType>'
                    '<TargetFramework>net8.0</TargetFramework><Nullable>disable</Nullable>'
                    '<ImplicitUsings>disable</ImplicitUsings></PropertyGroup></Project>')
        err = compile_(["dotnet", "build", "-o", "out", "-nologo", "-v", "q"])
        return (["dotnet", "out/app.dll"], None) if not err else (None, err)
    return None, {"status": "unavailable", "stdout": "", "stderr": f"{language} is not supported."}



def _run_via_piston(language: str, code: str, stdin: str) -> dict:
    """
    Execute code via the free Piston API (https://emkc.org/api/v2/piston).
    Returns the same shape as _exec(): {status, stdout, stderr, returncode}.
    """
    lang_id, version = _PISTON_LANG.get(language, (language, "*"))
    payload = _json.dumps({
        "language": lang_id,
        "version": version,
        "files": [{"content": code}],
        "stdin": stdin,
        "run_timeout": RUN_TIMEOUT_SECONDS * 1000,
        "compile_timeout": 30000,
    }).encode()
    try:
        req = urllib.request.Request(
            PISTON_URL,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "ai-bugfixer/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=RUN_TIMEOUT_SECONDS + 10) as resp:
            data = _json.loads(resp.read())
    except Exception as exc:
        return {"status": "runtime_error", "stdout": "", "stderr": f"Piston API error: {exc}", "returncode": 1}

    compile_stage = data.get("compile", {})
    run_stage = data.get("run", {})

    if compile_stage and compile_stage.get("code", 0) != 0:
        msg = (compile_stage.get("stderr") or compile_stage.get("stdout") or "Compile error").strip()
        return {"status": "compile_error", "stdout": "", "stderr": _trim(msg), "returncode": compile_stage.get("code", 1)}

    stdout = _trim((run_stage.get("stdout") or ""))
    stderr = _trim((run_stage.get("stderr") or ""))
    rc = run_stage.get("code", 0)
    if run_stage.get("signal") == "SIGKILL":
        return {"status": "timeout", "stdout": "", "stderr": f"Time limit exceeded ({RUN_TIMEOUT_SECONDS}s). Possible infinite loop."}
    return {
        "status": "ok" if rc == 0 else "runtime_error",
        "stdout": stdout,
        "stderr": stderr,
        "returncode": rc,
    }


def run_tests(language: str, code: str, tests: list[tuple[str, str]]) -> dict:
    """
    Returns {"status": ..., "compile_error": str|None, "results": [ {passed, actual, stderr, status} ... ]}
    status is 'ok' when the code compiled and every test ran (pass or fail), otherwise
    'compile_error' / 'unavailable'.

    When a local toolchain is not installed, falls back to the free Piston API
    if PISTON_ENABLED=true (the default).
    """
    local_ok = is_available(language)
    use_piston = not local_ok and PISTON_ENABLED and language in _PISTON_LANG

    if not local_ok and not use_piston:
        return {
            "status": "unavailable",
            "message": (
                f"The {language} toolchain is not installed on this server and the Piston "
                f"API fallback is disabled. Install {language} or set PISTON_ENABLED=true."
            ),
            "results": [],
        }

    if use_piston:
        # Run all tests via Piston (one API call per test — acceptable for small test sets)
        results = []
        for stdin, expected in tests:
            res = _run_via_piston(language, code, stdin + "\n")
            if res["status"] == "compile_error":
                return {"status": "compile_error", "message": res["stderr"], "results": []}
            actual = res["stdout"].replace("\r\n", "\n").strip()
            passed = res["status"] == "ok" and actual == expected.strip()
            results.append({"passed": passed, "actual": actual, "stderr": res["stderr"], "status": res["status"]})
        return {"status": "ok", "message": "(executed via Piston API — free remote judge)", "results": results}

    # --- local execution path (unchanged) ---
    workdir = tempfile.mkdtemp(prefix="bf_run_")
    try:
        cmd, err = _prepare(language, code, workdir)
        if err:
            return {"status": err["status"], "message": err["stderr"], "results": []}

        results = []
        for stdin, expected in tests:
            res = _exec(cmd, stdin + "\n", workdir, language, RUN_TIMEOUT_SECONDS)
            actual = res["stdout"].replace("\r\n", "\n").strip()
            passed = res["status"] == "ok" and actual == expected.strip()
            results.append({"passed": passed, "actual": actual, "stderr": res["stderr"], "status": res["status"]})
        return {"status": "ok", "message": "", "results": results}
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

