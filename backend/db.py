"""
db.py
-----
Tiny SQLite layer (stdlib only - no ORM needed for this project's scale).

Tables
  users              accounts (email/password and/or Google)
  analyses           each user's private debug history
  notifications      what the bell icon shows
  practice_progress  which practice problems a user solved, per language
"""

import sqlite3
import threading
from contextlib import contextmanager

from backend.config import DB_PATH

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    email           TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name            TEXT NOT NULL,
    password_hash   TEXT,
    google_sub      TEXT UNIQUE,
    avatar          TEXT,
    default_language TEXT NOT NULL DEFAULT 'python',
    accent          TEXT NOT NULL DEFAULT 'violet',
    failed_logins   INTEGER NOT NULL DEFAULT 0,
    locked_until    TEXT,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id          TEXT PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    payload     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS notifications (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL,
    title       TEXT NOT NULL,
    body        TEXT NOT NULL DEFAULT '',
    is_read     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notif_user ON notifications(user_id, is_read, created_at DESC);

CREATE TABLE IF NOT EXISTS practice_progress (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    problem_id  TEXT NOT NULL,
    language    TEXT NOT NULL,
    attempts    INTEGER NOT NULL DEFAULT 0,
    solved      INTEGER NOT NULL DEFAULT 0,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (user_id, problem_id, language)
);
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db():
    with get_db() as db:
        db.executescript(SCHEMA)


@contextmanager
def get_db():
    """Yields a connection, commits on success, rolls back on error."""
    with _lock:
        conn = _connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
