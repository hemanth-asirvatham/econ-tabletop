from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")


async def gather_with_concurrency(
    limit: int,
    tasks: list[Callable[[], Awaitable[T]]],
    *,
    timeout: float | None = None,
    fallback: T | None = None,
) -> list[T]:
    semaphore = asyncio.Semaphore(limit)

    async def _run(task: Callable[[], Awaitable[T]]) -> T:
        async with semaphore:
            try:
                if timeout is not None and timeout > 0:
                    return await asyncio.wait_for(task(), timeout=timeout)
                return await task()
            except Exception:
                if fallback is not None:
                    return fallback
                raise

    return await asyncio.gather(*[_run(task) for task in tasks])
