import asyncio
import contextlib
from collections.abc import Generator

import pytest
import structlog
from conftest import SpanCollector
from opentelemetry.trace import SpanKind, StatusCode

from yaol.context import (
    UNKNOWN_TRACE_ID,
    attached,
    capture,
    current_span_id,
    current_trace_id,
    detached,
    fail,
    link,
    links,
    record_exception,
    span,
)


def test_escaping_exception_marks_the_span(collector: SpanCollector) -> None:
    with pytest.raises(ValueError, match="boom"), span("work"):
        raise ValueError("boom")

    recorded = collector.named("work")
    assert recorded.status.status_code is StatusCode.ERROR
    assert [event.name for event in recorded.events] == ["exception"]


def test_handled_exception_still_marks_the_span(collector: SpanCollector) -> None:
    with span("work"):
        try:
            raise ValueError("boom")
        except ValueError as error:
            record_exception(error)

    recorded = collector.named("work")
    assert recorded.status.status_code is StatusCode.ERROR
    assert [event.name for event in recorded.events] == ["exception"]


def test_fail_marks_the_span_without_an_exception(collector: SpanCollector) -> None:
    with span("work"):
        fail("upstream said no")

    recorded = collector.named("work")
    assert recorded.status.status_code is StatusCode.ERROR
    assert recorded.status.description == "upstream said no"
    assert recorded.events == ()


def test_captured_context_continues_the_trace_after_the_parent_ends(
    collector: SpanCollector,
) -> None:
    with span("update") as parent:
        captured = capture()
        parent_context = parent.get_span_context()

    with attached(captured), span("deferred") as child:
        child_context = child.get_span_context()

    deferred = collector.named("deferred")
    assert child_context.trace_id == parent_context.trace_id
    assert deferred.parent is not None
    assert deferred.parent.span_id == parent_context.span_id


def test_detached_starts_a_fresh_trace(collector: SpanCollector) -> None:
    with span("update") as parent:
        parent_trace = parent.get_span_context().trace_id
        with detached(), span("worker") as worker:
            assert worker.get_span_context().trace_id != parent_trace

    assert collector.named("worker").parent is None


def test_attached_none_is_a_noop() -> None:
    with span("outer"):
        before = current_trace_id()
        with attached(None):
            assert current_trace_id() == before


def test_span_links_point_at_captured_contexts(collector: SpanCollector) -> None:
    with span("first") as first:
        first_context = capture()
        first_span = first.get_span_context()
    with span("second") as second:
        second_context = capture()
        second_span = second.get_span_context()

    with span("batch", span_links=links([first_context, second_context])):
        pass

    linked = {item.context.span_id for item in collector.named("batch").links}
    assert linked == {first_span.span_id, second_span.span_id}


def test_link_of_empty_context_is_none() -> None:
    assert link(None) is None
    with detached():
        assert link(capture()) is None


def test_span_kind_and_attributes_are_recorded(collector: SpanCollector) -> None:
    with span("serve", {"update.id": 7}, kind=SpanKind.SERVER):
        pass

    recorded = collector.named("serve")
    assert recorded.kind is SpanKind.SERVER
    assert recorded.attributes is not None
    assert recorded.attributes["update.id"] == 7


def test_cancellation_marks_the_span(collector: SpanCollector) -> None:
    async def scenario() -> None:
        async def slow() -> None:
            with span("slow"):
                await asyncio.sleep(10)

        task = asyncio.create_task(slow())
        await asyncio.sleep(0)
        _ = task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(scenario())

    recorded = collector.named("slow")
    assert recorded.status.status_code is StatusCode.ERROR
    assert recorded.status.description == "CancelledError"
    assert [event.name for event in recorded.events] == ["exception"]


def test_abandoning_a_generator_is_not_an_error(collector: SpanCollector) -> None:
    def stream() -> Generator[int]:
        with span("stream"):
            yield 1
            yield 2

    generator = stream()
    assert next(generator) == 1
    generator.close()

    assert collector.named("stream").status.status_code is not StatusCode.ERROR


