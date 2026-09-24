"""
notifications.py - the bell icon.

GET  /notifications            latest 30 + unread count
POST /notifications/read-all   mark everything read
POST /notifications/{id}/read  mark one read
DELETE /notifications         clear all
"""

from fastapi import APIRouter, Depends

from backend.db import get_db
from backend.security import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
def list_notifications(user: dict = Depends(get_current_user)):
    with get_db() as db:
        rows = db.execute(
            "SELECT id, kind, title, body, is_read, created_at FROM notifications "
            "WHERE user_id=? ORDER BY created_at DESC, id DESC LIMIT 30", (user["id"],)
        ).fetchall()
        unread = db.execute(
            "SELECT COUNT(*) c FROM notifications WHERE user_id=? AND is_read=0", (user["id"],)
        ).fetchone()["c"]
    return {"unread": unread, "items": [{**dict(r), "is_read": bool(r["is_read"])} for r in rows]}


@router.post("/read-all")
def read_all(user: dict = Depends(get_current_user)):
    with get_db() as db:
        db.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user["id"],))
    return {"ok": True}


@router.post("/{notification_id}/read")
def read_one(notification_id: int, user: dict = Depends(get_current_user)):
    with get_db() as db:
        db.execute("UPDATE notifications SET is_read=1 WHERE id=? AND user_id=?", (notification_id, user["id"]))
    return {"ok": True}


@router.delete("")
def clear_all(user: dict = Depends(get_current_user)):
    with get_db() as db:
        db.execute("DELETE FROM notifications WHERE user_id=?", (user["id"],))
    return {"ok": True}
