"""
build_knowledge_base.py  (DAY 3 deliverable)
-----------------------------------------------
Creates data/knowledge_base.json — the "known bugs and fixes" RAG corpus
described in the project plan:

    "Create a knowledge base containing language, bug type, error pattern,
     root cause, fix and example."

This dedupes data/bugs.csv down to unique (bug_type, error) templates so
the knowledge base holds one clean entry per known bug pattern instead of
hundreds of near-duplicate training rows.

Usage:
    python data/build_knowledge_base.py
"""

import json
import os

import pandas as pd

DATA_DIR = os.path.dirname(__file__)
BUGS_CSV = os.path.join(DATA_DIR, "bugs.csv")
OUT_PATH = os.path.join(DATA_DIR, "knowledge_base.json")


def main():
    df = pd.read_csv(BUGS_CSV)
    df["stack_trace"] = df["stack_trace"].fillna("")

    # One canonical entry per (bug_type, error) pattern — code/root_cause/fix
    # are identical across duplicates in the synthetic dataset, so keep the
    # first occurrence of each.
    deduped = df.drop_duplicates(subset=["bug_type", "error"]).reset_index(drop=True)

    kb = []
    for i, row in deduped.iterrows():
        kb.append(
            {
                "kb_id": f"kb_{i + 1:03d}",
                "language": row["language"],
                "bug_type": row["bug_type"],
                "error_pattern": row["error"],
                "example_code": row["code"],
                "stack_trace": row["stack_trace"],
                "root_cause": row["root_cause"],
                "fix": row["fix"],
            }
        )

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(kb, f, indent=2)

    print(f"Wrote {len(kb)} knowledge-base entries -> {OUT_PATH}")
    by_type = {}
    for e in kb:
        by_type[e["bug_type"]] = by_type.get(e["bug_type"], 0) + 1
    for k, v in by_type.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