def test_ids_are_unknown_outside_a_span() -> None:
    with detached():
        assert current_trace_id() == UNKNOWN_TRACE_ID
        assert current_span_id() == UNKNOWN_TRACE_ID


def test_ids_are_hex_of_the_active_span() -> None:
    with span("work") as active:
        context = active.get_span_context()
        assert current_trace_id() == format(context.trace_id, "032x")
        assert current_span_id() == format(context.span_id, "016x")


def test_trace_id_is_bound_for_logging() -> None:
    with span("work") as active:
        bound = structlog.contextvars.get_contextvars()
        assert bound["trace_id"] == format(active.get_span_context().trace_id, "032x")

    assert "trace_id" not in structlog.contextvars.get_contextvars()


def test_nested_span_leaves_the_outer_trace_id_bound() -> None:
    with span("outer") as outer:
        expected = format(outer.get_span_context().trace_id, "032x")
        with span("inner"):
            pass
        assert structlog.contextvars.get_contextvars()["trace_id"] == expected


def test_binding_can_be_disabled() -> None:
    with span("work", bind_trace_id=False):
        assert "trace_id" not in structlog.contextvars.get_contextvars()


def test_trace_id_is_unbound_when_the_span_fails() -> None:
    with pytest.raises(ValueError, match="boom"), span("work"):
        raise ValueError("boom")

    assert "trace_id" not in structlog.contextvars.get_contextvars()


def test_nested_spans_share_the_trace(collector: SpanCollector) -> None:
    with span("outer") as outer, span("inner") as inner:
        assert inner.get_span_context().trace_id == outer.get_span_context().trace_id
        outer_id = outer.get_span_context().span_id

    recorded = collector.named("inner")
    assert recorded.parent is not None
    assert recorded.parent.span_id == outer_id


def test_record_exception_outside_a_span_is_silent() -> None:
    with detached():
        record_exception(ValueError("boom"))
        fail("nothing to mark")


def test_record_exception_carries_attributes(collector: SpanCollector) -> None:
    with span("work"):
        record_exception(ValueError("boom"), attributes={"retry": 2})

    event = collector.named("work").events[0]
    assert event.attributes is not None
    assert event.attributes["retry"] == 2


def test_escaping_exception_type_is_the_status_description(
    collector: SpanCollector,
) -> None:
    with pytest.raises(KeyError), span("work"):
        raise KeyError("missing")

    assert collector.named("work").status.description == "KeyError"


def test_explicit_context_parents_the_span(collector: SpanCollector) -> None:
    with span("first") as first:
        captured = capture()
        parent = first.get_span_context()

    with detached(), span("second", context=captured):
        pass

    recorded = collector.named("second")
    assert recorded.parent is not None
    assert recorded.parent.span_id == parent.span_id


def test_links_of_an_empty_iterable_is_empty() -> None:
    assert links([]) == []


def test_links_drop_invalid_contexts() -> None:
    with detached():
        empty = capture()
    with span("first"):
        real = capture()

    assert len(links([empty, real])) == 1


def test_link_survives_a_captured_context() -> None:
    with span("first") as first:
        built = link(capture())

    assert built is not None
    assert built.context.span_id == first.get_span_context().span_id


def test_attached_restores_the_previous_context() -> None:
    with span("outer") as outer:
        with detached(), span("worker"):
            pass
        assert current_trace_id() == format(outer.get_span_context().trace_id, "032x")


def test_cancellation_of_the_awaiting_task_is_recorded_once(
    collector: SpanCollector,
) -> None:
    async def scenario() -> None:
        with span("outer"):
            task = asyncio.create_task(asyncio.sleep(10))
            _ = task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    asyncio.run(scenario())

    assert collector.named("outer").status.status_code is not StatusCode.ERROR
