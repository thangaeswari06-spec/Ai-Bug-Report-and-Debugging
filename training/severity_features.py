"""
severity_features.py  (DAY 2 deliverable)
-------------------------------------------
Builds the feature vector used by the severity model from a bug record.
Shared by train_severity.py (training) and backend/ai/severity.py (inference)
so both sides stay in sync.

Features used:
  - bug_type (one-hot encoded, comes from the Day-1 classifier's prediction)
  - code_length            : number of characters in the code snippet
  - error_length           : number of characters in the error message
  - has_stack_trace        : 1 if a stack trace is present, else 0
  - stack_trace_length     : number of characters in the stack trace
  - num_code_lines         : number of lines in the code snippet
  - mentions_security_kw   : 1 if error/code contains security-sensitive keywords
  - mentions_critical_kw   : 1 if error contains words like 'critical', 'fatal', 'crash'
  - mentions_db_kw         : 1 if error/code mentions database-related keywords
"""

import re

SECURITY_KEYWORDS = ["auth", "token", "password", "permission", "unauthorized", "security", "role", "access"]
CRITICAL_KEYWORDS = ["critical", "fatal", "crash", "corrupt", "data loss", "security breach"]
DB_KEYWORDS = ["sql", "query", "database", "connection", "psycopg2", "mysql", "mongodb"]

BUG_TYPES = [
    "Syntax Error",
    "Runtime Error",
    "Logic Error",
    "Type Error",
    "Import/Dependency Error",
    "API Error",
    "Database Error",
    "Authentication Error",
    "Configuration Error",
    "Performance Error",
]


def _contains_any(text: str, keywords) -> int:
    text = (text or "").lower()
    return int(any(kw in text for kw in keywords))


def extract_features(bug_type: str, code: str, error: str, stack_trace: str = "") -> dict:
    """Returns a flat dict of numeric/one-hot features for one bug record."""
    code = code or ""
    error = error or ""
    stack_trace = stack_trace or ""
    combined = f"{code}\n{error}\n{stack_trace}"

    features = {
        "code_length": len(code),
        "error_length": len(error),
        "has_stack_trace": int(bool(stack_trace.strip())),
        "stack_trace_length": len(stack_trace),
        "num_code_lines": len(code.splitlines()) if code else 0,
        "mentions_security_kw": _contains_any(combined, SECURITY_KEYWORDS),
        "mentions_critical_kw": _contains_any(combined, CRITICAL_KEYWORDS),
        "mentions_db_kw": _contains_any(combined, DB_KEYWORDS),
    }

    # One-hot encode bug_type using the fixed BUG_TYPES order so training and
    # inference always produce vectors of the same length/order.
    for bt in BUG_TYPES:
        features[f"bug_type_{re.sub(r'[^a-zA-Z]', '_', bt)}"] = int(bug_type == bt)

    return features


FEATURE_COLUMNS = list(
    extract_features("Syntax Error", "x", "y", "").keys()
)
