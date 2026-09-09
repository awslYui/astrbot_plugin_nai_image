from __future__ import annotations

import asyncio
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

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

    async def write_image(self, user_id: str, data: bytes, extension: str) -> Path:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S_%f")
        safe_user = "".join(char for char in user_id if char.isalnum())[:32] or "user"
        path = self.output_dir / f"nai_{safe_user}_{timestamp}{extension}"
        await asyncio.to_thread(path.write_bytes, data)
        return path.resolve()

    async def cleanup_outputs(self, retention_hours: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(hours=max(1, retention_hours))
        removed = 0
        for path in self.output_dir.glob("nai_*"):
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, UTC)
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
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        attempts = self._state["daily_attempts"]
        self._state["daily_attempts"] = {
            key: value for key, value in attempts.items() if key.startswith(today + ":")
        }

    @staticmethod
    def _daily_key(user_id: str) -> str:
        return f"{datetime.now(UTC).strftime('%Y-%m-%d')}:{user_id}"

