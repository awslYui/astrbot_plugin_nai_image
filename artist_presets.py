from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

DISABLED_ARTIST_VALUES = frozenset({"none", "off", "关闭", "无"})


def parse_artist_presets(value: Any) -> dict[str, str]:
    """Normalize WebUI list entries (name=tags) or a mapping into presets."""
    if isinstance(value, Mapping):
        items = value.items()
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        parsed: list[tuple[str, str]] = []
        for index, item in enumerate(value, start=1):
            text = str(item).strip()
            if not text:
                continue
            if "=" in text:
                name, tags = text.split("=", 1)
            else:
                name, tags = f"preset{index}", text
            parsed.append((name, tags))
        items = parsed
    else:
        return {}

    presets: dict[str, str] = {}
    for raw_name, raw_tags in items:
        name = str(raw_name).strip()
        tags = str(raw_tags).strip()
        if not name or not tags:
            continue
        if len(name) > 50:
            raise ValueError("画师预设名称不能超过 50 个字符")
        if any(char in name for char in "\r\n=,"):
            raise ValueError("画师预设名称不能包含换行、等号或逗号")
        if len(tags) > 2000:
            raise ValueError(f"画师预设 {name} 的 Tags 不能超过 2000 个字符")
        presets[name] = tags
    return presets


def resolve_artist_preset(
    config: Mapping[str, Any], requested: str | None = None
) -> tuple[str, str] | None:
    presets = parse_artist_presets(config.get("artist_presets", []))
    if requested is None:
        selected = str(config.get("default_artist_preset", "")).strip()
        if not selected and presets:
            selected = next(iter(presets))
    else:
        selected = requested.strip()
    if not selected or selected.lower() in DISABLED_ARTIST_VALUES:
        return None
    if selected not in presets:
        available = "、".join(presets) or "（未配置）"
        raise ValueError(f"未找到画师预设：{selected}；可用预设：{available}")
    return selected, presets[selected]


def append_prompt_tags(prompt: str, tags: str) -> str:
    parts = [part.strip(" ,") for part in (prompt, tags) if part.strip(" ,")]
    return ", ".join(parts)
