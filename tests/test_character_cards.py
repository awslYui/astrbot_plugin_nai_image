import pytest
from astrbot_plugin_nai_image.character_cards import (
    expand_character_cards,
    validate_card,
)


def test_expand_character_card() -> None:
    result = expand_character_cards(
        "小画嘉, school uniform",
        {"小画嘉": "1girl, silver hair, blue eyes"},
    )
    assert result.prompt == "1girl, silver hair, blue eyes, school uniform"
    assert result.matched_names == ["小画嘉"]


def test_longer_card_name_is_replaced_first() -> None:
    result = expand_character_cards(
        "小画嘉夏装",
        {"小画嘉": "base", "小画嘉夏装": "summer"},
    )
    assert result.prompt == "summer"
    assert result.matched_names == ["小画嘉夏装"]


def test_card_tags_are_not_recursively_expanded() -> None:
    result = expand_character_cards("卡A", {"卡A": "卡B, red hair", "卡B": "blue hair"})
    assert result.prompt == "卡B, red hair"


@pytest.mark.parametrize("name", ["", "bad,name", "bad|name", "--model"])
def test_invalid_card_name(name: str) -> None:
    with pytest.raises(ValueError):
        validate_card(name, "1girl")
