from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

from .models import CharacterPrompt


@dataclass(slots=True)
class CharacterCard:
    positive: str
    negative: str = ""


@dataclass(slots=True)
class CardExpansion:
    prompt: str
    matched_names: list[str]
    character_prompts: list[CharacterPrompt]


def parse_card_set_command(text: str) -> tuple[str, str, str]:
    """Parse: <name> <positive tags> [--neg <negative tags>]."""
    try:
        tokens = shlex.split(text, posix=True)
    except ValueError as exc:
        raise ValueError("人设卡指令中的引号没有正确闭合") from exc
    if len(tokens) < 2:
        raise ValueError("用法：/nai_card_set 人设名 正面Tags [--neg 反面Tags]")

    name = tokens[0]
    rest = tokens[1:]
    markers = [
        index for index, token in enumerate(rest) if token in {"--neg", "--negative"}
    ]
    if len(markers) > 1:
        raise ValueError("反面提示词参数只能填写一次")
    if markers:
        marker = markers[0]
        positive_tokens = rest[:marker]
        negative_tokens = rest[marker + 1 :]
    else:
        positive_tokens = rest
        negative_tokens = []
    return name, " ".join(positive_tokens).strip(), " ".join(negative_tokens).strip()


def validate_card(
    name: str,
    positive: str,
    negative: str = "",
    *,
    max_tags_length: int = 2000,
) -> tuple[str, CharacterCard]:
    normalized_name = name.strip()
    normalized_positive = positive.strip()
    normalized_negative = negative.strip()
    if not normalized_name:
        raise ValueError("人设卡名称不能为空")
    if len(normalized_name) > 40:
        raise ValueError("人设卡名称不能超过 40 个字符")
    if any(char in normalized_name for char in "\r\n|,"):
        raise ValueError("人设卡名称不能包含换行、竖线或逗号")
    if normalized_name.startswith("--"):
        raise ValueError("人设卡名称不能以 -- 开头")
    if not normalized_positive:
        raise ValueError("人设卡正面 Tags 不能为空")
    if len(normalized_positive) > max_tags_length:
        raise ValueError(f"人设卡正面 Tags 不能超过 {max_tags_length} 个字符")
    if len(normalized_negative) > max_tags_length:
        raise ValueError(f"人设卡反面 Tags 不能超过 {max_tags_length} 个字符")
    return normalized_name, CharacterCard(normalized_positive, normalized_negative)


def expand_character_cards(
    prompt: str,
    cards: dict[str, CharacterCard],
    *,
    structured: bool,
) -> CardExpansion:
    names = [name for name in sorted(cards, key=len, reverse=True) if name]
    if not names:
        return CardExpansion(prompt=prompt, matched_names=[], character_prompts=[])
    pattern = re.compile("|".join(re.escape(name) for name in names))
    matched: list[str] = []
    for match in pattern.finditer(prompt):
        name = match.group(0)
        if name not in matched:
            matched.append(name)
    if not matched:
        return CardExpansion(prompt=prompt, matched_names=[], character_prompts=[])

    slot_by_name = {name: index + 1 for index, name in enumerate(matched)}

    def replace(match: re.Match[str]) -> str:
        name = match.group(0)
        if structured:
            return f"character {slot_by_name[name]}"
        return cards[name].positive

    expanded = pattern.sub(replace, prompt)
    character_prompts: list[CharacterPrompt] = []
    if structured:
        count = len(matched)
        for index, name in enumerate(matched):
            x = 0.5 if count == 1 else round(0.2 + 0.6 * index / (count - 1), 2)
            card = cards[name]
            character_prompts.append(
                CharacterPrompt(card.positive, card.negative, x=x, y=0.5)
            )
    return CardExpansion(expanded, matched, character_prompts)
