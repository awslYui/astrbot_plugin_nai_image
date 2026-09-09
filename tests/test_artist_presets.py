import pytest
from astrbot_plugin_nai_image.artist_presets import (
    append_prompt_tags,
    parse_artist_presets,
    resolve_artist_preset,
)


def test_parse_named_artist_preset() -> None:
    presets = parse_artist_presets(
        ["sushi=sushispin, konya_karasue", "soft=artist_a, artist_b"]
    )
    assert presets["sushi"] == "sushispin, konya_karasue"
    assert presets["soft"] == "artist_a, artist_b"


def test_resolve_default_requested_and_disabled_artist() -> None:
    config = {
        "artist_presets": ["sushi=sushispin, konya_karasue"],
        "default_artist_preset": "sushi",
    }
    assert resolve_artist_preset(config) == (
        "sushi",
        "sushispin, konya_karasue",
    )
    assert resolve_artist_preset(config, "none") is None
    with pytest.raises(ValueError, match="未找到画师预设"):
        resolve_artist_preset(config, "missing")


def test_blank_default_uses_first_artist_for_existing_configs() -> None:
    config = {
        "artist_presets": [
            "sushi=sushispin, konya_karasue",
            "soft=artist_a, artist_b",
        ],
        "default_artist_preset": "",
    }
    assert resolve_artist_preset(config) == (
        "sushi",
        "sushispin, konya_karasue",
    )


def test_explicit_disabled_default_does_not_use_first_artist() -> None:
    config = {
        "artist_presets": ["sushi=sushispin"],
        "default_artist_preset": "关闭",
    }
    assert resolve_artist_preset(config) is None


def test_append_prompt_tags_normalizes_separator() -> None:
    assert append_prompt_tags("1girl, ", " sushispin") == "1girl, sushispin"
