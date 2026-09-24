"""
End-to-end API tests for accounts, security, error-line location, OCR,
history isolation, notifications and the practice arena.

Run:  pytest tests/test_v2_api.py -q
"""

import io
import os
import tempfile

_tmp = tempfile.mkdtemp()
os.environ["BUGFIXER_DB"] = os.path.join(_tmp, "test.db")
os.environ["RUN_TIMEOUT_SECONDS"] = "2"

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from backend.main import app
from backend.practice.runner import available_languages

client = TestClient(app)
PW = "Str0ngPass"


def signup(email, name="Tester"):
    r = client.post("/auth/signup", json={"name": name, "email": email, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()["token"], r.json()["user"]


def H(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def alice():
    return signup("alice@example.com", "Alice")


@pytest.fixture(scope="module")
def bob():
    return signup("bob@example.com", "Bob")


# ------------------------------------------------------------------ auth
def test_protected_routes_need_login():
    for method, path in [("get", "/history"), ("get", "/notifications"), ("get", "/auth/me"), ("get", "/practice/problems")]:
        assert getattr(client, method)(path).status_code == 401
    assert client.post("/analyze", json={"language": "python", "code": "x", "error": "y"}).status_code == 401


def test_password_policy_and_duplicate(alice):
    r = client.post("/auth/signup", json={"name": "X", "email": "weak@example.com", "password": "abc"})
    assert r.status_code == 400 and "Password needs" in r.json()["detail"]
    assert client.post("/auth/signup", json={"name": "A", "email": "ALICE@example.com", "password": PW}).status_code == 409
    assert client.post("/auth/signup", json={"name": "A", "email": "not-an-email", "password": PW}).status_code == 400


def test_tampered_token_rejected(alice):
    token, _ = alice
    assert client.get("/auth/me", headers=H(token + "x")).status_code == 401
    assert client.get("/auth/me", headers=H(token)).json()["email"] == "alice@example.com"


def test_lockout_after_failed_logins():
    signup("lock@example.com")
    for _ in range(4):
        assert client.post("/auth/login", json={"email": "lock@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", json={"email": "lock@example.com", "password": "wrong"}).status_code == 423
    # even the right password is refused while locked
    assert client.post("/auth/login", json={"email": "lock@example.com", "password": PW}).status_code == 423


def test_unknown_email_same_message_as_wrong_password(alice):
    a = client.post("/auth/login", json={"email": "nobody@example.com", "password": PW})
    b = client.post("/auth/login", json={"email": "alice@example.com", "password": "Wrong1234"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


def test_google_not_configured(monkeypatch):
    monkeypatch.setattr("backend.routes.auth.GOOGLE_CLIENT_ID", "")
    assert client.get("/auth/config").json()["google_enabled"] is False
    assert client.post("/auth/google", json={"credential": "x" * 40}).status_code == 503


def test_google_configured(monkeypatch):
    monkeypatch.setattr("backend.routes.auth.GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    cfg = client.get("/auth/config").json()
    assert cfg["google_enabled"] is True
    assert cfg["google_client_id"] == "test-client-id.apps.googleusercontent.com"


def test_change_password(alice):
    token, _ = alice
    assert client.post("/auth/change-password", headers=H(token),
                       json={"current_password": "nope", "new_password": "NewPass123"}).status_code == 400
    assert client.post("/auth/change-password", headers=H(token),
                       json={"current_password": PW, "new_password": "NewPass123"}).status_code == 200
    assert client.post("/auth/login", json={"email": "alice@example.com", "password": "NewPass123"}).status_code == 200


def test_security_headers():
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "DENY"


# ----------------------------------------------------- profile + avatar
def test_profile_update_and_avatar(bob):
    token, _ = bob
    r = client.put("/auth/me", headers=H(token), json={"name": "Bobby", "default_language": "go", "accent": "cyan"})
    assert r.json()["name"] == "Bobby" and r.json()["default_language"] == "go"
    assert client.put("/auth/me", headers=H(token), json={"default_language": "cobol"}).status_code == 400

    img = Image.new("RGB", (400, 300), (200, 50, 50)); buf = io.BytesIO(); img.save(buf, "PNG")
    r = client.post("/auth/avatar", headers=H(token), files={"file": ("me.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200 and r.json()["avatar"].startswith("data:image/webp;base64,")
    # not an image -> rejected
    r = client.post("/auth/avatar", headers=H(token), files={"file": ("x.png", b"<script>alert(1)</script>", "image/png")})
    assert r.status_code == 400
    assert client.delete("/auth/avatar", headers=H(token)).json()["avatar"] is None


# ------------------------------------------ analyze + error-line locating
def test_python_error_line_from_traceback(alice, bob):
    token, _ = bob
    code = "total = 10\ncount = 0\nprint(total / count)\n"
    trace = 'Traceback (most recent call last):\n  File "app.py", line 3, in <module>\nZeroDivisionError: division by zero'
    r = client.post("/analyze", headers=H(token), json={
        "language": "python", "code": code, "error": "ZeroDivisionError: division by zero", "stack_trace": trace})
    assert r.status_code == 200, r.text
    locs = r.json()["error_locations"]
    assert locs and locs[0]["line"] == 3 and "total / count" in locs[0]["text"] and "division by zero" in locs[0]["reason"]


def test_innermost_frame_is_the_error_and_outer_frames_are_callers(bob):
    token, _ = bob
    code = 'def average(t, c):\n    return t / c\n\nprint(average(10, 0))\n'
    trace = ('Traceback (most recent call last):\n  File "app.py", line 4, in <module>\n    print(average(10, 0))\n'
             '  File "app.py", line 2, in average\n    return t / c\nZeroDivisionError: division by zero')
    r = client.post("/analyze", headers=H(token), json={"language": "python", "code": code,
                    "error": "ZeroDivisionError: division by zero", "stack_trace": trace}).json()
    by_line = {l["line"]: l for l in r["error_locations"]}
    assert "raised here" in by_line[2]["reason"] and by_line[2]["source"] == "trace"
    assert by_line[4]["source"] == "caller" and "line 2" in by_line[4]["reason"]


def test_syntax_error_line_from_parser_without_trace(bob):
    token, _ = bob
    r = client.post("/analyze", headers=H(token), json={
        "language": "c", "code": "#include <stdio.h>\nint main(void) {\n    int x = 5\n    printf(\"%d\", x);\n    return 0;\n}\n",
        "error": "error: expected ';' before 'printf'"})
    body = r.json()
    assert [l["line"] for l in body["error_locations"]] == [3]   # the line missing the ';', not line 4
    assert "syntax" in body["error_locations"][0]["sources"]


def test_all_ten_languages_accepted(bob):
    token, _ = bob
    for lang in ["python", "javascript", "typescript", "java", "c", "cpp", "csharp", "go", "rust", "php"]:
        r = client.post("/analyze", headers=H(token), json={"language": lang, "code": "x", "error": "boom"})
        assert r.status_code == 200, (lang, r.text)
    assert client.post("/analyze", headers=H(token), json={"language": "cobol", "code": "x", "error": "boom"}).status_code == 422


def test_history_is_private_per_user(alice, bob):
    ta, tb = alice[0], bob[0]
    r = client.post("/analyze", headers=H(ta), json={"language": "python", "code": "print(1", "error": "SyntaxError"})
    item_id = r.json()["id"]
    assert any(i["id"] == item_id for i in client.get("/history", headers=H(ta)).json())
    assert not any(i["id"] == item_id for i in client.get("/history", headers=H(tb)).json())
    assert client.get(f"/history/{item_id}", headers=H(tb)).status_code == 404
    assert client.delete(f"/history/{item_id}", headers=H(tb)).status_code == 404
    assert client.delete(f"/history/{item_id}", headers=H(ta)).status_code == 200


def test_notifications(bob):
    token, _ = bob
    data = client.get("/notifications", headers=H(token)).json()
    assert data["unread"] >= 1 and any(n["kind"] == "welcome" for n in data["items"])
    client.post("/notifications/read-all", headers=H(token))
    assert client.get("/notifications", headers=H(token)).json()["unread"] == 0


# -------------------------------------------------------------------- OCR
def test_ocr_reads_dark_screenshot(alice):
    token = alice[0]
    import shutil
    from backend.ai.ocr import pytesseract
    tess_cmd = getattr(pytesseract, "pytesseract", None) and getattr(pytesseract.pytesseract, "tesseract_cmd", None)
    has_tess = pytesseract is not None and (shutil.which("tesseract") or (tess_cmd and os.path.exists(tess_cmd)) or os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"))
    if not has_tess:
        pytest.skip("Tesseract OCR engine is not installed on this machine (installed in Docker/production container).")
    from PIL import ImageFont
    import glob
    fonts = glob.glob("/usr/share/fonts/**/*Mono*.ttf", recursive=True)
    font = ImageFont.truetype(fonts[0], 22) if fonts else ImageFont.load_default()
    img = Image.new("RGB", (900, 140), (30, 30, 40)); d = ImageDraw.Draw(img)
    d.text((10, 10), 'File "app.py", line 7, in <module>\nZeroDivisionError: division by zero', fill=(230, 230, 230), font=font)
    buf = io.BytesIO(); img.save(buf, "PNG")
    r = client.post("/ocr", headers=H(token), files={"file": ("e.png", buf.getvalue(), "image/png")})
    assert r.status_code == 200, r.text
    assert "ZeroDivisionError" in r.json()["text"] and r.json()["language_guess"] == "python"


def test_ocr_rejects_non_image_and_oversize(alice):
    token = alice[0]
    assert client.post("/ocr", headers=H(token), files={"file": ("a.png", b"hello", "image/png")}).status_code == 400
    big = b"\x89PNG" + b"0" * (5 * 1024 * 1024 + 10)
    assert client.post("/ocr", headers=H(token), files={"file": ("a.png", big, "image/png")}).status_code == 413


# --------------------------------------------------------------- practice
PY_SOLUTIONS = {
    "sum-two": "a, b = map(int, input().split())\nprint(a + b)",
    "even-odd": "n = int(input())\nprint('Even' if n % 2 == 0 else 'Odd')",
    "max-list": "print(max(map(int, input().split())))",
    "factorial": "import math\nprint(math.factorial(int(input())))",
    "fizzbuzz": "n = int(input())\nfor i in range(1, n + 1):\n    print('FizzBuzz' if i % 15 == 0 else 'Fizz' if i % 3 == 0 else 'Buzz' if i % 5 == 0 else i)",
    "reverse-string": "print(input()[::-1])",
    "count-vowels": "print(sum(c in 'aeiouAEIOU' for c in input()))",
    "palindrome": "s = input().lower()\nprint('Yes' if s == s[::-1] else 'No')",
    "fibonacci": "a, b = 0, 1\nfor _ in range(int(input())):\n    a, b = b, a + b\nprint(a)",
    "prime-check": "n = int(input())\nprint('Prime' if n > 1 and all(n % i for i in range(2, int(n ** .5) + 1)) else 'Not Prime')",
}
OTHER_SOLUTIONS = {
    ("javascript", "sum-two"): 'const [a,b]=require("fs").readFileSync(0,"utf8").trim().split(/\\s+/).map(Number);console.log(a+b);',
    ("typescript", "reverse-string"): 'const s: string = require("fs").readFileSync(0,"utf8").split("\\n")[0];console.log(s.split("").reverse().join(""));',
    ("c", "sum-two"): '#include <stdio.h>\nint main(void){long long a,b;scanf("%lld %lld",&a,&b);printf("%lld\\n",a+b);return 0;}',
    ("cpp", "palindrome"): '#include <bits/stdc++.h>\nusing namespace std;\nint main(){string s;getline(cin,s);for(auto&c:s)c=tolower(c);string r(s.rbegin(),s.rend());cout<<(s==r?"Yes":"No")<<endl;}',
}


def test_practice_catalogue(alice):
    token = alice[0]
    langs = client.get("/practice/languages", headers=H(token)).json()
    assert len(langs) == 10 and langs[0]["id"] == "python" and langs[0]["runnable"] is True
    probs = client.get("/practice/problems", headers=H(token)).json()
    assert len(probs["problems"]) == 10 and probs["stats"]["solved"] == 0
    for lang in [l["id"] for l in langs]:                       # a starter exists for every language
        p = client.get(f"/practice/problems/fizzbuzz?language={lang}", headers=H(token)).json()
        assert p["starter"].strip() and len(p["examples"]) == 2


@pytest.mark.parametrize("pid", list(PY_SOLUTIONS))
def test_python_reference_solutions_pass_all_tests(alice, pid):
    r = client.post("/practice/submit", headers=H(alice[0]), json={"problem_id": pid, "language": "python", "code": PY_SOLUTIONS[pid]})
    assert r.status_code == 200, r.text
    assert r.json()["all_passed"], r.json()


@pytest.mark.parametrize("key", list(OTHER_SOLUTIONS))
def test_other_language_solutions(alice, key):
    lang, pid = key
    if not available_languages()[lang]:
        pytest.skip(f"{lang} toolchain not installed")
    r = client.post("/practice/submit", headers=H(alice[0]), json={"problem_id": pid, "language": lang, "code": OTHER_SOLUTIONS[key]})
    assert r.json()["all_passed"], r.json()


def test_wrong_answer_hidden_tests_and_progress(bob):
    token = bob[0]
    r = client.post("/practice/submit", headers=H(token), json={"problem_id": "sum-two", "language": "python", "code": "print(999)"}).json()
    assert not r["all_passed"] and r["passed"] == 0 and r["total"] == 5
    hidden = [x for x in r["results"] if x["hidden"]]
    assert hidden and all("input" not in x and "expected" not in x for x in hidden)   # no leaking
    r = client.post("/practice/run", headers=H(token), json={"problem_id": "sum-two", "language": "python", "code": "print(999)"}).json()
    assert r["total"] == 2                                                               # run = visible tests only


def test_timeout_and_compile_error(bob):
    token = bob[0]
    r = client.post("/practice/run", headers=H(token), json={"problem_id": "sum-two", "language": "python", "code": "while True: pass"}).json()
    assert r["results"][0]["status"] == "timeout"
    if available_languages().get("c"):
        r = client.post("/practice/run", headers=H(token), json={"problem_id": "sum-two", "language": "c", "code": "int main( {"}).json()
        assert r["status"] == "compile_error" and "error" in r["message"]
    else:
        r = client.post("/practice/run", headers=H(token), json={"problem_id": "sum-two", "language": "c", "code": "int main( {"})
        assert r.status_code == 503


def test_progress_and_solve_notification(alice):
    token = alice[0]
    stats = client.get("/practice/problems", headers=H(token)).json()["stats"]
    assert stats["solved"] >= 10
    assert any(n["kind"] == "practice" for n in client.get("/notifications", headers=H(token)).json()["items"])


def test_delete_account(bob):
    token, user = bob
    assert client.request("DELETE", "/auth/me", headers=H(token), json={"confirm_email": "wrong@x.com"}).status_code == 400
    assert client.request("DELETE", "/auth/me", headers=H(token), json={"confirm_email": user["email"]}).status_code == 200
    assert client.get("/auth/me", headers=H(token)).status_code == 401
