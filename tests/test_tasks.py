import asyncio

from conftest import SpanCollector

from yaol.context import capture, span
from yaol.tasks import spawn


def test_spawn_without_context_starts_a_clean_trace(collector: SpanCollector) -> None:
    async def scenario() -> None:
        async def work() -> None:
            with span("worker"):
                pass

        with span("update"):
            task = spawn(work())
        await task

    asyncio.run(scenario())

    assert collector.named("worker").parent is None


def test_spawn_with_captured_context_continues_the_trace(
    collector: SpanCollector,
) -> None:
    async def scenario() -> None:
        async def work() -> None:
            with span("deferred"):
                pass

        with span("update"):
            task = spawn(work(), context=capture())
        await task

    asyncio.run(scenario())

    update = collector.named("update")
    deferred = collector.named("deferred")
    assert update.context is not None
    assert deferred.context is not None
    assert deferred.parent is not None
    assert deferred.parent.span_id == update.context.span_id
    assert deferred.context.trace_id == update.context.trace_id


def test_plain_create_task_would_inherit_the_caller(collector: SpanCollector) -> None:
    async def scenario() -> None:
        async def work() -> None:
            with span("inherited"):
                pass

        with span("update"):
            task = asyncio.create_task(work())
        await task

    asyncio.run(scenario())

    assert collector.named("inherited").parent is not None
