import io
import json
import zipfile

import httpx
import pytest
from astrbot_plugin_nai_image.models import (
    CharacterPrompt,
    GenerationMode,
    GenerationRequest,
    ReferenceType,
)
from astrbot_plugin_nai_image.nai_client import (
    NaiAPIError,
    NovelAIClient,
    build_generation_payload,
    extract_first_image,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"test"


def request(**overrides) -> GenerationRequest:
    values = {
        "prompt": "1girl, solo",
        "negative_prompt": "lowres",
        "model": "nai-diffusion-5-curated",
        "width": 832,
        "height": 1216,
        "steps": 28,
        "scale": 5.0,
        "sampler": "k_euler_ancestral",
        "schedule": "karras",
        "seed": 42,
    }
    values.update(overrides)
    return GenerationRequest(**values)


def test_build_v5_payload() -> None:
    payload = build_generation_payload(request())
    assert payload["action"] == "generate"
    assert payload["model"] == "nai-diffusion-5-curated"
    assert payload["parameters"]["params_version"] == 3
    assert payload["parameters"]["n_samples"] == 1
    assert payload["parameters"]["v4_prompt"]["caption"]["base_caption"] == (
        "1girl, solo"
    )


def test_build_character_prompt_payload() -> None:
    payload = build_generation_payload(
        request(
            prompt="character 1, classroom",
            character_prompts=[
                CharacterPrompt(
                    positive="1girl, silver hair",
                    negative="bad hands",
                    x=0.5,
                    y=0.5,
                )
            ],
        )
    )
    params = payload["parameters"]
    assert params["characterPrompts"] == [
        {
            "prompt": "1girl, silver hair",
            "uc": "bad hands",
            "center": {"x": 0.5, "y": 0.5},
        }
    ]
    assert params["v4_prompt"]["caption"]["char_captions"] == [
        {
            "char_caption": "1girl, silver hair",
            "centers": [{"x": 0.5, "y": 0.5}],
        }
    ]
    assert params["v4_negative_prompt"]["caption"]["char_captions"][0][
        "char_caption"
    ] == "bad hands"


def test_build_img2img_payload() -> None:
    payload = build_generation_payload(
        request(
            mode=GenerationMode.IMAGE_TO_IMAGE,
            source_image_b64="aW1hZ2U=",
            strength=0.5,
            noise=0.1,
        )
    )
    assert payload["action"] == "img2img"
    assert payload["parameters"]["image"] == "aW1hZ2U="
    assert payload["parameters"]["strength"] == 0.5


def test_build_precise_reference_payload() -> None:
    payload = build_generation_payload(
        request(
            model="nai-diffusion-4-5-full",
            mode=GenerationMode.PRECISE_REFERENCE,
            reference_image_b64="aW1hZ2U=",
            reference_type=ReferenceType.CHARACTER,
            reference_strength=0.8,
            reference_fidelity=0.3,
        )
    )
    params = payload["parameters"]
    assert params["director_reference_images"] == ["aW1hZ2U="]
    assert params["director_reference_strength_values"] == [0.8]
    assert params["director_reference_secondary_strength_values"] == [0.7]
    assert params["director_reference_descriptions"][0]["caption"][
        "base_caption"
    ] == "character"


def test_extract_image_from_zip() -> None:
    archive_bytes = io.BytesIO()
    with zipfile.ZipFile(archive_bytes, "w") as archive:
        archive.writestr("image_0.png", PNG)
    image, extension = extract_first_image(archive_bytes.getvalue())
    assert image == PNG
    assert extension == ".png"


def test_reject_non_image_response() -> None:
    with pytest.raises(NaiAPIError):
        extract_first_image(b'{"error":"bad"}')


@pytest.mark.asyncio
async def test_generate_with_mock_transport() -> None:
    captured = {}

    def handler(http_request: httpx.Request) -> httpx.Response:
        captured["payload"] = json.loads(http_request.content)
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})

    client = NovelAIClient("secret", transport=httpx.MockTransport(handler))
    try:
        result = await client.generate(request())
    finally:
        await client.close()
    assert result.extension == ".png"
    assert captured["payload"]["parameters"]["n_samples"] == 1


@pytest.mark.asyncio
async def test_account_info_parsing() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "subscription": {
                    "tier": 3,
                    "active": True,
                    "trainingStepsLeft": {
                        "fixedTrainingStepsLeft": 1000,
                        "purchasedTrainingSteps": 50,
                    },
                    "usage": {"percent": 82, "timeUntilNextPercent": 120},
                }
            },
        )

    client = NovelAIClient("secret", transport=httpx.MockTransport(handler))
    try:
        info = await client.get_account_info()
    finally:
        await client.close()
    assert info.tier_name == "Opus"
    assert info.anlas == 1050
    assert info.v5_usage_percent == 82
