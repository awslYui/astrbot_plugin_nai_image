import pytest
from astrbot_plugin_nai_image.character_cards import (
    CharacterCard,
    expand_character_cards,
    parse_card_set_command,
    validate_card,
)


def test_parse_card_without_negative_prompt() -> None:
    assert parse_card_set_command("小画嘉 1girl, silver hair, blue eyes") == (
        "小画嘉",
        "1girl, silver hair, blue eyes",
        "",
    )


def test_parse_quoted_name_and_optional_negative_prompt() -> None:
    assert parse_card_set_command(
        '"小画嘉 夏装" 1girl, summer dress --neg bad hands, watermark'
    ) == (
        "小画嘉 夏装",
        "1girl, summer dress",
        "bad hands, watermark",
    )


def test_expand_card_as_structured_character_prompt() -> None:
    result = expand_character_cards(
        "小画嘉, school uniform",
        {"小画嘉": CharacterCard("1girl, silver hair", "bad hands")},
        structured=True,
    )
    assert result.prompt == "character 1, school uniform"
    assert result.matched_names == ["小画嘉"]
    assert result.character_prompts[0].positive == "1girl, silver hair"
    assert result.character_prompts[0].negative == "bad hands"


def test_v3_falls_back_to_inline_expansion() -> None:
    result = expand_character_cards(
        "小画嘉, outdoors",
        {"小画嘉": CharacterCard("1girl, silver hair")},
        structured=False,
    )
    assert result.prompt == "1girl, silver hair, outdoors"
    assert result.character_prompts == []


def test_multiple_characters_receive_separate_positions() -> None:
    result = expand_character_cards(
        "甲和乙",
        {"甲": CharacterCard("red hair"), "乙": CharacterCard("blue hair")},
        structured=True,
    )
    assert result.prompt == "character 1和character 2"
    assert [item.x for item in result.character_prompts] == [0.2, 0.8]


@pytest.mark.parametrize("name", ["", "bad,name", "bad|name", "--model"])
def test_invalid_card_name(name: str) -> None:
    with pytest.raises(ValueError):
        validate_card(name, "1girl")
