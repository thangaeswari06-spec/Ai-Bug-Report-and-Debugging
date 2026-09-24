"""
history.py
----------
Per-user analysis history (every query is scoped by user_id, so one user can
never read or delete another user's reports).

GET    /history          list (newest first)
GET    /history/{id}     one item
DELETE /history/{id}     delete one item
DELETE /history          clear all of MY history
"""

import json

from fastapi import APIRouter, Depends, HTTPException

from backend.db import get_db
from backend.security import get_current_user

router = APIRouter()


@router.get("/history")
def list_history(limit: int = 50, user: dict = Depends(get_current_user)):
    limit = max(1, min(limit, 200))
    with get_db() as db:
        rows = db.execute(
            "SELECT payload FROM analyses WHERE user_id=? ORDER BY created_at DESC LIMIT ?", (user["id"], limit)
        ).fetchall()
    return [json.loads(r["payload"]) for r in rows]


@router.get("/history/{item_id}")
def get_history_item(item_id: str, user: dict = Depends(get_current_user)):
    with get_db() as db:
        row = db.execute("SELECT payload FROM analyses WHERE id=? AND user_id=?", (item_id, user["id"])).fetchone()
    if not row:
        raise HTTPException(404, "History item not found.")
    return json.loads(row["payload"])


@router.delete("/history/{item_id}")
def delete_history_item(item_id: str, user: dict = Depends(get_current_user)):
    with get_db() as db:
        cur = db.execute("DELETE FROM analyses WHERE id=? AND user_id=?", (item_id, user["id"]))
    if cur.rowcount == 0:
        raise HTTPException(404, "History item not found.")
    return {"message": "Deleted."}


@router.delete("/history")
def clear_history(user: dict = Depends(get_current_user)):
    with get_db() as db:
        db.execute("DELETE FROM analyses WHERE user_id=?", (user["id"],))
    return {"message": "History cleared."}
