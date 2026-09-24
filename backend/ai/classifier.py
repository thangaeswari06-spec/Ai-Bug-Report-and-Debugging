"""
classifier.py  (DAY 1 deliverable — inference side)
-----------------------------------------------------
Loads the fine-tuned CodeBERT bug-type classifier saved under
models/bug_classifier/ and exposes a simple predict() function that the
FastAPI backend (Day 4) will call.

Usage:
    from backend.ai.classifier import BugClassifier
    clf = BugClassifier()
    result = clf.predict(language="python", code="...", error="...", stack_trace="")
    # -> {"bug_type": "Type Error", "confidence": 0.94}
"""

import json
import os

try:
    from transformers import pipeline
except ImportError:
    pipeline = None  # transformers not installed yet — MockBugClassifier still works without it

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models", "bug_classifier")


class MockBugClassifier:
    """
    Keyword-based stand-in for the trained CodeBERT classifier, used
    automatically when models/bug_classifier/ hasn't been trained yet
    (e.g. this sandbox, or a fresh clone before you run
    training/train_classifier.py). Lets the rest of the pipeline
    (severity, RAG, LLM, validator, API) be built and tested without
    waiting on GPU/Hugging-Face access. Swap for BugClassifier once you
    have run Day 1 training locally.
    """

    RULES = [
        ("Syntax Error", ["syntaxerror", "expected ':'", "missing )", "unexpected token", "expected ';'", "parse error",
                          "error: expected", "syntax error, unexpected", "expected `;`", "expected one of", "cs1002", "cs1525"]),
        ("Import/Dependency Error", ["modulenotfounderror", "cannot resolve", "no module named", "cannot find module",
                                    "undefined reference", "fatal error: no such file", "cannot find package",
                                    "unresolved import", "cs0246", "class not found", "failed to open stream"]),
        ("Database Error", ["psycopg2", "operationalerror", "sql", "database", "connection refused"]),
        ("Authentication Error", ["401", "unauthorized", "token", "permission", "auth"]),
        ("API Error", ["failed to fetch", "jsondecodeerror", "requests.exceptions", "cors", "status code"]),
        ("Configuration Error", ["keyerror: 'debug'", "environ", "config", "environment variable"]),
        ("Performance Error", ["seconds", "slow", "full table scan", "o(n"]),
        ("Type Error", ["typeerror", "mismatched types", "cannot use", "incompatible types", "cs0029", "cannot convert",
                        "invalid conversion", "is not assignable to type"]),
        ("Runtime Error", ["indexerror", "zerodivisionerror", "nullpointerexception", "cannot read propert",
                           "segmentation fault", "nil pointer dereference", "index out of range", "panicked at",
                           "attempt to divide by zero", "undefined array key", "nullreferenceexception",
                           "stack smashing", "core dumped", "std::out_of_range", "division by zero"]),
    ]

    def predict(self, language: str, code: str, error: str, stack_trace: str = ""):
        text = f"{code}\n{error}\n{stack_trace}".lower()
        for bug_type, keywords in self.RULES:
            if any(kw in text for kw in keywords):
                return {"bug_type": bug_type, "confidence": 0.75, "all_scores": {bug_type: 0.75}}
        return {"bug_type": "Logic Error", "confidence": 0.5, "all_scores": {"Logic Error": 0.5}}


def is_trained_model_available(model_dir: str = MODEL_DIR) -> bool:
    return os.path.exists(os.path.join(model_dir, "config.json"))


def get_classifier():
    """Factory used by the API layer: real classifier if trained, mock otherwise."""
    if is_trained_model_available():
        return BugClassifier()
    return MockBugClassifier()


class BugClassifier:
    def __init__(self, model_dir: str = MODEL_DIR):
        self.model_dir = model_dir
        label_map_path = os.path.join(model_dir, "label_map.json")
        if os.path.exists(label_map_path):
            with open(label_map_path) as f:
                self.label_map = json.load(f)
        else:
            self.label_map = None

        # Uses the same Hugging Face pipeline mentioned in the project spec:
        # pipeline('text-classification', ...)
        self.pipe = pipeline(
            "text-classification",
            model=self.model_dir,
            tokenizer=self.model_dir,
            top_k=None,  # return scores for all classes so we can expose confidence
        )

    def _build_input_text(self, language, code, error, stack_trace=""):
        stack = f"\nStack trace: {stack_trace}" if stack_trace else ""
        return f"Language: {language}\nCode:\n{code}\nError: {error}{stack}"

    def predict(self, language: str, code: str, error: str, stack_trace: str = ""):
        text = self._build_input_text(language, code, error, stack_trace)
        results = self.pipe(text, truncation=True, max_length=256)[0]
        best = max(results, key=lambda r: r["score"])
        return {
            "bug_type": best["label"],
            "confidence": round(float(best["score"]), 4),
            "all_scores": {r["label"]: round(float(r["score"]), 4) for r in results},
        }


if __name__ == "__main__":
    # Quick manual test once a model has been trained.
    clf = BugClassifier()
    sample = clf.predict(
        language="python",
        code="age = '25'\nnext_year = age + 1",
        error="TypeError: can only concatenate str (not \"int\") to str",
    )
    print(sample)
