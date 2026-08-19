import asyncio

import pytest
from conftest import SpanCollector

from yaol.context import UNKNOWN_TRACE_ID, capture, current_trace_id, span
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


def test_spawn_returns_a_named_task() -> None:
    async def scenario() -> str | None:
        async def work() -> None:
            return None

        task = spawn(work(), name="worker")
        await task
        return task.get_name()

    assert asyncio.run(scenario()) == "worker"


def test_spawn_propagates_the_result() -> None:
    async def scenario() -> int:
        async def work() -> int:
            return 7

        return await spawn(work())

    assert asyncio.run(scenario()) == 7


def test_spawn_propagates_failures() -> None:
    async def scenario() -> None:
        async def work() -> None:
            raise ValueError("boom")

        await spawn(work())

    with pytest.raises(ValueError, match="boom"):
        asyncio.run(scenario())


def test_spawn_without_context_sees_no_ambient_trace() -> None:
    async def scenario() -> str:
        async def work() -> str:
            return current_trace_id()

        with span("update"):
            task = spawn(work())
        return await task

    assert asyncio.run(scenario()) == UNKNOWN_TRACE_ID


def test_a_context_captured_after_the_span_ended_still_parents_the_task(
    collector: SpanCollector,
) -> None:
    async def scenario() -> None:
        async def work() -> None:
            with span("deferred"):
                pass

        with span("update") as active:
            captured = capture()
            parent = active.get_span_context().span_id

        await spawn(work(), context=captured)
        deferred = collector.named("deferred")
        assert deferred.parent is not None
        assert deferred.parent.span_id == parent

    asyncio.run(scenario())
