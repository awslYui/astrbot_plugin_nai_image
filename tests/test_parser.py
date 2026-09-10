import pytest
from astrbot_plugin_nai_image.models import GenerationMode, ReferenceType
from astrbot_plugin_nai_image.request_parser import parse_generation_command

DEFAULT_CONFIG = {
    "default_model": "nai-diffusion-5-curated",
    "reference_model": "nai-diffusion-4-5-full",
    "vibe_model": "nai-diffusion-4-5-full",
    "default_size": "portrait",
    "default_steps": 28,
    "max_steps": 50,
    "default_scale": 5.0,
    "default_sampler": "k_euler_ancestral",
    "default_schedule": "karras",
    "default_negative_prompt": "bad hands",
}


def test_parse_text_to_image() -> None:
    parsed = parse_generation_command(
        '/nai --model v5f --size square --seed 42 --neg "lowres, text" 1girl, solo',
        command_name="nai",
        config=DEFAULT_CONFIG,
        mode=GenerationMode.TEXT_TO_IMAGE,
    )
    request = parsed.request
    assert request.prompt == "1girl, solo"
    assert request.negative_prompt == "lowres, text"
    assert request.model == "nai-diffusion-5-full"
    assert (request.width, request.height) == (1024, 1024)
    assert request.seed == 42


def test_parse_manual_shot_override() -> None:
    parsed = parse_generation_command(
        "/nai --shot closeup 然老师, sleeping",
        command_name="nai",
        config=DEFAULT_CONFIG,
        mode=GenerationMode.TEXT_TO_IMAGE,
    )
    assert parsed.request.shot == "closeup"


def test_reject_unknown_shot() -> None:
    with pytest.raises(ValueError, match="--shot"):
        parse_generation_command(
            "/nai --shot aerial 1girl",
            command_name="nai",
            config=DEFAULT_CONFIG,
            mode=GenerationMode.TEXT_TO_IMAGE,
        )


def test_precise_reference_defaults_to_v45() -> None:
    parsed = parse_generation_command(
        "/nai_ref --type character 1girl",
        command_name="nai_ref",
        config=DEFAULT_CONFIG,
        mode=GenerationMode.PRECISE_REFERENCE,
    )
    assert parsed.request.model == "nai-diffusion-4-5-full"
    assert parsed.request.reference_type is ReferenceType.CHARACTER


def test_precise_reference_rejects_v5() -> None:
    with pytest.raises(ValueError, match="V4.5"):
        parse_generation_command(
            "/nai_ref --model v5c 1girl",
            command_name="nai_ref",
            config=DEFAULT_CONFIG,
            mode=GenerationMode.PRECISE_REFERENCE,
        )


def test_unknown_option_is_rejected() -> None:
    with pytest.raises(ValueError, match="未知参数"):
        parse_generation_command(
            "/nai --unknown value 1girl",
            command_name="nai",
            config=DEFAULT_CONFIG,
            mode=GenerationMode.TEXT_TO_IMAGE,
        )


def test_artist_preset_is_appended() -> None:
    config = {
        **DEFAULT_CONFIG,
        "artist_presets": ["sushi=sushispin, 0.9::toosaka_asagi"],
    }
    parsed = parse_generation_command(
        "/nai --artist sushi 1girl, classroom",
        command_name="nai",
        config=config,
        mode=GenerationMode.TEXT_TO_IMAGE,
    )
    assert parsed.request.prompt.endswith("sushispin, 0.9::toosaka_asagi")
    assert parsed.warnings == ["已应用画师预设：sushi"]


def test_artist_none_overrides_default() -> None:
    config = {
        **DEFAULT_CONFIG,
        "artist_presets": ["sushi=sushispin"],
        "default_artist_preset": "sushi",
    }
    parsed = parse_generation_command(
        "/nai --artist none 1girl",
        command_name="nai",
        config=config,
        mode=GenerationMode.TEXT_TO_IMAGE,
    )
    assert parsed.request.prompt == "1girl"


def test_blank_default_artist_uses_first_configured_preset() -> None:
    config = {
        **DEFAULT_CONFIG,
        "artist_presets": ["sushi=sushispin, konya_karasue"],
        "default_artist_preset": "",
    }
    parsed = parse_generation_command(
        "/nai 1girl, classroom",
        command_name="nai",
        config=config,
        mode=GenerationMode.TEXT_TO_IMAGE,
    )
    assert parsed.request.prompt == "1girl, classroom, sushispin, konya_karasue"
    assert parsed.warnings == ["已应用画师预设：sushi"]
