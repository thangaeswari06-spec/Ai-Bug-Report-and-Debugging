# AI BugFixer — v2 (accounts, error-line finder, screenshot OCR, practice arena)

## What's new in v2

| Feature | Where |
|---|---|
| **Sign-in required** for the whole app (email + password, or **Continue with Google**) | `backend/routes/auth.py`, `frontend/src/pages/AuthPage.jsx` |
| **Exact error line + reason** — highlighted in your code with a "why" note under each line | `backend/ai/locator.py`, `frontend/src/components/CodeView.jsx` |
| **Error screenshot upload** → OCR → fills the error box (dark-theme screenshots handled) | `backend/ai/ocr.py`, `frontend/src/components/ImageDropzone.jsx` |
| **10 languages**: Python, JavaScript, TypeScript, Java, C, C++, C#, Go, Rust, PHP | `backend/utils/languages.py`, `backend/ai/validator.py` |
| **Practice arena**: 10 problems, run against examples, submit against hidden tests, "Ask AI BugFixer" on failure | `backend/practice/`, `frontend/src/pages/Practice*.jsx` |
| **Profile picture, Settings page, History page (separate), bell notifications, Log out** in the profile menu | `frontend/src/components/Navbar.jsx` etc. |
| **Advanced CSS** design system (aurora background, glass, animated gradient borders, `@property`, container queries…) | `frontend/src/index.css` |

## Run it

```bash
# 1. backend
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000

# 2. frontend (new terminal)
cd frontend && npm install && npm run dev            # http://localhost:5173
```

The first time you open the site you are sent to **/login** — create an account and you're in.

### Continue with Google (needs your own Client ID — 3 minutes)
1. <https://console.cloud.google.com/apis/credentials> → **Create credentials → OAuth client ID → Web application**.
2. Under **Authorized JavaScript origins** add `http://localhost:5173` (and your real domain later).
3. Start the backend with the id: `GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com uvicorn backend.main:app --reload`
   (Windows PowerShell: `$env:GOOGLE_CLIENT_ID="xxxx"; uvicorn backend.main:app --reload`).

The frontend reads the id from the backend, so you configure it in **one** place. Until it is set the Google button is shown greyed-out with a hint. The server verifies Google's signed ID token itself — the browser is never trusted.
(I could not test the live Google round-trip here because it needs your real Client ID; the "not configured" path and the server-side checks are tested.)

### Screenshot OCR needs the Tesseract engine
Windows: <https://github.com/UB-Mannheim/tesseract/wiki> (tick "add to PATH") · macOS: `brew install tesseract` · Ubuntu: `sudo apt install tesseract-ocr`.
Without it the upload shows a clear "Tesseract is not installed" message; everything else keeps working.

### Practice arena: which languages can actually run?
The server needs each language's compiler/runtime on `PATH`. Missing ones are greyed out in the UI (you can still use them in the Debugger).

| Language | Needs |
|---|---|
| Python / JavaScript / PHP | `python3`, `node`, `php` |
| TypeScript | Node **22.6+** (runs `.ts` directly); the debugger's type check also uses `tsc` if installed |
| C / C++ | `gcc` / `g++` |
| Java | a **JDK** (`javac` + `java`), not just a JRE |
| Go / Rust | `go` / `rustc` |
| C# | `dotnet` SDK, or Mono (`mcs` + `mono`) |

### Error-line detection — how it works
Four signals are merged and clamped to your real code length: the **AI's** own `error_lines`, line numbers parsed from the **stack trace / error message** (per-language formats; innermost frame = "raised here", outer frames = "call path"), a **compiler/parser pass** over your original code, and a **diff** against the fix. Missing-semicolon errors are moved to the line *before* the one the compiler reports.
With `LLM_BACKEND=mock` (default) the fix text comes from the knowledge base, but line detection still works because it does not depend on the LLM. Set `LLM_BACKEND=ollama` or `api` for real generated fixes.

## Security — what is and isn't covered

Done: PBKDF2-SHA256 salted password hashing (390k rounds) · password policy · signed JWT sessions that expire (12 h) and are checked against the DB on every request · login lockout (5 wrong tries → 10 min) and per-IP rate limits · same error for unknown email vs wrong password (no account enumeration) · every history / notification / progress query is scoped to the signed-in user · uploads validated by real image decoding, size-limited and **re-encoded** (avatars) · request-size and field-length limits · CORS locked to your frontend origin · security headers · hidden practice tests never sent to the browser · Google ID tokens verified server-side.

