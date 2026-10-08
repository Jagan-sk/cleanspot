"""Upload sanitising: validate + re-encode images with Pillow.

Security rules (Phase 1):
- the REAL content is checked with Pillow, not the filename/content-type
- only JPEG / PNG / WebP are accepted
- EXIF orientation is applied, then ALL metadata (including EXIF GPS) is
  stripped by re-encoding - location is recorded separately by the app,
  so photos must not leak extra data
- oversized images (in pixels) are downscaled to MAX_IMAGE_DIMENSION
- files are stored under a random UUID name (never the original filename)
"""
import hashlib
import io
import os
import uuid

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings

# Pillow format name -> file extension we store
ALLOWED_FORMATS = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}


class InvalidImageError(ValueError):
    """Raised when the uploaded bytes are not a usable JPEG/PNG/WebP."""


def sanitize_upload(raw: bytes, upload_dir: str) -> tuple[str, str, str]:
    """Validate and re-encode an image upload.

    Returns (absolute_path, sha256_of_saved_bytes, filename).
    Raises InvalidImageError for anything that is not a real allowed image.
    """
    try:
        img = Image.open(io.BytesIO(raw))
        img.load()  # forces a full decode - rejects truncated/fake files
    except (UnidentifiedImageError, OSError):
        raise InvalidImageError("File is not a valid image")

    fmt = (img.format or "").upper()  # format from CONTENT, not extension
    if fmt not in ALLOWED_FORMATS:
        raise InvalidImageError("File is not a valid image")

    img = ImageOps.exif_transpose(img)

    max_dim = settings.MAX_IMAGE_DIMENSION
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim))  # keeps aspect ratio

    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    # re-encode WITHOUT metadata -> strips EXIF (incl. GPS), IPTC, XMP
    buf = io.BytesIO()
    save_kwargs = {"quality": 85} if fmt in ("JPEG", "WEBP") else {}
    img.save(buf, format=fmt, **save_kwargs)
    data = buf.getvalue()

    fname = uuid.uuid4().hex + ALLOWED_FORMATS[fmt]  # random name, no originals
    os.makedirs(upload_dir, exist_ok=True)
    out_path = os.path.join(upload_dir, fname)
    with open(out_path, "wb") as f:
        f.write(data)

    return out_path, hashlib.sha256(data).hexdigest(), fname
