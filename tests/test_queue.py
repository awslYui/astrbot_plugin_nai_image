import asyncio

import pytest
from astrbot_plugin_nai_image.queue_manager import GenerationQueue


@pytest.mark.asyncio
async def test_queue_serializes_jobs() -> None:
    queue = GenerationQueue(concurrency=1, max_size=3)
    first, first_position = await queue.register("1")
    second, second_position = await queue.register("2")
    assert first_position == 1
    assert second_position == 2
    assert await queue.wait_turn(first) is True

    waiter = asyncio.create_task(queue.wait_turn(second))
    await asyncio.sleep(0)
    assert not waiter.done()
    await queue.finish(first)
    assert await waiter is True
    await queue.finish(second)


@pytest.mark.asyncio
async def test_cancel_queued_job() -> None:
    queue = GenerationQueue(concurrency=1, max_size=3)
    first, _ = await queue.register("1")
    second, _ = await queue.register("2")
    await queue.wait_turn(first)
    assert await queue.cancel("2") == "cancelled"
    assert await queue.wait_turn(second) is False
    await queue.finish(first)


@pytest.mark.asyncio
async def test_rejects_duplicate_user_job() -> None:
    queue = GenerationQueue()
    await queue.register("1")
    with pytest.raises(ValueError):
        await queue.register("1")


@pytest.mark.asyncio
async def test_queue_starts_up_to_configured_concurrency() -> None:
    queue = GenerationQueue(concurrency=2, max_size=3)
    first, _ = await queue.register("1")
    second, _ = await queue.register("2")

    first_waiter = asyncio.create_task(queue.wait_turn(first))
    second_waiter = asyncio.create_task(queue.wait_turn(second))
    assert await asyncio.wait_for(first_waiter, timeout=0.1) is True
    assert await asyncio.wait_for(second_waiter, timeout=0.1) is True

    await queue.finish(first)
    await queue.finish(second)