Know before deploying publicly:
- **The practice runner is not a full sandbox.** It uses a temp dir, timeouts, CPU/memory/file limits and a clean environment, but submitted code could still use the network or read files the server user can read. For a public site, run it in Docker/gVisor or use Judge0/Piston.
- The login token is kept in `localStorage` (simple, but readable by any XSS bug). For production consider an `HttpOnly` cookie + CSRF protection.
- Rate limits and lockout counters that live in memory reset on restart and are per-process; use Redis if you run several workers.
- Serve over HTTPS and set a real `SECRET_KEY` (see `.env.example`).
- SQLite (`data/bugfixer.db`) is fine for a project; move to Postgres for scale.

## Tests
```bash
pytest tests -q        # auth, lockout, isolation, OCR, error lines, practice runner
```
Practice execution was tested for Python, JavaScript, TypeScript, C and C++ (the toolchains available where this was built). Java / C# / Go / Rust / PHP starter templates and runner commands are written but **not executed in tests** — please try one solution in each language you care about.

---

# Original project notes (Days 1–5)

# AI BugFixer — Full 5-Day Project (Finished)

Complete project: Day 1 (Bug Classifier) → Day 2 (Severity Model) →
Day 3 (RAG + Coding LLM) → Day 4 (Validator + FastAPI) → Day 5 (React +
Tailwind frontend). Everything below Day 1's CodeBERT download has been
**actually run and tested** in this environment — backend server started,
`/analyze` and `/history` endpoints hit with real requests, frontend built
and served, and the full pipeline verified end-to-end.

## Setup

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Step 0 — Generate the dataset

Real dataset illama irundhalum pipeline test panna oru synthetic
dataset generate pannurom (345 rows, 10 bug types, 4 severities):

```bash
python data/generate_dataset.py
```

This creates `data/bugs.csv`. **Production-ku neenga idha real bug
reports/GitHub issues vechi replace pannunga** — code structure ellam
same-ah irukkum, samples mattum kootunga.

## Day 1 — Bug-Type Classifier (CodeBERT)

```bash
python training/train_classifier.py --epochs 5 --batch_size 8
```

- Fine-tunes `microsoft/codebert-base` on the (language + code + error +
  stack trace) text, 10 bug-type labels.
- 70/15/15 train/val/test split, stratified.
- Reports Accuracy, Precision, Recall, Macro-F1, confusion matrix on the
  held-out test set.
- Saves model + tokenizer + `label_map.json` + `test_metrics.json` to
  `models/bug_classifier/`.

**Note:** this step needs internet access to `huggingface.co` to
download the pretrained CodeBERT weights the first time — run it on
your own machine (this sandbox's network doesn't allow that domain, so
I verified the script's syntax/logic but couldn't execute the download
here).

Inference wrapper: `backend/ai/classifier.py` — uses
`pipeline('text-classification', ...)` exactly as the project spec
describes, loads the saved model, and returns `{bug_type, confidence,
all_scores}`.

## Day 2 — Severity Model + Evaluation

```bash
python training/train_severity.py --model rf     # Random Forest (default)
python training/train_severity.py --model xgb    # or XGBoost
```

This one is **fully tested and working** in this environment (no
external downloads needed).

Features (`training/severity_features.py`):
- predicted `bug_type` (one-hot)
- code length, error length, number of code lines
- stack-trace presence + length
- keyword signals: security/auth, critical/fatal, database-related

Model: RandomForestClassifier (class-balanced) or XGBClassifier.

Outputs saved to `models/severity_model/`:
- `severity_model.joblib`, `label_encoder.joblib`
- `metrics.json` — accuracy, macro precision/recall/F1, confusion matrix
- `confusion_matrix.png` — visual confusion matrix

Sample run on the synthetic dataset (RF):

```
Accuracy: 0.54   Macro F1: 0.51
```

(Numbers are modest because the synthetic dataset assigns severity
somewhat randomly within each bug template — with a real dataset the
signal will be much stronger. Pipeline/code correctness is what Day 1–2
are meant to prove.)

