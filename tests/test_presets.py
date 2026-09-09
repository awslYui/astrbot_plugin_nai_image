import pytest
from astrbot_plugin_nai_image.presets import (
    normalize_model,
    parse_size,
    validate_dimensions,
)


def test_model_aliases() -> None:
    assert normalize_model("v5c") == "nai-diffusion-5-curated"
    assert normalize_model("v45f") == "nai-diffusion-4-5-full"


def test_size_presets_and_custom_size() -> None:
    assert parse_size("portrait") == (832, 1216)
    assert parse_size("1024x1024") == (1024, 1024)


@pytest.mark.parametrize(
    "width,height", [(255, 1024), (800, 1024), (1600, 768), (1536, 1088)]
)
def test_invalid_dimensions(width: int, height: int) -> None:
    with pytest.raises(ValueError):
        validate_dimensions(width, height)
