from __future__ import annotations

import hashlib
import hmac
import io
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_BYTES = 6 * 1024 * 1024
ALLOWED = {"JPEG", "PNG", "WEBP"}
NAME_RE = re.compile(r"^[0-9a-f]{16}\.jpg$")
LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")  # допущение: снимают в Нячанге

Image.MAX_IMAGE_PIXELS = 50_000_000


def _open(data: bytes) -> Image.Image:
    if len(data) > MAX_BYTES:
        raise ValueError("photo too large")
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ALLOWED:
            raise ValueError("bad format")
        img.load()
        return img
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError,
            Image.DecompressionBombWarning) as e:
        raise ValueError("not an image") from e


def exif_age_s(data: bytes, now: datetime) -> int | None:
    """Возраст снимка по EXIF в секундах или None, если даты нет."""
    try:
        img = _open(data)
        ex = img.getexif()
        raw = ex.get_ifd(0x8769).get(36867) or ex.get(306)
        if not raw:
            return None
        t = datetime.strptime(str(raw).strip(), "%Y:%m:%d %H:%M:%S").replace(tzinfo=LOCAL_TZ)
        return int((now - t).total_seconds())
    except Exception:
        return None


def store_photo(data: bytes, photos_dir: str | Path) -> str:
    img = _open(data)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((1280, 1280))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)  # EXIF не переносится
    out = buf.getvalue()
    name = hashlib.sha256(out).hexdigest()[:16] + ".jpg"
    d = Path(photos_dir)
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_bytes(out)
    return name


def _sig(name: str, user_id: int, exp: int, secret: str) -> str:
    return hmac.new(secret.encode(), f"{name}:{user_id}:{exp}".encode(),
                    hashlib.sha256).hexdigest()[:32]


def sign_photo_url(name: str, user_id: int, exp: int, secret: str) -> str:
    return f"/api/photos/{name}?u={user_id}&e={exp}&s={_sig(name, user_id, exp, secret)}"


def check_photo_sig(name: str, u: int, e: int, s: str, secret: str, now_ts: int) -> bool:
    if not NAME_RE.match(name) or e < now_ts:
        return False
    return hmac.compare_digest(_sig(name, u, e, secret), s)