Inference wrapper: `backend/ai/severity.py` — takes the Day-1
classifier's `bug_type` output + the code/error/stack trace, returns
`{severity, confidence}`.

## Quick pipeline test (Day 1 → Day 2 chained)

Once you've trained the classifier locally:

```python
from backend.ai.classifier import BugClassifier
from backend.ai.severity import SeverityPredictor

clf = BugClassifier()
sev = SeverityPredictor()

code = "cursor.execute('SELECT * FROM users WHERE id = ' + user_id)"
error = "psycopg2.errors.SyntaxError: syntax error at or near ..."

bug_result = clf.predict(language="python", code=code, error=error)
sev_result = sev.predict(bug_type=bug_result["bug_type"], code=code, error=error)

print(bug_result)   # {'bug_type': 'Database Error', 'confidence': 0.94, ...}
print(sev_result)   # {'severity': 'CRITICAL', 'confidence': 0.71}
```

## Day 3 — RAG Knowledge Base + Coding LLM

**Fully tested and working in this environment** (retrieval + prompt-building
+ JSON parsing). Only the live LLM network call itself is mocked, since this
sandbox has no access to Ollama/hosted LLM APIs — the code is correct and
ready to run wherever you have one of those set up.

### Step 1 — Build the knowledge base

```bash
python data/build_knowledge_base.py
```

Dedupes `data/bugs.csv` down to 22 unique known bug/fix entries and writes
`data/knowledge_base.json` with fields: `language, bug_type, error_pattern,
example_code, stack_trace, root_cause, fix`.

### Step 2 — RAG retrieval (`backend/ai/rag.py`)

- Embeds the knowledge base with **TF-IDF** (scikit-learn) — chosen so it
  runs fully offline with no model download. The `retrieve()` interface is
  designed as a drop-in: swap `_build_index()` for sentence-transformers
  embeddings and the in-memory matrix for FAISS/Chroma later without
  touching any calling code.
- Index is cached to `models/rag_index/` after the first build.
- Test it directly:
  ```bash
  python -m backend.ai.rag
  ```

### Step 3 — Coding LLM (`backend/ai/llm.py`)

- `build_prompt()` combines the original bug + Day-1 classifier output +
  Day-2 severity output + Day-3 RAG hits into one prompt, and asks the LLM
  to return **only JSON**: `root_cause, explanation, fix, corrected_code`.
- Two backends, switchable via env vars:
  - `LLM_BACKEND=ollama` (default) → calls a local model via
    `OLLAMA_URL` / `OLLAMA_MODEL` (e.g. `qwen2.5-coder:7b`, `codellama`).
  - `LLM_BACKEND=api` → calls any OpenAI-compatible chat endpoint via
    `LLM_API_URL`, `LLM_API_KEY`, `LLM_API_MODEL`.
- `_extract_json()` safely strips markdown fences / stray text if the LLM
  doesn't return pure JSON, with a bounded fallback so the app never
  crashes on a bad LLM response.

### Step 4 — Full pipeline test (Day 1→2→3 chained)

```bash
python -m tests.test_day3_pipeline
```

This chains: mocked Day-1 classifier → **real** Day-2 severity model →
**real** Day-3 RAG retrieval → mocked LLM call → final combined debug
report, in the exact shape the spec's example API response uses:

```json
{
  "bug_type": "Database Error",
  "severity": "CRITICAL",
  "confidence": 0.94,
  "root_cause": "...",
  "fix": "...",
  "corrected_code": "...",
  "similar_known_bugs": [...]
}
```

To go live: set up Ollama (`ollama pull qwen2.5-coder:7b`) or an API key,
then in `test_day3_pipeline.py` remove the `patch.object(...)` mock and
call `llm.generate(...)` directly — everything else is unchanged.

## Day 4 — Validator + FastAPI Backend

**Tested live**: server started with uvicorn, `/health`, `/analyze` and
`/history` endpoints hit with real HTTP requests and returned correct
results.

