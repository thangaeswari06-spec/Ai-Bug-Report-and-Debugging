"""
ocr.py
------
Reads text out of an error screenshot.

Needs the Tesseract OCR engine installed on the machine running the backend:
    Windows : https://github.com/UB-Mannheim/tesseract/wiki   (then add it to PATH)
    macOS   : brew install tesseract
    Ubuntu  : sudo apt install tesseract-ocr

Screenshots of terminals/IDEs are usually LIGHT text on a DARK background,
which Tesseract reads poorly - so we detect that and invert the image first.
"""

import io
import re

from PIL import Image, ImageOps, ImageStat, UnidentifiedImageError

try:
    import pytesseract
except ImportError:  # handled at call time with a friendly message
    pytesseract = None

Image.MAX_IMAGE_PIXELS = 25_000_000


class OCRUnavailable(RuntimeError):
    pass


class BadImage(ValueError):
    pass


ERROR_LINE = re.compile(
    r"(error|exception|traceback|fatal|panic|failed|undefined|cannot|unexpected|segmentation|not defined|null|refused|denied|warning)",
    re.I,
)

_LANG_HINTS = [
    ("python", r'Traceback \(most recent call last\)|File ".*\.py", line \d+|\b\w+Error: '),
    ("typescript", r"\.tsx?[:(]\d+|error TS\d+"),
    ("javascript", r"\.(?:m?js|jsx):\d+|ReferenceError|node:internal|Uncaught "),
    ("java", r"\.java:\d+|Exception in thread|java\.lang\."),
    ("rust", r"error\[E\d+\]|-->\s*\S+\.rs:\d+|panicked at"),
    ("go", r"\.go:\d+|goroutine \d+|panic: "),
    ("php", r"PHP (?:Parse|Fatal|Warning)|on line \d+|\.php"),
    ("csharp", r"\.cs\(\d+,\d+\)|CS\d{4}|System\.\w+Exception"),
    ("cpp", r"\.(?:cpp|cc|cxx):\d+:\d+|std::"),
    ("c", r"\.c:\d+:\d+|Segmentation fault|undefined reference to"),
]


def _prepare(img: Image.Image) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("L")
    if img.width < 1200:  # small screenshots OCR badly - upscale
        scale = 1200 / img.width
        img = img.resize((int(img.width * scale), int(img.height * scale)), Image.LANCZOS)
    if ImageStat.Stat(img).mean[0] < 128:  # dark theme -> invert to dark text on light background
        img = ImageOps.invert(img)
    img = ImageOps.autocontrast(img)
    return img


def guess_language(text: str) -> str | None:
    for lang, pattern in _LANG_HINTS:
        if re.search(pattern, text):
            return lang
    return None


def extract_text(raw: bytes) -> dict:
    if pytesseract is None:
        raise OCRUnavailable("pytesseract is not installed. Run: pip install pytesseract")
    try:
        img = Image.open(io.BytesIO(raw))
        if img.format not in ("PNG", "JPEG", "WEBP"):
            raise BadImage("Only PNG, JPEG or WebP screenshots are supported.")
        img.load()
    except BadImage:
        raise
    except (UnidentifiedImageError, Exception):
        raise BadImage("That file is not a valid image.")

    try:
        text = pytesseract.image_to_string(_prepare(img), config="--psm 6")
    except pytesseract.TesseractNotFoundError:
        raise OCRUnavailable("Tesseract OCR is not installed on the server. See backend/ai/ocr.py for install steps.")

    lines = [ln.rstrip() for ln in text.splitlines()]
    cleaned = "\n".join(lines).strip()

    error_only = [ln for ln in lines if ln.strip() and ERROR_LINE.search(ln)]
    return {
        "text": cleaned,
        "suggested_error": "\n".join(error_only[:8]).strip() or cleaned[:600],
        "language_guess": guess_language(cleaned),
        "chars": len(cleaned),
    }
