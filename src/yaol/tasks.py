import asyncio
from collections.abc import Coroutine
from typing import Any

from opentelemetry.context import Context

from yaol.context import attached, detached


def spawn[T](
    coro: Coroutine[Any, Any, T],
    *,
    context: Context | None = None,
    name: str | None = None,
) -> asyncio.Task[T]:
    if context is None:
        with detached():
            return asyncio.create_task(coro, name=name)

    with attached(context):
        return asyncio.create_task(coro, name=name)