- `backend/ai/validator.py` — Python via `ast.parse()` (exactly as spec'd),
  JS/TS via `node --check`, other languages via a bracket-balance
  fallback. Never crashes the API even on unsupported input.
- `backend/routes/analyze.py` — `POST /analyze`. Runs classifier → severity
  → RAG → LLM → validator, and if validation fails, does **one bounded
  retry** (asks the LLM again with the validation error attached) before
  giving up and returning the failure — exactly the spec's rule.
- `backend/routes/history.py` — `GET /history`, `GET /history/{id}`,
  `DELETE /history`, backed by a simple `data/history.json` file.
- `backend/main.py` — FastAPI app, CORS enabled for the Vite dev server.
- **Mock modes so the API works before Day 1 finishes training:**
  `get_classifier()` in `classifier.py` auto-falls-back to a keyword-based
  `MockBugClassifier` if `models/bug_classifier/` isn't trained yet, and
  `LLM_BACKEND=mock` (the default) returns the best-matching RAG entry's
  fix instead of calling a real LLM. Switch both off once Day 1 is
  trained and `LLM_BACKEND=ollama`/`api` is configured.

### Run the backend

```bash
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Interactive API docs: http://localhost:8000/docs

## Day 5 — React + Tailwind Frontend

**Built and served live** in this environment: `npm install`, `npm run
build` (clean build, no errors), and `npm run dev` all verified working.

Stack: Vite + React 19 + Tailwind CSS v4 + React Router + Axios + lucide-react icons.

```
frontend/src/
├── pages/
│   ├── DebuggerPage.jsx   # language select, code/error/stack-trace inputs, Analyze Bug button
│   └── HistoryPage.jsx    # past analyses, expandable, Clear all
├── components/
│   ├── Navbar.jsx
│   ├── ResultCard.jsx     # bug type, severity, root cause, fix, corrected code, validation,
│   │                      # similar known bugs, Copy Code + Download Report buttons
│   └── SeverityBadge.jsx
└── services/api.js        # analyzeBug(), fetchHistory(), fetchHistoryItem(), clearHistory()
```

### Run the frontend

```bash
cd frontend
npm install
npm run dev
```

Opens at http://localhost:5173 — make sure the FastAPI backend (above) is
running on port 8000 first, since the frontend calls it directly.

### Full end-to-end flow (matches the spec's Final Demonstration Flow)

1. Start the backend (`uvicorn backend.main:app --reload --port 8000`).
2. Start the frontend (`npm run dev` inside `frontend/`).
3. Open http://localhost:5173, click **"Load sample bug"**, then **"Analyze Bug"**.
4. See predicted bug type + severity, similar known bug, root cause,
   recommended fix, corrected code, and validation result — all in one card.
5. Visit the **History** page to see it saved and re-expandable.

## Project structure (full project)

```
AI-BugFixer/
├── data/
│   ├── generate_dataset.py
│   ├── build_knowledge_base.py   # Day 3
│   ├── bugs.csv
│   ├── knowledge_base.json       # Day 3
│   └── history.json              # created at runtime by /analyze
├── training/
│   ├── train_classifier.py       # Day 1
│   ├── severity_features.py      # Day 2
│   └── train_severity.py         # Day 2
├── backend/
│   ├── main.py                   # Day 4 — FastAPI app
│   ├── routes/
│   │   ├── analyze.py            # Day 4 — POST /analyze
│   │   └── history.py            # Day 4 — GET/DELETE /history
│   ├── utils/
│   │   └── schemas.py            # Day 4 — pydantic request/response models
│   └── ai/
│       ├── classifier.py         # Day 1 inference (+ mock fallback)
│       ├── severity.py           # Day 2 inference
│       ├── rag.py                # Day 3 retrieval
│       ├── llm.py                # Day 3 generation (+ mock/ollama/api backends)
│       └── validator.py          # Day 4 validation
├── models/
│   ├── bug_classifier/           # created after Day-1 training
│   ├── severity_model/           # already trained
│   └── rag_index/                # already built (TF-IDF index)
├── frontend/                     # Day 5 — React + Tailwind app
│   └── src/{pages,components,services}/
├── tests/
│   └── test_day3_pipeline.py     # Day 1→2→3 chained demo
└── requirements.txt
```

## What's left for you

The only thing this environment genuinely could not run is training the
real CodeBERT classifier (Day 1), since it needs to download
`microsoft/codebert-base` from Hugging Face and this sandbox has no
network access to that domain. Run `training/train_classifier.py` on
your own machine with internet access, then the API automatically
switches from the mock classifier to your trained one.
