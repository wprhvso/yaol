import pytest
import structlog
from conftest import SpanCollector
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import StatusCode

from yaol.context import span
from yaol.processors import SHARED_PROCESSORS, inject_otel_vars, record_failures


def test_no_span_leaves_event_untouched() -> None:
    event = {"event": "hello"}
    assert inject_otel_vars(None, "info", event) == {"event": "hello"}


def test_processor_is_registered_once() -> None:
    assert SHARED_PROCESSORS.count(inject_otel_vars) == 1


def test_trace_id_survives_a_non_recording_remote_span() -> None:
    remote = extract(
        {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
    )
    remote_span = trace.get_current_span(remote)
    assert not remote_span.is_recording()

    with trace.use_span(remote_span, end_on_exit=False):
        event = inject_otel_vars(None, "info", {"event": "hello"})

    assert event["trace_id"] == "0af7651916cd43dd8448eb211c80319c"


def test_ids_are_injected_inside_a_span() -> None:
    with span("work") as active:
        event = inject_otel_vars(None, "info", {"event": "hello"})
        context = active.get_span_context()

    assert event["trace_id"] == format(context.trace_id, "032x")
    assert event["span_id"] == format(context.span_id, "016x")


def test_existing_keys_are_kept() -> None:
    with span("work"):
        event = inject_otel_vars(None, "info", {"event": "hello", "user": 1})

    assert event["user"] == 1


@pytest.mark.parametrize("method", ["error", "critical", "exception", "fatal"])
def test_every_failure_method_marks_the_span(
    method: str, collector: SpanCollector
) -> None:
    with span("work"):
        _ = record_failures(None, method, {"event": "broken"})

    assert collector.named("work").status.status_code is StatusCode.ERROR


@pytest.mark.parametrize("method", ["info", "debug", "warning"])
def test_healthy_methods_leave_the_span_alone(
    method: str, collector: SpanCollector
) -> None:
    with span("work"):
        _ = record_failures(None, method, {"event": "fine"})

    assert collector.named("work").status.status_code is not StatusCode.ERROR


def test_a_missing_event_falls_back_to_the_method_name(
    collector: SpanCollector,
) -> None:
    with span("work"):
        _ = record_failures(None, "error", {})

    assert collector.named("work").status.description == "error"


def test_an_empty_exception_tuple_records_nothing(collector: SpanCollector) -> None:
    with span("work"):
        _ = record_failures(None, "error", {"exc_info": (None, None, None)})

    assert collector.named("work").events == ()


def test_contextvars_are_merged_first() -> None:
    assert SHARED_PROCESSORS[0] is structlog.contextvars.merge_contextvars


def test_the_renderer_is_not_part_of_the_shared_chain() -> None:
    assert not any(
        isinstance(processor, structlog.processors.JSONRenderer)
        for processor in SHARED_PROCESSORS
    )
