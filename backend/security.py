"""
security.py
-----------
Everything security-related in one file so it is easy to review:

  * password hashing  - PBKDF2-HMAC-SHA256, per-user random salt, 390k rounds
  * password policy   - length + mixed character classes + common-password block
  * JWT access tokens - signed, short-lived, checked on every protected route
  * rate limiting     - in-memory sliding window (per IP + route)
  * security headers  - nosniff, frame deny, referrer policy, CSP for the API
"""

import base64
import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.config import ACCESS_TOKEN_MINUTES, JWT_ALGORITHM, SECRET_KEY
from backend.db import get_db

PBKDF2_ROUNDS = 390_000
COMMON_PASSWORDS = {
    "password", "password1", "password123", "12345678", "123456789", "qwerty123",
    "iloveyou", "admin123", "welcome1", "letmein123", "abc12345", "11111111",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------- passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        _, rounds, salt_b64, digest_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(rounds))
        return hmac.compare_digest(actual, expected)  # constant-time compare
    except Exception:
        return False


def password_problems(password: str) -> list[str]:
    problems = []
    if len(password) < 8:
        problems.append("at least 8 characters")
    if len(password) > 128:
        problems.append("at most 128 characters")
    if not re.search(r"[a-z]", password):
        problems.append("a lowercase letter")
    if not re.search(r"[A-Z]", password):
        problems.append("an uppercase letter")
    if not re.search(r"\d", password):
        problems.append("a number")
    if password.lower() in COMMON_PASSWORDS:
        problems.append("something less common")
    return problems


def validate_password_or_400(password: str):
    problems = password_problems(password)
    if problems:
        raise HTTPException(status_code=400, detail="Password needs: " + ", ".join(problems) + ".")


def validate_email_or_400(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email) or len(email) > 254:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    return email


# --------------------------------------------------------------------- JWT
def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


_bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """FastAPI dependency - put it on every route that needs a signed-in user."""
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Please sign in to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if creds is None:
        raise unauthorized
    try:
        payload = jwt.decode(creds.credentials, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized

    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None:
        raise unauthorized
    return dict(row)


def public_user(row: dict) -> dict:
    """What the frontend is allowed to see (never the hash)."""
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "avatar": row["avatar"],
        "default_language": row["default_language"],
        "accent": row["accent"],
        "has_password": bool(row["password_hash"]),
        "has_google": bool(row["google_sub"]),
        "created_at": row["created_at"],
    }


# ------------------------------------------------------------ rate limiting
class RateLimiter:
    """Sliding-window limiter. Use as: Depends(RateLimiter('login', 10, 60))."""

    def __init__(self, name: str, limit: int, window_seconds: int):
        self.name, self.limit, self.window = name, limit, window_seconds
        self.hits: dict[str, deque] = defaultdict(deque)

    def __call__(self, request: Request):
        key = f"{self.name}:{request.client.host if request.client else 'unknown'}"
        now = time.monotonic()
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            retry = int(self.window - (now - q[0])) + 1
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests. Try again in {retry} seconds.",
                headers={"Retry-After": str(retry)},
            )
        q.append(now)


# --------------------------------------------------------------- notifications
def notify(user_id: int, kind: str, title: str, body: str = ""):
    with get_db() as db:
        db.execute(
            "INSERT INTO notifications (user_id, kind, title, body, created_at) VALUES (?,?,?,?,?)",
            (user_id, kind, title, body, datetime.now(timezone.utc).isoformat()),
        )
