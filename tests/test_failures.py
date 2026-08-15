import structlog
from conftest import SpanCollector
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from yaol.context import span
from yaol.processors import SHARED_PROCESSORS, record_failures
from yaol.propagation import extract_context, inject_headers


def test_info_events_leave_the_span_alone(collector: SpanCollector) -> None:
    with span("work"):
        _ = record_failures(None, "info", {"event": "fine"})

    assert collector.named("work").status.status_code is not StatusCode.ERROR


def test_error_event_marks_the_span(collector: SpanCollector) -> None:
    with span("work"):
        _ = record_failures(None, "error", {"event": "update_handling_failed"})

    recorded = collector.named("work")
    assert recorded.status.status_code is StatusCode.ERROR
    assert recorded.status.description == "update_handling_failed"


def test_logged_exception_becomes_a_span_event(collector: SpanCollector) -> None:
    error = ValueError("boom")
    with span("work"):
        _ = record_failures(None, "exception", {"event": "failed", "exc_info": error})

    recorded = collector.named("work")
    assert [event.name for event in recorded.events] == ["exception"]
    assert recorded.status.status_code is StatusCode.ERROR


def test_exc_info_tuple_is_understood(collector: SpanCollector) -> None:
    error = ValueError("boom")
    with span("work"):
        _ = record_failures(
            None,
            "exception",
            {"event": "failed", "exc_info": (type(error), error, None)},
        )

    assert [event.name for event in collector.named("work").events] == ["exception"]


def test_exc_info_true_reads_the_live_exception(collector: SpanCollector) -> None:
    with span("work"):
        try:
            raise ValueError("boom")
        except ValueError:
            _ = record_failures(
                None, "exception", {"event": "failed", "exc_info": True}
            )

    assert [event.name for event in collector.named("work").events] == ["exception"]


def test_event_dict_is_passed_through_unchanged() -> None:
    event = {"event": "failed", "exc_info": True}
    assert record_failures(None, "error", event) is event


def test_processor_runs_before_exc_info_is_rendered() -> None:
    order = list(SHARED_PROCESSORS)
    assert order.index(record_failures) < order.index(
        structlog.processors.format_exc_info
    )


def test_headers_round_trip_the_trace() -> None:
    with span("outer") as outer:
        headers = inject_headers()

    restored = extract_context(dict(headers))
    assert (
        trace.get_current_span(restored).get_span_context().trace_id
        == outer.get_span_context().trace_id
    )
