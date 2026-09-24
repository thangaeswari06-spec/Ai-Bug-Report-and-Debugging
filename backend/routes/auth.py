"""
auth.py
-------
POST   /auth/signup           email + password account
POST   /auth/login            email + password (lockout after repeated failures)
POST   /auth/google           "Continue with Google" - verifies Google's ID token server-side
GET    /auth/config           tells the frontend whether Google sign-in is configured
GET    /auth/me               current user
PUT    /auth/me               update name / default language / accent colour
POST   /auth/avatar           upload profile picture (validated + re-encoded)
DELETE /auth/avatar           remove profile picture
POST   /auth/change-password  change (or first-time set) password
DELETE /auth/me               delete account and all of its data
"""

import base64
import io
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from backend.config import (
    GOOGLE_CLIENT_ID,
    LOCKOUT_MINUTES,
    MAX_AVATAR_BYTES,
    MAX_FAILED_LOGINS,
)
from backend.db import get_db
from backend.security import (
    RateLimiter,
    create_access_token,
    get_current_user,
    hash_password,
    notify,
    public_user,
    validate_email_or_400,
    validate_password_or_400,
    verify_password,
)
from backend.utils.languages import LANGUAGE_IDS

router = APIRouter(prefix="/auth", tags=["auth"])

ACCENTS = {"violet", "cyan", "emerald", "rose", "amber"}
_login_limiter = RateLimiter("login", limit=20, window_seconds=60)
_signup_limiter = RateLimiter("signup", limit=10, window_seconds=300)

# A real hash so unknown-email logins take as long as wrong-password logins
# (prevents telling which emails are registered by timing the response).
_DUMMY_HASH = hash_password("dummy-password-for-timing")

Image.MAX_IMAGE_PIXELS = 25_000_000  # decompression-bomb guard


class SignupBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    email: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str


class GoogleBody(BaseModel):
    credential: str = Field(..., min_length=20, max_length=4096)


class ProfileBody(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=60)
    default_language: str | None = None
    accent: str | None = None


class PasswordBody(BaseModel):
    current_password: str | None = None
    new_password: str


class DeleteBody(BaseModel):
    confirm_email: str


def _session(user_row: dict) -> dict:
    return {"token": create_access_token(user_row["id"]), "user": public_user(user_row)}


def _get_user(user_id: int) -> dict:
    with get_db() as db:
        return dict(db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


@router.get("/config")
def auth_config():
    return {"google_enabled": bool(GOOGLE_CLIENT_ID), "google_client_id": GOOGLE_CLIENT_ID or None}


@router.post("/signup", dependencies=[Depends(_signup_limiter)])
def signup(body: SignupBody):
    email = validate_email_or_400(body.email)
    validate_password_or_400(body.password)
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Please enter your name.")

    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(409, "An account with this email already exists. Try signing in.")
        cur = db.execute(
            "INSERT INTO users (email, name, password_hash, created_at) VALUES (?,?,?,?)",
            (email, name, hash_password(body.password), now),
        )
        user_id = cur.lastrowid

    notify(user_id, "welcome", "Welcome to AI BugFixer 🎉",
           "Paste a bug, upload an error screenshot, or try a practice problem to get started.")
    return _session(_get_user(user_id))


@router.post("/login", dependencies=[Depends(_login_limiter)])
def login(body: LoginBody):
    email = (body.email or "").strip().lower()
    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        user = dict(row) if row else None

        generic = HTTPException(401, "Incorrect email or password.")
        if user is None:
            verify_password(body.password, _DUMMY_HASH)
            raise generic

        # ---- account lockout ---------------------------------------------
        if user["locked_until"]:
            until = datetime.fromisoformat(user["locked_until"])
            if until > datetime.now(timezone.utc):
                minutes = int((until - datetime.now(timezone.utc)).total_seconds() // 60) + 1
                raise HTTPException(423, f"Too many failed attempts. Try again in {minutes} minute(s).")

        if not verify_password(body.password, user["password_hash"]):
            failed = user["failed_logins"] + 1
            locked = None
            if failed >= MAX_FAILED_LOGINS:
                locked = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)).isoformat()
                failed = 0
            db.execute("UPDATE users SET failed_logins=?, locked_until=? WHERE id=?", (failed, locked, user["id"]))
            db.commit()
            if locked:
                raise HTTPException(423, f"Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.")
            raise generic

        db.execute("UPDATE users SET failed_logins=0, locked_until=NULL WHERE id=?", (user["id"],))

    notify(user["id"], "security", "New sign-in to your account",
           "If this wasn't you, change your password in Settings → Security.")
    return _session(user)


