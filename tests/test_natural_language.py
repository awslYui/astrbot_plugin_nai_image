import json
from types import SimpleNamespace

import pytest
from astrbot_plugin_nai_image.natural_language import (
    NaturalPromptError,
    NaturalPromptGenerator,
    parse_natural_prompt_response,
)


class _Provider:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls = []

    async def text_chat(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(completion_text=self.output)


class _Context:
    def __init__(self, provider) -> None:
        self.provider = provider

    async def get_using_provider_async(self, **_kwargs):
        return self.provider


class _Event:
    unified_msg_origin = "qq:friend:123"

    @staticmethod
    def get_sender_id() -> str:
        return "123"


@pytest.mark.asyncio
async def test_generate_keeps_directly_named_character_card() -> None:
    output = json.dumps(
        {
            "positive_prompt": "1teacher, standing, teaching, classroom, blackboard",
            "negative_prompt": "empty classroom",
            "character_cards": [],
            "artist_preset": "",
            "size": "landscape",
        }
    )
    provider = _Provider(output)
    result = await NaturalPromptGenerator(_Context(provider), {}).generate(
        "来张然老师在黑板墙讲课的图",
        _Event(),
        card_names=["然老师", "小画嘉"],
        artist_names=["sushi"],
    )
    assert result.character_cards == ["然老师"]
    assert result.size == "landscape"
    assert "然老师" in provider.calls[0]["prompt"]


@pytest.mark.asyncio
async def test_original_message_restores_card_lost_by_outer_llm() -> None:
    output = json.dumps(
        {
            "positive_prompt": "1girl, sleeping, face on folded arms, desk",
            "negative_prompt": "",
            "character_cards": [],
            "artist_preset": "",
            "size": "portrait",
        }
    )
    provider = _Provider(output)
    result = await NaturalPromptGenerator(_Context(provider), {}).generate(
        "可爱的小个子偶像少女趴在办公桌上小憩",
        _Event(),
        card_names=["jk然", "然老师"],
        artist_names=[],
        original_description="来一张小然老师睡觉的图",
    )
    assert result.character_cards == ["然老师"]
    assert "来一张小然老师睡觉的图" in provider.calls[0]["prompt"]
    assert "可爱的小个子偶像少女" not in provider.calls[0]["prompt"]


def test_parse_rejects_hallucinated_card() -> None:
    output = json.dumps(
        {
            "positive_prompt": "classroom",
            "negative_prompt": "",
            "character_cards": ["不存在"],
            "artist_preset": "",
            "size": "portrait",
        }
    )
    with pytest.raises(NaturalPromptError, match="不存在的人设卡"):
        parse_natural_prompt_response(
            output, valid_cards={"然老师"}, valid_artists={"sushi"}
        )


def test_parse_accepts_fenced_json_and_artist() -> None:
    output = """```json
{"positive_prompt":"solo, classroom","negative_prompt":"text","character_cards":["然老师"],"artist_preset":"sushi","size":"portrait"}
```"""
    result = parse_natural_prompt_response(
        output, valid_cards={"然老师"}, valid_artists={"sushi"}
    )
    assert result.artist_preset == "sushi"
    assert result.character_cards == ["然老师"]
