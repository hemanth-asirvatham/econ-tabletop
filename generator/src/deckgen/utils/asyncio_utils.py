from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


def run_async(coro: Coroutine[Any, Any, T]) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        try:
            return asyncio.run(coro)
        except RuntimeError as exc:
            if "asyncio.run() cannot be called from a running event loop" in str(exc):
                return _run_async_in_thread(coro)
            raise
    return _run_async_in_thread(coro)


def _run_async_in_thread(coro: Coroutine[Any, Any, T]) -> T:
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()
