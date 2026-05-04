from __future__ import annotations

import uuid
from pathlib import Path

import numpy as np
from PIL import Image

UPLOAD_DIR = Path("/tmp/webplotdigitizer_uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_DIMENSION = 4000
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


class ImageValidationError(Exception):
    pass


def validate_image(data: bytes, filename: str) -> Image.Image:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ImageValidationError(f"Unsupported format: {ext}. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    if len(data) > MAX_FILE_SIZE:
        raise ImageValidationError(f"File too large: {len(data)} bytes. Max: {MAX_FILE_SIZE} bytes")

    img = Image.open(__import__("io").BytesIO(data))
    w, h = img.size
    if w > MAX_DIMENSION or h > MAX_DIMENSION:
        raise ImageValidationError(f"Image too large: {w}x{h}. Max dimension: {MAX_DIMENSION}")

    return img


def normalize_to_rgb(img: Image.Image) -> Image.Image:
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        return background
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def save_upload(data: bytes, filename: str) -> tuple[str, int, int]:
    img = validate_image(data, filename)
    img = normalize_to_rgb(img)

    image_id = uuid.uuid4().hex[:12]
    save_path = UPLOAD_DIR / f"{image_id}.png"
    img.save(save_path, "PNG")

    return image_id, img.size[0], img.size[1]


def load_image(image_id: str) -> np.ndarray:
    path = UPLOAD_DIR / f"{image_id}.png"
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_id}")
    img = Image.open(path).convert("RGB")
    return np.array(img)
