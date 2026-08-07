from yaol.processors import SHARED_PROCESSORS, inject_otel_vars


def test_no_span_leaves_event_untouched() -> None:
    event = {"event": "hello"}
    assert inject_otel_vars(None, "info", event) == {"event": "hello"}


def test_processor_is_registered_once() -> None:
    assert SHARED_PROCESSORS.count(inject_otel_vars) == 1
