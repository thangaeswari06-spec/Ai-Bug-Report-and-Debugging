"""
test_day3_pipeline.py
------------------------
Demonstrates and verifies the Day 3 deliverable end-to-end:

    Bug -> RAG context -> LLM -> root cause + recommended fix + corrected code

The Day-1 classifier (needs a live CodeBERT download) and the live LLM
call (needs Ollama/API network access) are mocked here since this
environment has neither. The Day-2 severity model and Day-3 RAG
retrieval are REAL — they run against the actual trained model and the
actual knowledge base, nothing is faked there.

Run:
    python -m tests.test_day3_pipeline
"""

import json
from unittest.mock import patch

from backend.ai.severity import SeverityPredictor
from backend.ai.rag import RAGRetriever
from backend.ai.llm import CodingLLM, build_prompt


def mock_classifier_predict(language, code, error, stack_trace=""):
    """Stand-in for backend.ai.classifier.BugClassifier.predict (Day 1)."""
    return {"bug_type": "Database Error", "confidence": 0.94}


def mock_llm_call(prompt: str) -> str:
    """Stand-in for a live Ollama/API call — proves the JSON contract works."""
    return json.dumps(
        {
            "root_cause": "Raw string concatenation builds the SQL query, allowing unsafe/malformed SQL.",
            "explanation": "user_id is concatenated directly into the query string instead of being bound as a parameter.",
            "fix": "Use a parameterized query so the driver escapes values safely.",
            "corrected_code": "cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))",
        }
    )


def run_pipeline():
    language = "python"
    code = "cursor.execute('SELECT * FROM users WHERE id = ' + user_id)"
    error = "psycopg2.errors.SyntaxError: syntax error at or near ..."
    stack_trace = "psycopg2.errors.SyntaxError: syntax error at or near"

    # --- Day 1 (mocked) ---
    bug_result = mock_classifier_predict(language, code, error, stack_trace)
    print("Day 1 - Bug classification:", bug_result)

    # --- Day 2 (real, trained model) ---
    severity_model = SeverityPredictor()
    severity_result = severity_model.predict(
        bug_type=bug_result["bug_type"], code=code, error=error, stack_trace=stack_trace
    )
    print("Day 2 - Severity prediction:", severity_result)

    # --- Day 3a: RAG retrieval (real) ---
    rag = RAGRetriever()
    rag_hits = rag.retrieve(language=language, code=code, error=error, stack_trace=stack_trace, top_k=3)
    print(f"Day 3 - Retrieved {len(rag_hits)} similar known bugs, top match:", rag_hits[0])

    # --- Day 3b: LLM generation (mocked network call, real prompt/parsing logic) ---
    llm = CodingLLM(backend="ollama")
    with patch.object(llm, "_call_ollama", side_effect=mock_llm_call):
        llm_result = llm.generate(
            language=language,
            code=code,
            error=error,
            stack_trace=stack_trace,
            bug_type=bug_result["bug_type"],
            bug_confidence=bug_result["confidence"],
            severity=severity_result["severity"],
            rag_hits=rag_hits,
        )
    print("Day 3 - LLM output:", json.dumps(llm_result, indent=2))

    # --- Combine everything into the final report shape from the spec ---
    final_report = {
        "bug_type": bug_result["bug_type"],
        "severity": severity_result["severity"],
        "confidence": bug_result["confidence"],
        "root_cause": llm_result["root_cause"],
        "fix": llm_result["fix"],
        "corrected_code": llm_result["corrected_code"],
        "similar_known_bugs": rag_hits,
    }
    print("\n=== FINAL DEBUG REPORT ===")
    print(json.dumps(final_report, indent=2))
    return final_report


if __name__ == "__main__":
    run_pipeline()
