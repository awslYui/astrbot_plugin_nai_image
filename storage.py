from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .character_cards import CharacterCard
from .models import GenerationRequest


class StateStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.output_dir = data_dir / "outputs"
        self.state_path = data_dir / "state.json"
        self._lock = asyncio.Lock()
        self._state: dict[str, Any] = {
            "last_requests": {},
            "daily_attempts": {},
            "character_cards": {},
            "health_modes": {},
            "statistics": {"attempted": 0, "succeeded": 0, "failed": 0},
        }
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self) -> None:
        if not self.state_path.exists():
            return
        try:
            loaded = json.loads(self.state_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                self._state.update(loaded)
        except (OSError, json.JSONDecodeError):
            # Keep a clean in-memory state. The malformed file is not overwritten
            # until the next successful state mutation.
            return

    async def daily_attempts(self, user_id: str) -> int:
        async with self._lock:
            self._prune_daily()
            return int(self._state["daily_attempts"].get(self._daily_key(user_id), 0))

    async def mark_attempt(self, user_id: str) -> None:
        async with self._lock:
            self._prune_daily()
            key = self._daily_key(user_id)
            attempts = self._state["daily_attempts"]
            attempts[key] = int(attempts.get(key, 0)) + 1
            self._state["statistics"]["attempted"] += 1
            await self._save_locked()

    async def mark_result(
        self, user_id: str, request: GenerationRequest, *, success: bool
    ) -> None:
        async with self._lock:
            stat_key = "succeeded" if success else "failed"
            self._state["statistics"][stat_key] += 1
            if success and request.mode.value == "text2img":
                self._state["last_requests"][user_id] = request.safe_dict()
            await self._save_locked()

    async def get_last_request(self, user_id: str) -> GenerationRequest | None:
        async with self._lock:
            data = self._state["last_requests"].get(user_id)
            if not isinstance(data, dict):
                return None
            try:
                return GenerationRequest.from_safe_dict(data)
            except (TypeError, ValueError):
                return None

    async def statistics(self) -> dict[str, int]:
        async with self._lock:
            return dict(self._state["statistics"])

    async def get_character_cards(self, user_id: str) -> dict[str, CharacterCard]:
        async with self._lock:
            cards = self._state["character_cards"].get(user_id, {})
            if not isinstance(cards, dict):
                return {}
            result: dict[str, CharacterCard] = {}
            for raw_name, raw_card in cards.items():
                name = str(raw_name).strip()
                if not name:
                    continue
                if isinstance(raw_card, str) and raw_card.strip():
                    result[name] = CharacterCard(positive=raw_card.strip())
                elif isinstance(raw_card, dict):
                    positive = str(
                        raw_card.get("positive", raw_card.get("tags", ""))
                    ).strip()
                    negative = str(raw_card.get("negative", "")).strip()
                    if positive:
                        result[name] = CharacterCard(positive, negative)
            return result

    async def set_character_card(
        self, user_id: str, name: str, card: CharacterCard, *, max_cards: int
    ) -> bool:
        async with self._lock:
            user_cards = self._state["character_cards"].setdefault(user_id, {})
            if not isinstance(user_cards, dict):
                user_cards = {}
                self._state["character_cards"][user_id] = user_cards
            is_new = name not in user_cards
            if is_new and len(user_cards) >= max(1, max_cards):
                raise ValueError(f"每位用户最多保存 {max(1, max_cards)} 张人设卡")
            user_cards[name] = {
                "positive": card.positive,
                "negative": card.negative,
            }
            await self._save_locked()
            return is_new

    async def delete_character_card(self, user_id: str, name: str) -> bool:
        async with self._lock:
            user_cards = self._state["character_cards"].get(user_id, {})
            if not isinstance(user_cards, dict) or name not in user_cards:
                return False
            del user_cards[name]
            await self._save_locked()
            return True

    async def get_health_mode(self, user_id: str, *, default: bool) -> bool:
        async with self._lock:
            value = self._state["health_modes"].get(user_id)
            return value if isinstance(value, bool) else default

    async def set_health_mode(self, user_id: str, enabled: bool) -> None:
        async with self._lock:
            self._state["health_modes"][user_id] = enabled
            await self._save_locked()

    async def write_image(self, user_id: str, data: bytes, extension: str) -> Path:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        safe_user = "".join(char for char in user_id if char.isalnum())[:32] or "user"
        path = self.output_dir / f"nai_{safe_user}_{timestamp}{extension}"
        await asyncio.to_thread(path.write_bytes, data)
        return path.resolve()

    async def cleanup_outputs(self, retention_hours: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, retention_hours))
        removed = 0
        for path in self.output_dir.glob("nai_*"):
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
                if modified < cutoff:
                    path.unlink()
                    removed += 1
            except OSError:
                continue
        return removed

    async def _save_locked(self) -> None:
        temp_path = self.state_path.with_suffix(".json.tmp")
        text = json.dumps(self._state, ensure_ascii=False, indent=2)
        await asyncio.to_thread(temp_path.write_text, text, encoding="utf-8")
        await asyncio.to_thread(os.replace, temp_path, self.state_path)

    def _prune_daily(self) -> None:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        attempts = self._state["daily_attempts"]
        self._state["daily_attempts"] = {
            key: value for key, value in attempts.items() if key.startswith(today + ":")
        }

    @staticmethod
    def _daily_key(user_id: str) -> str:
        return f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}:{user_id}"
