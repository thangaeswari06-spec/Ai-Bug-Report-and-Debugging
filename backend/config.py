"""
config.py
---------
Central place for environment-driven settings.

Copy `.env.example` to `.env` (or export the variables) before running in
production. Nothing here is a real secret - the defaults are only safe for
local development.
"""

import os
import secrets

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.environ.get("BUGFIXER_DB", os.path.join(DATA_DIR, "bugfixer.db"))


def _load_secret_key() -> str:
    """
    JWT signing key. Order of preference:
      1. SECRET_KEY environment variable (use this in production)
      2. A random key generated once and stored in data/.secret_key so
         logins survive a server restart during development.
    """
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    path = os.path.join(DATA_DIR, ".secret_key")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read().strip()
    key = secrets.token_urlsafe(64)
    with open(path, "w", encoding="utf-8") as f:
        f.write(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return key


SECRET_KEY = _load_secret_key()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.environ.get("ACCESS_TOKEN_MINUTES", "720"))  # 12 hours

# Google "Continue with Google" - create an OAuth Web client at
# https://console.cloud.google.com/apis/credentials and paste its client id here
# AND in frontend/.env as VITE_GOOGLE_CLIENT_ID.
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")

CORS_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"
    ).split(",")
    if o.strip()
]

# Login brute-force protection
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 10

# Uploads
MAX_IMAGE_BYTES = 5 * 1024 * 1024       # error screenshots
MAX_AVATAR_BYTES = 2 * 1024 * 1024      # profile pictures
MAX_CODE_CHARS = 50_000

# Practice code runner
RUN_TIMEOUT_SECONDS = int(os.environ.get("RUN_TIMEOUT_SECONDS", "6"))
