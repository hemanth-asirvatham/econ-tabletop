from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def gather_with_concurrency(limit: int, tasks: list[Callable[[], Awaitable[T]]]) -> list[T]:
    semaphore = asyncio.Semaphore(limit)

    async def _run(task: Callable[[], Awaitable[T]]) -> T:
        async with semaphore:
            return await task()

    return await asyncio.gather(*[_run(task) for task in tasks])
