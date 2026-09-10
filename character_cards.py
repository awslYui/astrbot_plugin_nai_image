from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field

from .models import CharacterPrompt

CARD_LAYERS = ("core", "face", "upper", "lower", "full")
SHOT_TYPES = ("auto", "closeup", "upper", "lower", "full")
SHOT_LAYERS = {
    "closeup": ("core", "face"),
    "upper": ("core", "face", "upper"),
    "lower": ("core", "lower"),
    "full": CARD_LAYERS,
}


@dataclass(slots=True)
class CharacterCard:
    positive: str
    negative: str = ""
    positive_layers: dict[str, str] = field(default_factory=dict)
    negative_layers: dict[str, str] = field(default_factory=dict)

    @property
    def is_layered(self) -> bool:
        return any(self.positive_layers.values())

    def prompts_for_shot(self, shot: str) -> tuple[str, str]:
        if not self.is_layered:
            return self.positive, self.negative
        selected = SHOT_LAYERS[normalize_shot(shot, allow_auto=False)]
        positive = join_tag_parts(*(self.positive_layers.get(part, "") for part in selected))
        negative = join_tag_parts(*(self.negative_layers.get(part, "") for part in selected))
        return positive, negative


@dataclass(slots=True)
class CardExpansion:
    prompt: str
    matched_names: list[str]
    character_prompts: list[CharacterPrompt]


def parse_card_set_command(text: str) -> tuple[str, str, str, bool]:
    """Parse: <name> <positive tags> [--neg <negative tags>]."""
    try:
        tokens = shlex.split(text, posix=True)
    except ValueError as exc:
        raise ValueError("人设卡指令中的引号没有正确闭合") from exc
    if len(tokens) < 2:
        raise ValueError("用法：/nai_card_set 人设名 正面Tags [--neg 反面Tags]")

    name = tokens[0]
    auto_layer = "--no-auto-layer" not in tokens[1:]
    rest = [token for token in tokens[1:] if token != "--no-auto-layer"]
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
    return (
        name,
        " ".join(positive_tokens).strip(),
        " ".join(negative_tokens).strip(),
        auto_layer,
    )


def parse_card_part_set_command(text: str) -> tuple[str, str, str, str]:
    """Parse: <name> <layer> <positive tags> [--neg <negative tags>]."""
    try:
        tokens = shlex.split(text, posix=True)
    except ValueError as exc:
        raise ValueError("人设卡指令中的引号没有正确闭合") from exc
    if len(tokens) < 2:
        raise ValueError(
            "用法：/nai_card_part_set 人设名 core|face|upper|lower|full "
            "正面Tags [--neg 反面Tags]"
        )
    name, layer = tokens[:2]
    normalized_layer = normalize_card_layer(layer)
    _, positive, negative, _ = parse_card_set_command(
        " ".join([shlex.quote(name), *tokens[2:]])
    )
    return name, normalized_layer, positive, negative


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
    shot: str = "full",
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
        return cards[name].prompts_for_shot(shot)[0]

    expanded = pattern.sub(replace, prompt)
    character_prompts: list[CharacterPrompt] = []
    if structured:
        count = len(matched)
        for index, name in enumerate(matched):
            x = 0.5 if count == 1 else round(0.2 + 0.6 * index / (count - 1), 2)
            positive, negative = cards[name].prompts_for_shot(shot)
            character_prompts.append(
                CharacterPrompt(positive, negative, x=x, y=0.5)
            )
    return CardExpansion(expanded, matched, character_prompts)


def normalize_card_layer(layer: str) -> str:
    aliases = {
        "核心": "core",
        "脸部": "face",
        "面部": "face",
        "上半身": "upper",
        "下半身": "lower",
        "全身": "full",
    }
    normalized = aliases.get(layer.strip().lower(), layer.strip().lower())
    if normalized not in CARD_LAYERS:
        raise ValueError("分层仅支持 core、face、upper、lower、full")
    return normalized


def normalize_shot(shot: str, *, allow_auto: bool = True) -> str:
    aliases = {
        "近景": "closeup",
        "特写": "closeup",
        "脸部": "closeup",
        "半身": "upper",
        "上半身": "upper",
        "下半身": "lower",
        "腿部": "lower",
        "远景": "full",
        "全身": "full",
    }
    normalized = aliases.get(shot.strip().lower(), shot.strip().lower())
    allowed = SHOT_TYPES if allow_auto else SHOT_TYPES[1:]
    if normalized not in allowed:
        raise ValueError("--shot 仅支持 auto、closeup、upper、lower、full")
    return normalized


def detect_shot(text: str) -> str | None:
    normalized = text.lower().replace("_", " ")
    rules = (
        ("lower", ("下半身", "腿部特写", "脚部特写", "leg focus", "feet focus")),
        ("closeup", ("近景", "特写", "脸部", "侧脸", "头像", "close-up", "closeup", "face focus", "headshot")),
        ("upper", ("上半身", "半身", "胸像", "upper body", "bust shot", "cowboy shot")),
        ("full", ("全身", "远景", "从头到脚", "full body", "wide shot", "long shot")),
    )
    for shot, keywords in rules:
        if any(keyword in normalized for keyword in keywords):
            return shot
    return None


def resolve_shot(requested: str, prompt: str) -> str:
    normalized = normalize_shot(requested)
    if normalized != "auto":
        return normalized
    return detect_shot(prompt) or "full"


def split_tags(text: str) -> list[str]:
    return [tag.strip() for tag in text.split(",") if tag.strip()]


def join_tag_parts(*parts: str) -> str:
    return ", ".join(part.strip(" ,") for part in parts if part.strip(" ,"))


def replace_card_layer(
    card: CharacterCard,
    layer: str,
    positive: str,
    negative: str = "",
) -> CharacterCard:
    if not card.is_layered:
        raise ValueError("该卡尚未分层，请先使用 /nai_card_relayer 人设名")
    normalized_layer = normalize_card_layer(layer)
    positive_layers = dict(card.positive_layers)
    negative_layers = dict(card.negative_layers)
    positive_layers[normalized_layer] = positive.strip()
    negative_layers[normalized_layer] = negative.strip()
    return CharacterCard(
        positive=join_tag_parts(*(positive_layers.get(part, "") for part in CARD_LAYERS)),
        negative=join_tag_parts(*(negative_layers.get(part, "") for part in CARD_LAYERS)),
        positive_layers=positive_layers,
        negative_layers=negative_layers,
    )
