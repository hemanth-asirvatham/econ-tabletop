from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

from tqdm import tqdm

T = TypeVar("T")


async def gather_with_concurrency(
    limit: int,
    tasks: list[Callable[[], Awaitable[T]]],
    *,
    timeout: float | None = None,
    fallback: T | None = None,
    progress_desc: str | None = None,
) -> list[T]:
    if not tasks:
        return []

    semaphore = asyncio.Semaphore(limit)

    async def _run(idx: int, task: Callable[[], Awaitable[T]]) -> tuple[int, T]:
        async with semaphore:
            try:
                if timeout is not None and timeout > 0:
                    return idx, await asyncio.wait_for(task(), timeout=timeout)
                return idx, await task()
            except Exception:
                if fallback is not None:
                    return idx, fallback
                raise

    coros = [asyncio.create_task(_run(idx, task)) for idx, task in enumerate(tasks)]
    results: list[T | None] = [None] * len(tasks)

    if progress_desc:
        for coro in tqdm(asyncio.as_completed(coros), total=len(coros), desc=progress_desc):
            idx, value = await coro
            results[idx] = value
    else:
        for idx, value in await asyncio.gather(*coros):
            results[idx] = value

    return [value for value in results]
