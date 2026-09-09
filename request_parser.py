from __future__ import annotations

import shlex
from typing import Any

from .models import GenerationMode, GenerationRequest, ParsedCommand, ReferenceType
from .presets import (
    SUPPORTED_SAMPLERS,
    SUPPORTED_SCHEDULES,
    normalize_model,
    parse_size,
    random_seed,
    supports_precise_reference,
    supports_vibe_transfer,
)

VALUE_OPTIONS = {
    "--model",
    "--size",
    "--seed",
    "--steps",
    "--scale",
    "--sampler",
    "--schedule",
    "--neg",
    "--strength",
    "--noise",
    "--type",
    "--fidelity",
    "--info",
}


def parse_generation_command(
    text: str,
    *,
    command_name: str,
    config: dict[str, Any],
    mode: GenerationMode,
) -> ParsedCommand:
    content = _remove_command_prefix(text, command_name)
    try:
        tokens = shlex.split(content, posix=True)
    except ValueError as exc:
        raise ValueError("指令中的引号没有正确闭合") from exc

    options: dict[str, str | bool] = {}
    prompt_parts: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token in {"--no-quality", "--quality"}:
            options[token] = True
            index += 1
            continue
        if token.startswith("--"):
            if token not in VALUE_OPTIONS:
                raise ValueError(f"未知参数：{token}")
            if index + 1 >= len(tokens):
                raise ValueError(f"参数 {token} 缺少值")
            options[token] = tokens[index + 1]
            index += 2
            continue
        prompt_parts.append(token)
        index += 1

    prompt = " ".join(prompt_parts).strip()
    if not prompt:
        raise ValueError("提示词不能为空")
    max_prompt_length = int(config.get("max_prompt_length", 6000))
    if len(prompt) > max_prompt_length:
        raise ValueError(f"提示词不能超过 {max_prompt_length} 个字符")

    default_model = str(config.get("default_model", "nai-diffusion-5-curated"))
    if mode is GenerationMode.PRECISE_REFERENCE:
        default_model = str(
            config.get("reference_model", "nai-diffusion-4-5-full")
        )
    elif mode is GenerationMode.VIBE_TRANSFER:
        default_model = str(config.get("vibe_model", "nai-diffusion-4-5-full"))
    model = normalize_model(str(options.get("--model", default_model)))

    if mode is GenerationMode.PRECISE_REFERENCE and not supports_precise_reference(
        model
    ):
        raise ValueError("Precise Reference 当前请选择 V4.5 模型（v45c/v45f）")
    if mode is GenerationMode.VIBE_TRANSFER and not supports_vibe_transfer(model):
        raise ValueError("Vibe Transfer 当前不支持 V5，请选择 v45c/v45f/v4/v3")

    width, height = parse_size(
        str(options.get("--size", config.get("default_size", "portrait")))
    )
    steps = _bounded_int(
        options.get("--steps", config.get("default_steps", 28)),
        "steps",
        1,
        int(config.get("max_steps", 50)),
    )
    scale = _bounded_float(
        options.get("--scale", config.get("default_scale", 5.0)),
        "scale",
        0.0,
        10.0,
    )
    seed = _parse_seed(options.get("--seed"))
    sampler = str(
        options.get(
            "--sampler", config.get("default_sampler", "k_euler_ancestral")
        )
    )
    if sampler not in SUPPORTED_SAMPLERS:
        raise ValueError(f"不支持的采样器：{sampler}")
    schedule = str(
        options.get("--schedule", config.get("default_schedule", "karras"))
    )
    if schedule not in SUPPORTED_SCHEDULES:
        raise ValueError(f"不支持的噪声计划：{schedule}")

    quality_tags = bool(config.get("quality_tags", True))
    if options.get("--no-quality"):
        quality_tags = False
    elif options.get("--quality"):
        quality_tags = True

    reference_type_raw = str(options.get("--type", "character&style")).lower()
    reference_type_aliases = {
        "character": ReferenceType.CHARACTER,
        "角色": ReferenceType.CHARACTER,
        "style": ReferenceType.STYLE,
        "画风": ReferenceType.STYLE,
        "character&style": ReferenceType.CHARACTER_AND_STYLE,
        "both": ReferenceType.CHARACTER_AND_STYLE,
        "全部": ReferenceType.CHARACTER_AND_STYLE,
    }
    if reference_type_raw not in reference_type_aliases:
        raise ValueError("--type 仅支持 character、style 或 both")

    request = GenerationRequest(
        prompt=prompt,
        negative_prompt=str(
            options.get("--neg", config.get("default_negative_prompt", ""))
        ),
        model=model,
        width=width,
        height=height,
        steps=steps,
        scale=scale,
        sampler=sampler,
        schedule=schedule,
        seed=seed,
        quality_tags=quality_tags,
        mode=mode,
        strength=_bounded_float(
            options.get("--strength", config.get("i2i_strength", 0.6)),
            "strength",
            0.0,
            1.0,
        ),
        noise=_bounded_float(
            options.get("--noise", config.get("i2i_noise", 0.0)),
            "noise",
            0.0,
            1.0,
        ),
        reference_type=reference_type_aliases[reference_type_raw],
        reference_strength=_bounded_float(
            options.get("--strength", config.get("reference_strength", 1.0)),
            "strength",
            -1.0,
            1.0,
        ),
        reference_fidelity=_bounded_float(
            options.get("--fidelity", config.get("reference_fidelity", 0.0)),
            "fidelity",
            0.0,
            1.0,
        ),
        vibe_strength=_bounded_float(
            options.get("--strength", config.get("vibe_strength", 0.6)),
            "strength",
            0.0,
            1.0,
        ),
        vibe_information=_bounded_float(
            options.get("--info", config.get("vibe_information", 1.0)),
            "info",
            0.0,
            1.0,
        ),
    )
    warnings: list[str] = []
    if request.width * request.height > 1_048_576:
        warnings.append("当前尺寸超过约一百万像素，可能产生额外 Anlas 消耗")
    return ParsedCommand(request=request, warnings=warnings)


def _remove_command_prefix(text: str, command_name: str) -> str:
    stripped = text.strip()
    for prefix in (f"/{command_name}", command_name):
        if stripped.lower().startswith(prefix.lower()):
            return stripped[len(prefix) :].strip()
    return stripped


def _parse_seed(value: str | bool | None) -> int:
    if value is None:
        return random_seed()
    return _bounded_int(value, "seed", 0, 4_294_967_295)


def _bounded_int(value: Any, name: str, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是整数") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} 必须在 {minimum}～{maximum} 之间")
    return parsed


def _bounded_float(value: Any, name: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是数字") from exc
    if not minimum <= parsed <= maximum:
        raise ValueError(f"{name} 必须在 {minimum}～{maximum} 之间")
    return parsed

