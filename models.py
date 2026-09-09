from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class GenerationMode(str, Enum):
    TEXT_TO_IMAGE = "text2img"
    IMAGE_TO_IMAGE = "img2img"
    PRECISE_REFERENCE = "precise_reference"
    VIBE_TRANSFER = "vibe_transfer"


class ReferenceType(str, Enum):
    CHARACTER = "character"
    STYLE = "style"
    CHARACTER_AND_STYLE = "character&style"


@dataclass(slots=True)
class CharacterPrompt:
    positive: str
    negative: str = ""
    x: float = 0.5
    y: float = 0.5


@dataclass(slots=True)
class GenerationRequest:
    prompt: str
    negative_prompt: str
    model: str
    width: int
    height: int
    steps: int
    scale: float
    sampler: str
    schedule: str
    seed: int
    quality_tags: bool = True
    mode: GenerationMode = GenerationMode.TEXT_TO_IMAGE
    source_image_b64: str | None = field(default=None, repr=False)
    strength: float = 0.6
    noise: float = 0.0
    reference_image_b64: str | None = field(default=None, repr=False)
    reference_type: ReferenceType = ReferenceType.CHARACTER_AND_STYLE
    reference_strength: float = 1.0
    reference_fidelity: float = 0.0
    vibe_strength: float = 0.6
    vibe_information: float = 1.0
    character_prompts: list[CharacterPrompt] = field(default_factory=list)

    def safe_dict(self) -> dict[str, Any]:
        """Return a persistable request without user-supplied image bytes."""
        data = asdict(self)
        data["mode"] = self.mode.value
        data["reference_type"] = self.reference_type.value
        data["source_image_b64"] = None
        data["reference_image_b64"] = None
        return data

    @classmethod
    def from_safe_dict(cls, data: dict[str, Any]) -> GenerationRequest:
        copied = dict(data)
        copied["mode"] = GenerationMode(copied.get("mode", "text2img"))
        copied["reference_type"] = ReferenceType(
            copied.get("reference_type", "character&style")
        )
        copied["character_prompts"] = [
            CharacterPrompt(**item)
            for item in copied.get("character_prompts", [])
            if isinstance(item, dict)
        ]
        return cls(**copied)


@dataclass(slots=True)
class GeneratedImage:
    data: bytes
    extension: str
    seed: int
    content_type: str


@dataclass(slots=True)
class AccountInfo:
    tier: int | None = None
    tier_name: str = "未知"
    active: bool | None = None
    anlas: int | None = None
    v5_usage_percent: int | None = None
    v5_next_percent_seconds: int | None = None


@dataclass(slots=True)
class ParsedCommand:
    request: GenerationRequest
    warnings: list[str] = field(default_factory=list)
