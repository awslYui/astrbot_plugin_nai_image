import base64
import io

import pytest
from astrbot_plugin_nai_image.image_utils import normalize_image_base64
from PIL import Image


def make_png() -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (64, 64), "pink").save(output, "PNG")
    return output.getvalue()


def test_normalize_image() -> None:
    encoded = base64.b64encode(make_png()).decode("ascii")
    result = base64.b64decode(normalize_image_base64(encoded))
    assert result.startswith(b"\x89PNG\r\n\x1a\n")


def test_reject_invalid_base64() -> None:
    with pytest.raises(ValueError):
        normalize_image_base64("not-base64")

