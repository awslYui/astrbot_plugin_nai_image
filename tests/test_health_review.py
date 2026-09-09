import json
from types import SimpleNamespace

import httpx
import pytest
from astrbot_plugin_nai_image.health_review import (
    HealthPromptReviewer,
    HealthReviewError,
    parse_review_response,
)


class Event:
    unified_msg_origin = "test:friend:1"

    def get_sender_id(self) -> str:
        return "123"


@pytest.mark.asyncio
async def test_review_with_astrbot_provider_only_deletes_segments() -> None:
    provider = SimpleNamespace(
        text_chat=lambda **_kwargs: None,
    )

    async def text_chat(**_kwargs):
        return SimpleNamespace(
            completion_text='{"remove_indices":[1],"reason":"不健康"}'
        )

    provider.text_chat = text_chat

    async def get_provider(**_kwargs):
        return provider

    context = SimpleNamespace(get_using_provider_async=get_provider)
    reviewer = HealthPromptReviewer(context, {})
    try:
        result = await reviewer.review("1girl, unsafe tag, blue eyes", Event())
    finally:
        await reviewer.close()
    assert result.prompt == "1girl, blue eyes"
    assert result.removed_segments == ["unsafe tag"]


@pytest.mark.asyncio
async def test_review_with_custom_openai_compatible_api() -> None:
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers["authorization"]
        captured["payload"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"remove_indices":[],"reason":"安全"}'}}
                ]
            },
        )

    reviewer = HealthPromptReviewer(
        object(),
        {
            "health_llm_api_key": "secret",
            "health_llm_base_url": "https://llm.example/v1",
            "health_llm_model": "review-model",
        },
        transport=httpx.MockTransport(handler),
    )
    try:
        result = await reviewer.review("1girl, blue eyes", Event())
    finally:
        await reviewer.close()
    assert result.prompt == "1girl, blue eyes"
    assert captured["authorization"] == "Bearer secret"
    assert captured["payload"]["model"] == "review-model"


def test_rejects_out_of_range_review_index() -> None:
    with pytest.raises(HealthReviewError):
        parse_review_response('{"remove_indices":[2]}', 2)


def test_rejects_boolean_review_index() -> None:
    with pytest.raises(HealthReviewError):
        parse_review_response('{"remove_indices":[true]}', 2)
