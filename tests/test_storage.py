import pytest
from astrbot_plugin_nai_image.models import GenerationRequest
from astrbot_plugin_nai_image.storage import StateStore


def sample_request() -> GenerationRequest:
    return GenerationRequest(
        prompt="1girl",
        negative_prompt="lowres",
        model="nai-diffusion-5-curated",
        width=832,
        height=1216,
        steps=28,
        scale=5.0,
        sampler="k_euler_ancestral",
        schedule="karras",
        seed=1,
    )


@pytest.mark.asyncio
async def test_store_roundtrip(tmp_path) -> None:
    store = StateStore(tmp_path)
    await store.mark_attempt("123")
    await store.mark_result("123", sample_request(), success=True)
    restored = await store.get_last_request("123")
    assert restored is not None
    assert restored.prompt == "1girl"
    assert await store.daily_attempts("123") == 1
    stats = await store.statistics()
    assert stats == {"attempted": 1, "succeeded": 1, "failed": 0}

