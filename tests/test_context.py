import pytest
from conftest import SpanCollector
from opentelemetry.trace import SpanKind, StatusCode

from yaol.context import (
    attached,
    capture,
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

    assert child_context.trace_id == parent_context.trace_id
    assert collector.named("deferred").parent is not None
    assert collector.named("deferred").parent.span_id == parent_context.span_id


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
    import asyncio

    async def scenario() -> None:
        async def slow() -> None:
            with span("slow"):
                await asyncio.sleep(10)

        task = asyncio.create_task(slow())
        await asyncio.sleep(0)
        _ = task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(scenario())

    recorded = collector.named("slow")
    assert recorded.status.status_code is StatusCode.ERROR
    assert recorded.status.description == "CancelledError"
    assert [event.name for event in recorded.events] == ["exception"]
