"""
severity.py  (DAY 2 deliverable — inference side)
----------------------------------------------------
Loads the trained severity model (models/severity_model/) and predicts
LOW / MEDIUM / HIGH / CRITICAL for a given bug, using the bug_type
predicted by the Day-1 classifier plus code/error/stack-trace signals.

Usage:
    from backend.ai.severity import SeverityPredictor
    sev = SeverityPredictor()
    result = sev.predict(bug_type="Type Error", code="...", error="...", stack_trace="")
    # -> {"severity": "MEDIUM", "confidence": 0.71}
"""

import os
import sys

import joblib
import numpy as np
import pandas as pd

# Make training/severity_features importable without turning it into a package.
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "training"))
from severity_features import extract_features, FEATURE_COLUMNS  # noqa: E402

MODEL_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models", "severity_model")


class SeverityPredictor:
    def __init__(self, model_dir: str = MODEL_DIR):
        self.model = joblib.load(os.path.join(model_dir, "severity_model.joblib"))
        self.encoder = joblib.load(os.path.join(model_dir, "label_encoder.joblib"))

    def predict(self, bug_type: str, code: str, error: str, stack_trace: str = ""):
        features = extract_features(bug_type, code, error, stack_trace)
        X = pd.DataFrame([[features[col] for col in FEATURE_COLUMNS]], columns=FEATURE_COLUMNS)

        pred_id = self.model.predict(X)[0]
        severity = self.encoder.inverse_transform([pred_id])[0]

        confidence = None
        if hasattr(self.model, "predict_proba"):
            proba = self.model.predict_proba(X)[0]
            confidence = round(float(np.max(proba)), 4)

        return {"severity": severity, "confidence": confidence}


if __name__ == "__main__":
    sev = SeverityPredictor()
    result = sev.predict(
        bug_type="Database Error",
        code="cursor.execute('SELECT * FROM users WHERE id = ' + user_id)",
        error="psycopg2.errors.SyntaxError: syntax error at or near ...",
        stack_trace="psycopg2.errors.SyntaxError: syntax error at or near",
    )
    print(result)