@router.post("/google", dependencies=[Depends(_login_limiter)])
def google_login(body: GoogleBody):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(503, "Google sign-in is not configured on the server (set GOOGLE_CLIENT_ID).")
    try:
        from google.auth.transport import requests as g_requests
        from google.oauth2 import id_token

        info = id_token.verify_oauth2_token(body.credential, g_requests.Request(), GOOGLE_CLIENT_ID)
    except Exception:
        raise HTTPException(401, "Google sign-in could not be verified. Please try again.")

    if not info.get("email_verified"):
        raise HTTPException(401, "Your Google email address is not verified.")

    email = info["email"].lower()
    sub = info["sub"]
    name = (info.get("name") or email.split("@")[0])[:60]
    now = datetime.now(timezone.utc).isoformat()
    is_new = False

    with get_db() as db:
        row = db.execute("SELECT * FROM users WHERE google_sub = ? OR email = ?", (sub, email)).fetchone()
        if row is None:
            cur = db.execute(
                "INSERT INTO users (email, name, google_sub, created_at) VALUES (?,?,?,?)",
                (email, name, sub, now),
            )
            user_id, is_new = cur.lastrowid, True
        else:
            user_id = row["id"]
            if not row["google_sub"]:  # link Google to an existing password account
                db.execute("UPDATE users SET google_sub=? WHERE id=?", (sub, user_id))

    if is_new:
        notify(user_id, "welcome", "Welcome to AI BugFixer 🎉", "You signed in with Google.")
    else:
        notify(user_id, "security", "New sign-in with Google", "If this wasn't you, review your Google account security.")
    return _session(_get_user(user_id))


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return public_user(user)


@router.put("/me")
def update_me(body: ProfileBody, user: dict = Depends(get_current_user)):
    fields, values = [], []
    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Name cannot be empty.")
        fields.append("name=?"); values.append(name)
    if body.default_language is not None:
        if body.default_language not in LANGUAGE_IDS:
            raise HTTPException(400, "Unsupported language.")
        fields.append("default_language=?"); values.append(body.default_language)
    if body.accent is not None:
        if body.accent not in ACCENTS:
            raise HTTPException(400, "Unknown accent colour.")
        fields.append("accent=?"); values.append(body.accent)
    if fields:
        with get_db() as db:
            db.execute(f"UPDATE users SET {', '.join(fields)} WHERE id=?", (*values, user["id"]))
    return public_user(_get_user(user["id"]))


@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    raw = await file.read(MAX_AVATAR_BYTES + 1)
    if len(raw) > MAX_AVATAR_BYTES:
        raise HTTPException(413, "Image is too large (max 2 MB).")
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ("PNG", "JPEG", "WEBP"):
            raise HTTPException(400, "Only PNG, JPEG or WebP images are allowed.")
        img = ImageOps.exif_transpose(img).convert("RGB")
    except HTTPException:
        raise
    except (UnidentifiedImageError, Exception):
        raise HTTPException(400, "That file is not a valid image.")

    # Re-encode: square crop + 160px WebP. This strips metadata and any
    # trailing/polyglot payload an attacker could hide in the original file.
    img = ImageOps.fit(img, (160, 160), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="WEBP", quality=88)
    data_url = "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()

    with get_db() as db:
        db.execute("UPDATE users SET avatar=? WHERE id=?", (data_url, user["id"]))
    return public_user(_get_user(user["id"]))


@router.delete("/avatar")
def remove_avatar(user: dict = Depends(get_current_user)):
    with get_db() as db:
        db.execute("UPDATE users SET avatar=NULL WHERE id=?", (user["id"],))
    return public_user(_get_user(user["id"]))


@router.post("/change-password", dependencies=[Depends(_login_limiter)])
def change_password(body: PasswordBody, user: dict = Depends(get_current_user)):
    if user["password_hash"]:
        if not body.current_password or not verify_password(body.current_password, user["password_hash"]):
            raise HTTPException(400, "Your current password is incorrect.")
    validate_password_or_400(body.new_password)
    with get_db() as db:
        db.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(body.new_password), user["id"]))
    notify(user["id"], "security", "Password changed", "Your password was updated successfully.")
    return {"message": "Password updated."}


@router.delete("/me")
def delete_me(body: DeleteBody, user: dict = Depends(get_current_user)):
    if body.confirm_email.strip().lower() != user["email"]:
        raise HTTPException(400, "Type your email address exactly to confirm deletion.")
    with get_db() as db:
        db.execute("DELETE FROM users WHERE id=?", (user["id"],))  # cascades to all user data
    return {"message": "Account deleted."}
