from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Job:
    user_id: str
    state: JobState = JobState.QUEUED
    cancelled: asyncio.Event = field(default_factory=asyncio.Event)


class GenerationQueue:
    def __init__(self, concurrency: int = 1, max_size: int = 20) -> None:
        self.concurrency = max(1, concurrency)
        self.max_size = max(1, max_size)
        self._jobs: dict[str, Job] = {}
        self._waiting: deque[str] = deque()
        self._running = 0
        self._condition = asyncio.Condition()

    async def register(self, user_id: str) -> tuple[Job, int]:
        async with self._condition:
            existing = self._jobs.get(user_id)
            if existing and existing.state is not JobState.CANCELLED:
                raise ValueError("你已有一个生成任务，请等待完成或取消排队任务")
            if len(self._jobs) >= self.max_size:
                raise ValueError("生成队列已满，请稍后再试")
            job = Job(user_id=user_id)
            self._jobs[user_id] = job
            self._waiting.append(user_id)
            position = len(self._waiting)
            self._condition.notify_all()
            return job, position

    async def wait_turn(self, job: Job) -> bool:
        async with self._condition:
            while True:
                if job.cancelled.is_set():
                    self._remove_waiting(job.user_id)
                    job.state = JobState.CANCELLED
                    self._jobs.pop(job.user_id, None)
                    self._condition.notify_all()
                    return False
                is_first = bool(self._waiting) and self._waiting[0] == job.user_id
                if is_first and self._running < self.concurrency:
                    self._waiting.popleft()
                    self._running += 1
                    job.state = JobState.RUNNING
                    self._condition.notify_all()
                    return True
                await self._condition.wait()

    async def finish(self, job: Job) -> None:
        async with self._condition:
            if job.state is JobState.RUNNING:
                self._running = max(0, self._running - 1)
            self._remove_waiting(job.user_id)
            self._jobs.pop(job.user_id, None)
            self._condition.notify_all()

    async def cancel(self, user_id: str) -> str:
        async with self._condition:
            job = self._jobs.get(user_id)
            if not job:
                return "none"
            if job.state is JobState.RUNNING:
                return "running"
            job.cancelled.set()
            self._remove_waiting(user_id)
            job.state = JobState.CANCELLED
            self._jobs.pop(user_id, None)
            self._condition.notify_all()
            return "cancelled"

    async def status(self, user_id: str) -> tuple[str, int | None]:
        async with self._condition:
            job = self._jobs.get(user_id)
            if not job:
                return "none", None
            if job.state is JobState.RUNNING:
                return "running", None
            try:
                return "queued", list(self._waiting).index(user_id) + 1
            except ValueError:
                return job.state.value, None

    def _remove_waiting(self, user_id: str) -> None:
        try:
            self._waiting.remove(user_id)
        except ValueError:
            pass
