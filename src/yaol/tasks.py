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
    """Create a task with an explicit trace context instead of an inherited one.

    ``asyncio`` copies the caller's context variables into every task, so a task
    created while a span is active silently adopts that span as its parent — for
    the whole lifetime of the task, not just the request that happened to create
    it. Pass ``context`` to continue a captured trace deliberately; leave it
    ``None`` to start the task from a clean context, which is what long-lived
    workers want.
    """
    if context is None:
        with detached():
            return asyncio.create_task(coro, name=name)

    with attached(context):
        return asyncio.create_task(coro, name=name)
