from __future__ import annotations

import base64
import io

from PIL import Image, ImageOps

MAX_INPUT_BYTES = 20 * 1024 * 1024
MAX_INPUT_PIXELS = 24_000_000


def normalize_image_base64(raw_base64: str) -> str:
    """Validate a message image and encode a normalized PNG for NovelAI."""
    if not raw_base64:
        raise ValueError("图片内容为空")
    if raw_base64.startswith("data:"):
        _, _, raw_base64 = raw_base64.partition(",")
    if raw_base64.startswith("base64://"):
        raw_base64 = raw_base64[9:]
    try:
        raw = base64.b64decode(raw_base64, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ValueError("无法解析输入图片") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("输入图片不能超过 20 MB")

    try:
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.width * image.height > MAX_INPUT_PIXELS:
                raise ValueError("输入图片像素过高")
            image = ImageOps.exif_transpose(image)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            output = io.BytesIO()
            image.save(output, format="PNG", optimize=True)
    except Image.DecompressionBombError as exc:
        raise ValueError("输入图片像素过高") from exc
    except (OSError, ValueError) as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError("输入内容不是有效图片") from exc
    return base64.b64encode(output.getvalue()).decode("ascii")

