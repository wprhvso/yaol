from yaol.processors import SHARED_PROCESSORS, inject_otel_vars


def test_no_span_leaves_event_untouched() -> None:
    event = {"event": "hello"}
    assert inject_otel_vars(None, "info", event) == {"event": "hello"}


def test_processor_is_registered_once() -> None:
    assert SHARED_PROCESSORS.count(inject_otel_vars) == 1


def test_trace_id_survives_a_non_recording_remote_span() -> None:
    from opentelemetry import trace
    from opentelemetry.propagate import extract

    remote = extract(
        {"traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"}
    )
    span = trace.get_current_span(remote)
    assert not span.is_recording()

    with trace.use_span(span, end_on_exit=False):
        event = inject_otel_vars(None, "info", {"event": "hello"})

    assert event["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
