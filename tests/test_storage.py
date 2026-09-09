import pytest
from astrbot_plugin_nai_image.character_cards import CharacterCard
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


@pytest.mark.asyncio
async def test_global_character_cards_and_health_mode_roundtrip(tmp_path) -> None:
    store = StateStore(tmp_path)
    assert await store.set_character_card(
        "小画嘉", CharacterCard("1girl, blue eyes"), max_cards=2
    )
    assert not await store.set_character_card(
        "小画嘉",
        CharacterCard("1girl, silver hair", "bad hands"),
        max_cards=2,
    )
    assert await store.get_character_cards() == {
        "小画嘉": CharacterCard("1girl, silver hair", "bad hands")
    }
    assert not await store.get_health_mode("123", default=False)
    await store.set_health_mode("123", True)

    restored = StateStore(tmp_path)
    assert await restored.get_health_mode("123", default=False)
    assert await restored.delete_character_card("小画嘉")
    assert await restored.get_character_cards() == {}


@pytest.mark.asyncio
async def test_legacy_string_character_card_is_migrated_on_read(tmp_path) -> None:
    store = StateStore(tmp_path)
    store._state["character_cards"] = {"123": {"旧卡": "1girl, pink hair"}}
    assert await store.get_character_cards() == {
        "旧卡": CharacterCard("1girl, pink hair", "")
    }
    assert store._state["character_cards"] == {}
    assert store._state["global_character_cards"] == {
        "旧卡": "1girl, pink hair"
    }


@pytest.mark.asyncio
async def test_legacy_user_cards_become_shared(tmp_path) -> None:
    store = StateStore(tmp_path)
    store._state["character_cards"] = {
        "10001": {"然老师": {"positive": "brown hair"}},
        "10002": {
            "小画嘉": {"positive": "silver hair"},
            "然老师": {"positive": "different card"},
        },
    }

    cards = await store.get_character_cards()

    assert cards == {
        "然老师": CharacterCard("brown hair", ""),
        "小画嘉": CharacterCard("silver hair", ""),
    }
    restored = StateStore(tmp_path)
    assert await restored.get_character_cards() == cards
