import json
import logging
import sys
from typing import Any

import pytest
import structlog
from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.sdk.resources import Resource

from yaol.config import ObservabilityConfig
from yaol.context import span
from yaol.log_config import build_logging_config, setup_logging
from yaol.logs import setup_logs
from yaol.processors import SHARED_PROCESSORS


class _Stream:
    def __init__(self, tty: bool) -> None:
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        return None


def _renderer_of(payload: dict[str, Any]) -> Any:
    return payload["formatters"]["structlog"]["processors"][1]


def test_otlp_handler_is_optional() -> None:
    config = ObservabilityConfig(service_name="bot", export_logs=False)

    payload = build_logging_config(config)

    assert "otlp" not in payload["handlers"]
    assert payload["loggers"][""]["handlers"] == ["console"]


def test_otlp_handler_is_attached_to_the_root() -> None:
    payload = build_logging_config(ObservabilityConfig(service_name="bot"))

    assert payload["loggers"][""]["handlers"] == ["console", "otlp"]
    assert payload["handlers"]["console"]["stream"] == "ext://sys.stdout"


def test_log_level_reaches_the_root_and_the_exporter() -> None:
    config = ObservabilityConfig(service_name="bot", log_level="WARNING")

    payload = build_logging_config(config)

    assert payload["loggers"][""]["level"] == "WARNING"
    assert payload["handlers"]["otlp"]["level"] == "WARNING"


def test_logger_levels_are_applied() -> None:
    config = ObservabilityConfig(
        service_name="bot",
        logger_levels={"sqlalchemy.engine": "WARNING"},
    )

    payload = build_logging_config(config)

    assert payload["loggers"]["sqlalchemy.engine"]["level"] == "WARNING"
    assert "otlp" in payload["loggers"]["sqlalchemy.engine"]["handlers"]
    assert payload["loggers"]["sqlalchemy.engine"]["propagate"] is False


def test_shared_processors_run_for_foreign_records() -> None:
    payload = build_logging_config(ObservabilityConfig(service_name="bot"))

    assert payload["formatters"]["structlog"]["foreign_pre_chain"] is SHARED_PROCESSORS


def test_json_logs_flag_is_respected() -> None:
    payload = build_logging_config(
        ObservabilityConfig(service_name="bot", json_logs=True)
    )

    assert type(_renderer_of(payload)).__name__ == "JSONRenderer"


def test_console_logs_flag_is_respected() -> None:
    payload = build_logging_config(
        ObservabilityConfig(service_name="bot", json_logs=False)
    )

    assert type(_renderer_of(payload)).__name__ == "ConsoleRenderer"


@pytest.mark.parametrize(
    ("tty", "expected"), [(True, "ConsoleRenderer"), (False, "JSONRenderer")]
)
def test_renderer_follows_the_stream_that_logs_are_written_to(
    monkeypatch: pytest.MonkeyPatch, tty: bool, expected: str
) -> None:
    monkeypatch.setattr(sys, "stdout", _Stream(tty=tty))
    monkeypatch.setattr(sys, "stderr", _Stream(tty=not tty))

    payload = build_logging_config(ObservabilityConfig(service_name="bot"))

    assert type(_renderer_of(payload)).__name__ == expected


def test_setup_logging_emits_structured_lines(
    logging_state: None, capsys: pytest.CaptureFixture[str]
) -> None:
    config = ObservabilityConfig(service_name="bot", export_logs=False, json_logs=True)

    setup_logging(config)
    with span("work") as active:
        structlog.get_logger("app").info("hello", answer=42)
        expected = format(active.get_span_context().trace_id, "032x")

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["event"] == "hello"
    assert payload["answer"] == 42
    assert payload["logger"] == "app"
    assert payload["level"] == "info"
    assert payload["trace_id"] == expected
    assert payload["span_id"] != ""


def test_setup_logging_formats_records_from_plain_loggers(
    logging_state: None, capsys: pytest.CaptureFixture[str]
) -> None:
    config = ObservabilityConfig(service_name="bot", export_logs=False, json_logs=True)

    setup_logging(config)
    logging.getLogger("legacy").warning("old %s", "style")

    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["event"] == "old style"
    assert payload["level"] == "warning"


def test_setup_logging_honours_per_logger_levels(
    logging_state: None, capsys: pytest.CaptureFixture[str]
) -> None:
    config = ObservabilityConfig(
        service_name="bot",
        export_logs=False,
        json_logs=True,
        logger_levels={"noisy": "ERROR"},
    )

    setup_logging(config)
    logging.getLogger("noisy").info("ignored")
    logging.getLogger("noisy").error("kept")

    lines = capsys.readouterr().out.strip().splitlines()
    events = [json.loads(line)["event"] for line in lines]
    assert "ignored" not in events
    assert "kept" in events


def test_setup_logging_attaches_the_exporting_handler(logging_state: None) -> None:
    config = ObservabilityConfig(service_name="bot", json_logs=True)
    _ = setup_logs(config, Resource.create({}))

    setup_logging(config)

    assert any(
        isinstance(handler, LoggingHandler) for handler in logging.getLogger().handlers
    )


def test_exported_records_are_rendered_without_colours() -> None:
    payload = build_logging_config(
        ObservabilityConfig(service_name="bot", json_logs=False)
    )
    renderer = payload["formatters"]["otlp"]["processors"][1]

    assert payload["handlers"]["otlp"]["formatter"] == "otlp"
    assert type(renderer).__name__ == "JSONRenderer"
