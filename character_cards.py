from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(slots=True)
class CardExpansion:
    prompt: str
    matched_names: list[str]


def validate_card(name: str, tags: str, *, max_tags_length: int = 2000) -> tuple[str, str]:
    normalized_name = name.strip()
    normalized_tags = tags.strip()
    if not normalized_name:
        raise ValueError("人设卡名称不能为空")
    if len(normalized_name) > 40:
        raise ValueError("人设卡名称不能超过 40 个字符")
    if any(char in normalized_name for char in "\r\n|,"):
        raise ValueError("人设卡名称不能包含换行、竖线或逗号")
    if normalized_name.startswith("--"):
        raise ValueError("人设卡名称不能以 -- 开头")
    if not normalized_tags:
        raise ValueError("人设卡 Tags 不能为空")
    if len(normalized_tags) > max_tags_length:
        raise ValueError(f"人设卡 Tags 不能超过 {max_tags_length} 个字符")
    return normalized_name, normalized_tags


def expand_character_cards(prompt: str, cards: dict[str, str]) -> CardExpansion:
    names = [name for name in sorted(cards, key=len, reverse=True) if name]
    if not names:
        return CardExpansion(prompt=prompt, matched_names=[])
    matched: list[str] = []
    pattern = re.compile("|".join(re.escape(name) for name in names))

    def replace(match: re.Match[str]) -> str:
        name = match.group(0)
        if name not in matched:
            matched.append(name)
        return cards[name]

    expanded = pattern.sub(replace, prompt)
    return CardExpansion(prompt=expanded, matched_names=matched)
