"""
generate_dataset.py
--------------------
Creates data/bugs.csv — a synthetic but realistic dataset used to train:
  1) The CodeBERT bug-type classifier (Day 1)
  2) The severity model (Day 2)

Real-world project-ல, indha file-ku pathila neenga real bug reports
(GitHub issues, Jira exports, StackOverflow Q&A) collect pannalam.
Ippo demo/training purpose-ku, template-based synthetic data generate pannurom
so the pipeline (classifier + severity model) end-to-end test panna mudiyum.

Columns: id, language, code, error, stack_trace, bug_type, severity, root_cause, fix
"""

import csv
import random
import os

random.seed(42)

LANGUAGES = ["python", "javascript", "typescript", "java"]

# Each bug type -> list of (code, error, stack_trace, root_cause, fix, severity_bias)
# severity_bias = list of severities that are realistic for this template
BUG_TEMPLATES = {
    "Syntax Error": [
        (
            "def add(a, b)\n    return a + b",
            "SyntaxError: expected ':'",
            'File "main.py", line 1\n    def add(a, b)\nSyntaxError: expected \':\'',
            "Missing colon at the end of the function definition line.",
            "Add a colon after the function signature: def add(a, b):",
            ["LOW", "MEDIUM"],
        ),
        (
            "if (x > 5 {\n  console.log('big');\n}",
            "SyntaxError: missing ) after condition",
            "SyntaxError: missing ) after condition\n    at Object.compileFunction",
            "The if-condition is missing a closing parenthesis.",
            "Close the condition properly: if (x > 5) {",
            ["LOW", "MEDIUM"],
        ),
        (
            "for i in range(10)\n    print(i)",
            "SyntaxError: expected ':'",
            'File "loop.py", line 1\nSyntaxError: expected \':\'',
            "The for-loop header is missing a trailing colon.",
            "Add a colon: for i in range(10):",
            ["LOW"],
        ),
    ],
    "Runtime Error": [
        (
            "arr = [1, 2, 3]\nprint(arr[5])",
            "IndexError: list index out of range",
            'File "main.py", line 2, in <module>\n    print(arr[5])\nIndexError: list index out of range',
            "Accessing an index beyond the length of the list.",
            "Add a bounds check before indexing, e.g. if len(arr) > 5.",
            ["MEDIUM", "HIGH"],
        ),
        (
            "x = 10\ny = 0\nprint(x / y)",
            "ZeroDivisionError: division by zero",
            'File "main.py", line 3, in <module>\n    print(x / y)\nZeroDivisionError: division by zero',
            "Dividing a number by a variable that is zero at runtime.",
            "Check the denominator for zero before dividing.",
            ["MEDIUM", "HIGH"],
        ),
        (
            "obj = None\nobj.doSomething();",
            "TypeError: Cannot read properties of null (reading 'doSomething')",
            "TypeError: Cannot read properties of null\n    at Object.<anonymous>",
            "Calling a method on a null/undefined object reference.",
            "Add a null check before calling obj.doSomething().",
            ["HIGH", "CRITICAL"],
        ),
    ],
    "Logic Error": [
        (
            "def is_even(n):\n    return n % 2 == 1",
            "No exception, but is_even(4) returns False incorrectly",
            "",
            "The modulo condition is inverted; it checks for odd instead of even.",
            "Change the condition to n % 2 == 0.",
            ["LOW", "MEDIUM"],
        ),
        (
            "total = 0\nfor i in range(1, 10):\n    total += i\nprint(total)",
            "Output is 45 but expected sum 1..10 is 55",
            "",
            "range(1, 10) excludes 10, so the loop stops one short.",
            "Use range(1, 11) to include 10 in the sum.",
            ["LOW", "MEDIUM"],
        ),
        (
            "function isAdult(age) {\n  return age > 18;\n}",
            "isAdult(18) returns false but should return true",
            "",
            "Boundary condition uses '>' instead of '>=' for age 18.",
            "Change the comparison to age >= 18.",
            ["MEDIUM"],
        ),
    ],
    "Type Error": [
        (
            "age = '25'\nnext_year = age + 1",
            "TypeError: can only concatenate str (not \"int\") to str",
            'File "main.py", line 2, in <module>\nTypeError: can only concatenate str (not "int") to str',
            "String value used in a numeric operation without conversion.",
            "Convert the input to an integer: next_year = int(age) + 1.",
            ["LOW", "MEDIUM"],
        ),
        (
            "let total = '5' * 'a';",
            "Result is NaN instead of throwing, causing downstream failures",
            "",
            "Multiplying a numeric string by a non-numeric string yields NaN silently.",
            "Validate and parse inputs with Number() before arithmetic.",
            ["MEDIUM", "HIGH"],
        ),
    ],
    "Import/Dependency Error": [
        (
            "import pandas as pd\ndf = pd.read_csv('data.csv')",
            "ModuleNotFoundError: No module named 'pandas'",
            'File "main.py", line 1, in <module>\nModuleNotFoundError: No module named \'pandas\'',
            "The pandas package is not installed in the current environment.",
            "Run: pip install pandas, or add it to requirements.txt.",
            ["LOW", "MEDIUM"],
        ),
        (
            "import { useState } from 'react';",
            "Module not found: Error: Can't resolve 'react'",
            "Module not found: Error: Can't resolve 'react' in '/src'",
            "The react package is missing from node_modules.",
            "Run: npm install react react-dom.",
            ["MEDIUM", "HIGH"],
        ),
    ],
    "API Error": [
        (
            "response = requests.get('https://api.example.com/data')\nprint(response.json())",
            "requests.exceptions.JSONDecodeError: Expecting value",
            'File "main.py", line 2, in <module>\nJSONDecodeError: Expecting value',
            "The API returned a non-JSON (e.g. HTML error) response, likely due to a bad endpoint or auth failure.",
            "Check response.status_code before parsing, and verify the endpoint/auth.",
            ["MEDIUM", "HIGH"],
        ),
        (
            "fetch('/api/users').then(r => r.json())",
            "TypeError: Failed to fetch",
            "TypeError: Failed to fetch\n    at fetchUsers",
            "The API endpoint is unreachable, possibly due to CORS or the server being down.",
            "Verify the server is running and CORS headers are correctly configured.",
            ["HIGH", "CRITICAL"],
        ),
    ],
    "Database Error": [
        (
            "cursor.execute('SELECT * FROM users WHERE id = ' + user_id)",
            "psycopg2.errors.SyntaxError: syntax error at or near ...",
            "psycopg2.errors.SyntaxError: syntax error at or near",
            "Unsanitized string concatenation used to build the SQL query.",
            "Use parameterized queries: cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,)).",
            ["HIGH", "CRITICAL"],
        ),
        (
            "conn = psycopg2.connect(host='localhost', dbname='app')",
            "OperationalError: could not connect to server",
            "OperationalError: could not connect to server: Connection refused",
            "The database server is not running or the connection details are wrong.",
            "Confirm the DB service is running and connection parameters are correct.",
            ["HIGH", "CRITICAL"],
        ),
    ],
    "Authentication Error": [
        (
            "headers = {'Authorization': f'Bearer {token}'}\nresp = requests.get(url, headers=headers)",
            "401 Unauthorized: Invalid or expired token",
            "",
            "The auth token is missing, malformed, or has expired.",
            "Refresh the token before the request and handle 401 by re-authenticating.",
            ["MEDIUM", "HIGH"],
        ),
        (
            "if (user.role === 'admin') { grantAccess(); }",
            "Unauthorized users are able to access admin routes",
            "",
            "Role check is done only on the client; the server does not verify it.",
            "Enforce role-based access control on the server/API layer as well.",
            ["CRITICAL"],
        ),
    ],
    "Configuration Error": [
        (
            "DEBUG = os.environ['DEBUG']",
            "KeyError: 'DEBUG'",
            'File "settings.py", line 1, in <module>\nKeyError: \'DEBUG\'',
            "Required environment variable DEBUG is not set.",
            "Use os.environ.get('DEBUG', 'False') with a sane default.",
            ["LOW", "MEDIUM"],
        ),
        (
            "DATABASE_URL = 'postgres://localhost/dev_db'",
            "Production app fails: connects to dev database instead of prod",
            "",
            "Hard-coded configuration value not overridden per environment.",
            "Load DATABASE_URL from environment-specific config/secret manager.",
            ["HIGH", "CRITICAL"],
        ),
    ],
    "Performance Error": [
        (
            "for item in large_list:\n    if item in another_large_list:\n        process(item)",
            "No crash, but function takes 40+ seconds for 100k items",
            "",
            "Using 'in' on a list results in O(n) lookup, causing O(n*m) overall complexity.",
            "Convert another_large_list to a set for O(1) average lookup time.",
            ["MEDIUM", "HIGH"],
        ),
        (
            "SELECT * FROM orders WHERE customer_id = 123",
            "Query takes 8 seconds on a 10M row table",
            "",
            "Missing index on the customer_id column causes a full table scan.",
            "Add an index: CREATE INDEX idx_orders_customer_id ON orders(customer_id).",
            ["MEDIUM", "HIGH"],
        ),
    ],
}

SEVERITY_ORDER = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]


def build_rows(samples_per_template=15):
    rows = []
    idx = 1
    for bug_type, templates in BUG_TEMPLATES.items():
        for code, error, stack_trace, root_cause, fix, sev_options in templates:
            for _ in range(samples_per_template):
                language = random.choice(LANGUAGES)
                severity = random.choice(sev_options)
                rows.append(
                    {
                        "id": idx,
                        "language": language,
                        "code": code,
                        "error": error,
                        "stack_trace": stack_trace,
                        "bug_type": bug_type,
                        "severity": severity,
                        "root_cause": root_cause,
                        "fix": fix,
                    }
                )
                idx += 1
    random.shuffle(rows)
    for i, r in enumerate(rows, start=1):
        r["id"] = i
    return rows


def main():
    out_path = os.path.join(os.path.dirname(__file__), "bugs.csv")
    rows = build_rows(samples_per_template=15)
    fieldnames = ["id", "language", "code", "error", "stack_trace", "bug_type", "severity", "root_cause", "fix"]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} rows -> {out_path}")
    print("Bug type distribution:")
    counts = {}
    for r in rows:
        counts[r["bug_type"]] = counts.get(r["bug_type"], 0) + 1
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
