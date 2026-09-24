"""
rag.py  (DAY 3 deliverable)
------------------------------
Embeds the knowledge base and retrieves the most similar known bugs/fixes
for a given (language, code, error, stack_trace) query.

Embedding choice: TF-IDF (scikit-learn) + cosine similarity.
  - Runs fully offline, no model download needed.
  - Good enough for short code/error text matching.
  - DROP-IN UPGRADE for production: replace `_vectorize()` with
    sentence-transformers embeddings (e.g. 'all-MiniLM-L6-v2') and swap
    the in-memory matrix for a FAISS or Chroma index — the retrieve()
    interface below stays identical, so nothing else in the pipeline
    needs to change.

Usage:
    from backend.ai.rag import RAGRetriever
    rag = RAGRetriever()
    hits = rag.retrieve(language="python", code="...", error="...", top_k=3)
    # -> [{"kb_id": "...", "bug_type": "...", "root_cause": "...", "fix": "...", "score": 0.83}, ...]
"""

import json
import os

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

KB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "knowledge_base.json")
INDEX_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "models", "rag_index")
VECTORIZER_PATH = os.path.join(INDEX_DIR, "tfidf_vectorizer.joblib")
MATRIX_PATH = os.path.join(INDEX_DIR, "tfidf_matrix.joblib")


def _entry_text(entry: dict) -> str:
    """Text used for embedding each knowledge-base entry."""
    return (
        f"{entry['bug_type']}\n"
        f"{entry['example_code']}\n"
        f"{entry['error_pattern']}\n"
        f"{entry.get('stack_trace', '')}"
    )


def _query_text(language: str, code: str, error: str, stack_trace: str = "") -> str:
    return f"{language}\n{code}\n{error}\n{stack_trace}"


class RAGRetriever:
    def __init__(self, kb_path: str = KB_PATH, index_dir: str = INDEX_DIR):
        self.kb_path = kb_path
        self.index_dir = index_dir
        with open(kb_path, encoding="utf-8") as f:
            self.knowledge_base = json.load(f)

        os.makedirs(index_dir, exist_ok=True)
        vec_path = os.path.join(index_dir, "tfidf_vectorizer.joblib")
        mat_path = os.path.join(index_dir, "tfidf_matrix.joblib")

        if os.path.exists(vec_path) and os.path.exists(mat_path):
            self.vectorizer = joblib.load(vec_path)
            self.matrix = joblib.load(mat_path)
        else:
            self.vectorizer, self.matrix = self._build_index()
            joblib.dump(self.vectorizer, vec_path)
            joblib.dump(self.matrix, mat_path)

    def _build_index(self):
        texts = [_entry_text(e) for e in self.knowledge_base]
        vectorizer = TfidfVectorizer(
            lowercase=True,
            token_pattern=r"(?u)\b\w[\w\.\-']*\b",  # keep tokens like "requests.get", "TypeError"
            max_features=5000,
        )
        matrix = vectorizer.fit_transform(texts)
        return vectorizer, matrix

    def rebuild_index(self):
        """Call this after knowledge_base.json changes (e.g. new bugs/fixes added)."""
        self.vectorizer, self.matrix = self._build_index()
        joblib.dump(self.vectorizer, VECTORIZER_PATH)
        joblib.dump(self.matrix, MATRIX_PATH)

    def retrieve(self, language: str, code: str, error: str, stack_trace: str = "", top_k: int = 3):
        query = _query_text(language, code, error, stack_trace)
        query_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(query_vec, self.matrix)[0]

        ranked_idx = sims.argsort()[::-1][:top_k]
        results = []
        for idx in ranked_idx:
            entry = self.knowledge_base[idx]
            results.append(
                {
                    "kb_id": entry["kb_id"],
                    "language": entry["language"],
                    "bug_type": entry["bug_type"],
                    "error_pattern": entry["error_pattern"],
                    "root_cause": entry["root_cause"],
                    "fix": entry["fix"],
                    "score": round(float(sims[idx]), 4),
                }
            )
        return results


if __name__ == "__main__":
    rag = RAGRetriever()
    hits = rag.retrieve(
        language="python",
        code="cursor.execute('SELECT * FROM users WHERE id = ' + user_id)",
        error="psycopg2.errors.SyntaxError: syntax error at or near",
        top_k=3,
    )
    for h in hits:
        print(h)
