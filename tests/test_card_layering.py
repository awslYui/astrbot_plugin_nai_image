import json
from types import SimpleNamespace

import pytest
from astrbot_plugin_nai_image.card_layering import (
    CardLayeringError,
    CharacterCardLayerer,
    parse_layering_response,
)
from astrbot_plugin_nai_image.character_cards import CharacterCard


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


def _response() -> str:
    return json.dumps(
        {
            "positive": {
                "core": [0],
                "face": [1],
                "upper": [2],
                "lower": [3],
                "full": [4],
            },
            "negative": {
                "core": [],
                "face": [0],
                "upper": [],
                "lower": [1],
                "full": [],
            },
        }
    )


@pytest.mark.asyncio
async def test_llm_only_assigns_indexes_and_original_tags_are_preserved() -> None:
    provider = _Provider(_response())
    card = CharacterCard(
        "diana(a-soul), {{blue eyes}}, white dress, white pumps, short stature",
        "missing glasses, wrong shoes",
    )
    layered = await CharacterCardLayerer(_Context(provider)).layer(
        "然老师", card, _Event()
    )
    assert layered.positive == card.positive
    assert layered.positive_layers == {
        "core": "diana(a-soul)",
        "face": "{{blue eyes}}",
        "upper": "white dress",
        "lower": "white pumps",
        "full": "short stature",
    }
    assert layered.negative_layers["face"] == "missing glasses"
    assert '"id": 0' in provider.calls[0]["prompt"]


def test_rejects_missing_or_duplicate_indexes() -> None:
    payload = json.loads(_response())
    payload["positive"]["core"].append(1)
    with pytest.raises(CardLayeringError, match="遗漏、重复或越界"):
        parse_layering_response(
            json.dumps(payload), positive_count=5, negative_count=2
        )
