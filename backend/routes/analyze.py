"""
analyze.py
----------
POST /analyze - the full pipeline (requires sign-in):

    Code + Error -> Classifier -> Severity -> RAG -> Coding LLM
                 -> Validator (one bounded retry) -> Error-line locator
                 -> saved to THIS user's history + a bell notification
"""

import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from backend.ai.classifier import get_classifier
from backend.ai.llm import CodingLLM
from backend.ai.locator import locate_errors
from backend.ai.rag import RAGRetriever
from backend.ai.severity import SeverityPredictor
from backend.ai.validator import validate_code
from backend.db import get_db
from backend.security import RateLimiter, get_current_user, notify
from backend.utils.schemas import AnalyzeRequest, AnalyzeResponse

router = APIRouter()

# Expensive to load, so created once and shared by all requests.
_classifier = get_classifier()
_severity_model = SeverityPredictor()
_rag = RAGRetriever()
_llm = CodingLLM()

_analyze_limiter = RateLimiter("analyze", limit=30, window_seconds=60)
MAX_HISTORY_PER_USER = 200


def run_pipeline(language, code, error, stack_trace="", expected_output=None, test_input=None) -> dict:
    bug = _classifier.predict(language=language, code=code, error=error, stack_trace=stack_trace)
    sev = _severity_model.predict(bug_type=bug["bug_type"], code=code, error=error, stack_trace=stack_trace)
    rag_hits = _rag.retrieve(language=language, code=code, error=error, stack_trace=stack_trace, top_k=3)

    def ask_llm(err_text):
        return _llm.generate(
            language=language, code=code, error=err_text, stack_trace=stack_trace,
            bug_type=bug["bug_type"], bug_confidence=bug["confidence"],
            severity=str(sev["severity"]), rag_hits=rag_hits,
        )

    llm_result = ask_llm(error)
    validation = validate_code(language, llm_result.get("corrected_code", ""), expected_output, test_input)

    retried = False
    if validation["valid"] is False:  # one bounded retry, as in the original spec
        retried = True
        llm_result = ask_llm(
            f"{error}\n\nPREVIOUS ATTEMPT FAILED VALIDATION: {validation['message']}. "
            f"Fix the corrected_code so it is valid {language}."
        )
        validation = validate_code(language, llm_result.get("corrected_code", ""), expected_output, test_input)

    # Compile/parse the ORIGINAL code too - gives an exact line for syntax errors.
    original_check = validate_code(language, code)
    locations = locate_errors(
        language=language, code=code, error=error, stack_trace=stack_trace,
        root_cause=llm_result.get("root_cause", ""), corrected_code=llm_result.get("corrected_code", ""),
        llm_lines=llm_result.get("error_lines"), syntax_result=original_check,
    )

    return {
        "id": str(uuid.uuid4()),
        "language": language,
        "bug_type": bug["bug_type"],
        "severity": str(sev["severity"]),
        "confidence": bug["confidence"],
        "root_cause": llm_result.get("root_cause", ""),
        "explanation": llm_result.get("explanation", ""),
        "fix": llm_result.get("fix", ""),
        "corrected_code": llm_result.get("corrected_code", ""),
        "error_locations": locations,
        "validation": validation,
        "similar_known_bugs": rag_hits,
        "retried": retried,
    }


@router.post("/analyze", response_model=AnalyzeResponse, dependencies=[Depends(_analyze_limiter)])
def analyze_bug(request: AnalyzeRequest, user: dict = Depends(get_current_user)):
    response = run_pipeline(
        request.language, request.code, request.error, request.stack_trace or "",
        request.expected_output, request.test_input,
    )

    now = datetime.now(timezone.utc).isoformat()
    record = {**response, "original_code": request.code, "original_error": request.error, "created_at": now}
    with get_db() as db:
        db.execute(
            "INSERT INTO analyses (id, user_id, payload, created_at) VALUES (?,?,?,?)",
            (response["id"], user["id"], json.dumps(record), now),
        )
        # keep only the newest MAX_HISTORY_PER_USER
        db.execute(
            "DELETE FROM analyses WHERE user_id=? AND id NOT IN "
            "(SELECT id FROM analyses WHERE user_id=? ORDER BY created_at DESC LIMIT ?)",
            (user["id"], user["id"], MAX_HISTORY_PER_USER),
        )

    where = f" at line {response['error_locations'][0]['line']}" if response["error_locations"] else ""
    notify(user["id"], "analysis", f"{response['bug_type']} analysed{where}",
           f"{response['severity']} severity · {response['language']}")
    return response
