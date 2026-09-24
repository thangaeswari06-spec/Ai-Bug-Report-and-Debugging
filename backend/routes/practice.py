"""
practice.py
-----------
GET  /practice/languages            which of the 10 languages can run on this server
GET  /practice/problems             list + my progress
GET  /practice/problems/{id}        statement, examples and starter code for one language
POST /practice/run                  run against the visible example tests only
POST /practice/submit               run against ALL tests (hidden ones too) + save progress
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.config import MAX_CODE_CHARS
from backend.db import get_db
from backend.practice.problems import PROBLEMS, VISIBLE_TESTS, get_problem, public_problem
from backend.practice.runner import available_languages, run_tests
from backend.security import RateLimiter, get_current_user, notify
from backend.utils.languages import LANGUAGES, strict_language

router = APIRouter(prefix="/practice", tags=["practice"])
_run_limiter = RateLimiter("practice-run", limit=20, window_seconds=60)


class RunBody(BaseModel):
    problem_id: str
    language: str
    code: str = Field(..., min_length=1, max_length=MAX_CODE_CHARS)

    @field_validator("language")
    @classmethod
    def _lang(cls, v):
        return strict_language(v)


@router.get("/languages")
def languages(user: dict = Depends(get_current_user)):
    avail = available_languages()
    return [{**l, "runnable": avail.get(l["id"], False)} for l in LANGUAGES]


@router.get("/problems")
def list_problems(user: dict = Depends(get_current_user)):
    with get_db() as db:
        rows = db.execute("SELECT problem_id, language, attempts, solved FROM practice_progress WHERE user_id=?",
                          (user["id"],)).fetchall()
    solved, attempts = {}, {}
    for r in rows:
        attempts[r["problem_id"]] = attempts.get(r["problem_id"], 0) + r["attempts"]
        if r["solved"]:
            solved.setdefault(r["problem_id"], []).append(r["language"])
    items = [{**public_problem(p), "solved_languages": solved.get(p["id"], []), "attempts": attempts.get(p["id"], 0)}
             for p in PROBLEMS]
    return {
        "problems": items,
        "stats": {"solved": len(solved), "total": len(PROBLEMS),
                  "languages_used": len({l for ls in solved.values() for l in ls})},
    }


@router.get("/problems/{problem_id}")
def get_one(problem_id: str, language: str = "python", user: dict = Depends(get_current_user)):
    p = get_problem(problem_id)
    if not p:
        raise HTTPException(404, "Problem not found.")
    try:
        language = strict_language(language)
    except ValueError:
        raise HTTPException(400, "Unsupported language.")
    return public_problem(p, include_starter_for=language)


def _execute(body: RunBody, only_visible: bool):
    p = get_problem(body.problem_id)
    if not p:
        raise HTTPException(404, "Problem not found.")
    tests = p["tests"][:VISIBLE_TESTS] if only_visible else p["tests"]
    outcome = run_tests(body.language, body.code, tests)
    if outcome["status"] == "unavailable":
        raise HTTPException(503, outcome["message"])

    shaped = []
    for i, r in enumerate(outcome["results"]):
        hidden = i >= VISIBLE_TESTS
        item = {"index": i + 1, "passed": r["passed"], "hidden": hidden, "status": r["status"]}
        if not hidden:  # never leak hidden inputs/expected outputs
            item.update(input=tests[i][0], expected=tests[i][1], actual=r["actual"], stderr=r["stderr"])
        elif not r["passed"] and r["status"] != "ok":
            item["stderr"] = r["stderr"]
        shaped.append(item)

    passed = sum(1 for r in shaped if r["passed"])
    return {
        "status": outcome["status"],           # ok | compile_error
        "message": outcome.get("message", ""),
        "passed": passed, "total": len(tests), "results": shaped,
        "all_passed": outcome["status"] == "ok" and passed == len(tests),
    }


@router.post("/run", dependencies=[Depends(_run_limiter)])
def run(body: RunBody, user: dict = Depends(get_current_user)):
    return _execute(body, only_visible=True)


@router.post("/submit", dependencies=[Depends(_run_limiter)])
def submit(body: RunBody, user: dict = Depends(get_current_user)):
    result = _execute(body, only_visible=False)
    now = datetime.now(timezone.utc).isoformat()
    first_solve = False
    with get_db() as db:
        row = db.execute("SELECT solved FROM practice_progress WHERE user_id=? AND problem_id=? AND language=?",
                         (user["id"], body.problem_id, body.language)).fetchone()
        if row is None:
            db.execute("INSERT INTO practice_progress (user_id, problem_id, language, attempts, solved, updated_at) "
                       "VALUES (?,?,?,?,?,?)", (user["id"], body.problem_id, body.language, 1, int(result["all_passed"]), now))
            first_solve = result["all_passed"]
        else:
            first_solve = result["all_passed"] and not row["solved"]
            db.execute("UPDATE practice_progress SET attempts=attempts+1, solved=?, updated_at=? "
                       "WHERE user_id=? AND problem_id=? AND language=?",
                       (int(bool(row["solved"]) or result["all_passed"]), now, user["id"], body.problem_id, body.language))
    if first_solve:
        p = get_problem(body.problem_id)
        notify(user["id"], "practice", f"Solved: {p['title']} 🎉", f"Nice work - {body.language} solution passed all {result['total']} tests.")
    result["first_solve"] = first_solve
    return result
