import pytest
from astrbot_plugin_nai_image.character_cards import (
    CharacterCard,
    detect_shot,
    expand_character_cards,
    parse_card_part_set_command,
    parse_card_set_command,
    replace_card_layer,
    validate_card,
)


def test_parse_card_without_negative_prompt() -> None:
    assert parse_card_set_command("小画嘉 1girl, silver hair, blue eyes") == (
        "小画嘉",
        "1girl, silver hair, blue eyes",
        "",
        True,
    )


def test_parse_quoted_name_and_optional_negative_prompt() -> None:
    assert parse_card_set_command(
        '"小画嘉 夏装" 1girl, summer dress --neg bad hands, watermark'
    ) == (
        "小画嘉 夏装",
        "1girl, summer dress",
        "bad hands, watermark",
        True,
    )


def test_parse_card_can_disable_auto_layering() -> None:
    assert parse_card_set_command("小画嘉 1girl, blue eyes --no-auto-layer") == (
        "小画嘉",
        "1girl, blue eyes",
        "",
        False,
    )


def test_parse_manual_card_layer_with_negative_prompt() -> None:
    assert parse_card_part_set_command(
        '"小画嘉 夏装" lower pleated skirt, white shoes --neg wrong shoes'
    ) == (
        "小画嘉 夏装",
        "lower",
        "pleated skirt, white shoes",
        "wrong shoes",
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


def test_layered_card_only_uses_tags_visible_in_closeup() -> None:
    card = CharacterCard(
        "diana, blue eyes, white dress, white pumps, short stature",
        "missing glasses, wrong shoes",
        positive_layers={
            "core": "diana",
            "face": "blue eyes",
            "upper": "white dress",
            "lower": "white pumps",
            "full": "short stature",
        },
        negative_layers={"face": "missing glasses", "lower": "wrong shoes"},
    )
    result = expand_character_cards(
        "然老师, sleeping",
        {"然老师": card},
        structured=True,
        shot="closeup",
    )
    character = result.character_prompts[0]
    assert character.positive == "diana, blue eyes"
    assert character.negative == "missing glasses"


def test_manual_layer_replacement_rebuilds_full_card() -> None:
    card = CharacterCard(
        "diana, blue eyes",
        positive_layers={"core": "diana", "face": "blue eyes"},
    )
    updated = replace_card_layer(card, "lower", "white pumps", "wrong shoes")
    assert updated.positive == "diana, blue eyes, white pumps"
    assert updated.negative == "wrong shoes"
    assert updated.positive_layers["lower"] == "white pumps"


def test_detect_shot_from_chinese_and_english_prompt() -> None:
    assert detect_shot("然老师的近景侧脸") == "closeup"
    assert detect_shot("upper body, classroom") == "upper"
    assert detect_shot("full body, standing") == "full"


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
