"""
POST /ocr  - upload an error screenshot, get the text back (sign-in required).
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.ai.ocr import BadImage, OCRUnavailable, extract_text
from backend.config import MAX_IMAGE_BYTES
from backend.security import RateLimiter, get_current_user

router = APIRouter()
_limiter = RateLimiter("ocr", limit=15, window_seconds=60)


@router.post("/ocr", dependencies=[Depends(_limiter)])
async def ocr_image(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    raw = await file.read(MAX_IMAGE_BYTES + 1)
    if len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "Image is too large (max 5 MB).")
    if not raw:
        raise HTTPException(400, "The uploaded file is empty.")
    try:
        result = extract_text(raw)
    except BadImage as e:
        raise HTTPException(400, str(e))
    except OCRUnavailable as e:
        raise HTTPException(503, str(e))
    if not result["text"]:
        raise HTTPException(422, "No readable text was found in that image. Try a sharper, larger screenshot.")
    return result
