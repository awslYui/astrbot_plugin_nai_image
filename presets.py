from __future__ import annotations

import random

MODEL_ALIASES: dict[str, str] = {
    "v5c": "nai-diffusion-5-curated",
    "v5-curated": "nai-diffusion-5-curated",
    "v5f": "nai-diffusion-5-full",
    "v5-full": "nai-diffusion-5-full",
    "v45c": "nai-diffusion-4-5-curated",
    "v4.5c": "nai-diffusion-4-5-curated",
    "v45f": "nai-diffusion-4-5-full",
    "v4.5f": "nai-diffusion-4-5-full",
    "v4c": "nai-diffusion-4-curated",
    "v4f": "nai-diffusion-4-full",
    "v3": "nai-diffusion-3",
}

SUPPORTED_MODELS = frozenset(MODEL_ALIASES.values())

SIZE_PRESETS: dict[str, tuple[int, int]] = {
    "square": (1024, 1024),
    "portrait": (832, 1216),
    "landscape": (1216, 832),
}

SUPPORTED_SAMPLERS = frozenset(
    {
        "k_euler",
        "k_euler_ancestral",
        "k_dpmpp_2m",
        "k_dpmpp_2m_sde",
        "k_dpmpp_sde",
        "ddim_v3",
    }
)

SUPPORTED_SCHEDULES = frozenset({"native", "karras", "exponential", "polyexponential"})


def normalize_model(value: str) -> str:
    value = value.strip().lower()
    model = MODEL_ALIASES.get(value, value)
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"不支持的模型：{value}")
    return model


def model_alias(model: str) -> str:
    preferred = {
        "nai-diffusion-5-curated": "v5c",
        "nai-diffusion-5-full": "v5f",
        "nai-diffusion-4-5-curated": "v45c",
        "nai-diffusion-4-5-full": "v45f",
        "nai-diffusion-4-curated": "v4c",
        "nai-diffusion-4-full": "v4f",
        "nai-diffusion-3": "v3",
    }
    return preferred.get(model, model)


def is_v4_plus(model: str) -> bool:
    return "diffusion-4" in model or "diffusion-5" in model


def is_v5(model: str) -> bool:
    return "diffusion-5" in model


def supports_precise_reference(model: str) -> bool:
    return "diffusion-4-5" in model


def supports_vibe_transfer(model: str) -> bool:
    return not is_v5(model)


def parse_size(value: str) -> tuple[int, int]:
    normalized = value.lower().strip()
    if normalized in SIZE_PRESETS:
        return SIZE_PRESETS[normalized]
    if "x" not in normalized:
        raise ValueError("尺寸应为 square/portrait/landscape 或 宽x高")
    width_text, height_text = normalized.split("x", 1)
    try:
        width, height = int(width_text), int(height_text)
    except ValueError as exc:
        raise ValueError("自定义尺寸必须是整数，例如 832x1216") from exc
    validate_dimensions(width, height)
    return width, height


def validate_dimensions(width: int, height: int) -> None:
    if width < 256 or height < 256:
        raise ValueError("宽和高不能小于 256")
    if width > 1536 or height > 1536:
        raise ValueError("宽和高不能超过 1536")
    if width % 64 or height % 64:
        raise ValueError("宽和高必须是 64 的倍数")
    if width * height > 1_572_864:
        raise ValueError("总像素过高，不能超过 1536×1024")


def random_seed() -> int:
    return random.SystemRandom().randint(0, 4_294_967_295)

