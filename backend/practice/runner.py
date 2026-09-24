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
"""

import os
import shutil
import subprocess
import sys
import tempfile

from backend.config import RUN_TIMEOUT_SECONDS

MAX_OUTPUT = 10_000
IS_POSIX = os.name == "posix"

# language -> (source filename, executables that must exist)
_SPEC = {
    "python": ("main.py", ["python3"]),
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
    if language == "csharp":
        return bool(shutil.which("dotnet") or (shutil.which("mcs") and shutil.which("mono")))
    if language == "typescript":
        return _node_supports_ts()
    return all(shutil.which(t) for t in _SPEC[language][1])


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
        return ["python3", filename], None
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


def run_tests(language: str, code: str, tests: list[tuple[str, str]]) -> dict:
    """
    Returns {"status": ..., "compile_error": str|None, "results": [ {passed, actual, stderr, status} ... ]}
    status is 'ok' when the code compiled and every test ran (pass or fail), otherwise
    'compile_error' / 'unavailable'.
    """
    if not is_available(language):
        return {"status": "unavailable", "message": f"No {language} toolchain is installed on the server.", "results": []}

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
