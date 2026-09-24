"""
main.py
-------
FastAPI entrypoint. Run with:

    uvicorn backend.main:app --reload --port 8000

Interactive docs: http://localhost:8000/docs
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.config import CORS_ORIGINS
from backend.db import init_db
from backend.routes import analyze, auth, history, notifications, ocr, practice
from backend.utils.languages import LANGUAGES

init_db()

app = FastAPI(
    title="AI BugFixer API",
    description="Bug classification, severity, RAG, LLM fixes, error-line location, OCR, practice arena and accounts.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Defensive headers on every response."""
    # Reject giant bodies early (uploads are additionally checked per-route).
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > 8 * 1024 * 1024:
        return JSONResponse({"detail": "Request body too large."}, status_code=413)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    return response


app.include_router(auth.router)
app.include_router(analyze.router, tags=["analyze"])
app.include_router(history.router, tags=["history"])
app.include_router(notifications.router)
app.include_router(ocr.router, tags=["ocr"])
app.include_router(practice.router)


@app.get("/languages", tags=["meta"])
def languages():
    return LANGUAGES


@app.get("/health", tags=["meta"])
def health_check():
    return {"status": "ok"}
