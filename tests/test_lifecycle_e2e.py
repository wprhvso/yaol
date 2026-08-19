import json
import logging

import pytest
import structlog
from otlp_stub import Collector

import yaol
from yaol import ObservabilityConfig, logs, metrics, setup, shutdown, span, tracing


def _config(endpoint: str) -> ObservabilityConfig:
    return ObservabilityConfig(
        service_name="checkout",
        service_version="9.9.9",
        environment="test",
        otlp_endpoint=endpoint,
        json_logs=True,
    )


def test_setup_ships_logs_and_shutdown_flushes_them(
    otlp: Collector, logging_state: None
) -> None:
    setup(_config(otlp.endpoint))

    with span("job") as active:
        structlog.get_logger("app").info("job_done", items=3)
        expected = format(active.get_span_context().trace_id, "032x")

    shutdown(5000)

    record = next(
        item for item in otlp.sink.log_records if "job_done" in item.body.string_value
    )
    payload = json.loads(record.body.string_value)
    assert payload["items"] == 3
    assert payload["logger"] == "app"
    assert record.severity_text == "INFO"
    assert record.trace_id.hex() == expected
    assert otlp.sink.resource_attributes()["service.name"] == "checkout"


def test_setup_is_refused_twice(
    otlp: Collector, logging_state: None, capsys: pytest.CaptureFixture[str]
) -> None:
    config = _config(otlp.endpoint)

    setup(config)
    handlers = list(logging.getLogger().handlers)
    setup(config)

    assert logging.getLogger().handlers == handlers
    assert "observability_already_configured" in capsys.readouterr().out


def test_setup_can_be_repeated_after_shutdown(
    otlp: Collector, logging_state: None
) -> None:
    config = _config(otlp.endpoint)

    setup(config)
    shutdown(1000)
    setup(config)

    assert yaol._configured is True

    shutdown(1000)
    assert yaol._configured is False


def test_shutdown_without_setup_is_silent() -> None:
    shutdown(1000)

    assert yaol._configured is False


def test_disabled_signals_are_not_wired(otlp: Collector, logging_state: None) -> None:
    config = ObservabilityConfig(
        service_name="checkout",
        otlp_endpoint=otlp.endpoint,
        export_logs=False,
        export_metrics=False,
        json_logs=True,
    )

    setup(config)

    assert logs._provider is None
    assert metrics._provider is None
    assert tracing._provider is not None
