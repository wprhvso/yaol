import sys
from typing import Any

import pyroscope
import pytest

from yaol import profiling
from yaol.config import ObservabilityConfig
from yaol.profiling import setup_profiling, shutdown_profiling


@pytest.fixture
def captured(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    calls: dict[str, Any] = {}

    def configure(**kwargs: Any) -> None:
        calls.update(kwargs)

    monkeypatch.setattr(pyroscope, "configure", configure)
    return calls


def test_disabled_profiling_does_nothing(captured: dict[str, Any]) -> None:
    assert setup_profiling(ObservabilityConfig(service_name="bot")) is False
    assert captured == {}
    assert profiling._active is False


def test_enabled_profiling_configures_the_agent(captured: dict[str, Any]) -> None:
    config = ObservabilityConfig(
        service_name="bot",
        service_version="1.2.3",
        environment="dev",
        profiling_enabled=True,
        pyroscope_address="http://pyroscope:4040",
        pyroscope_sample_rate=42,
        pyroscope_tags={"region": "eu"},
    )

    assert setup_profiling(config) is True
    assert profiling._active is True
    assert captured["application_name"] == "bot"
    assert captured["server_address"] == "http://pyroscope:4040"
    assert captured["sample_rate"] == 42
    assert captured["tags"] == {"env": "dev", "version": "1.2.3", "region": "eu"}


def test_custom_tags_cannot_be_dropped(captured: dict[str, Any]) -> None:
    config = ObservabilityConfig(
        service_name="bot",
        profiling_enabled=True,
        pyroscope_tags={"env": "override"},
    )

    assert setup_profiling(config) is True
    assert captured["tags"]["env"] == "override"


def test_agent_failure_is_survivable(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(**kwargs: Any) -> None:
        raise OSError("no route to host")

    monkeypatch.setattr(pyroscope, "configure", explode)
    config = ObservabilityConfig(service_name="bot", profiling_enabled=True)

    assert setup_profiling(config) is False
    assert profiling._active is False


def test_missing_package_is_survivable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "pyroscope", None)
    config = ObservabilityConfig(service_name="bot", profiling_enabled=True)

    assert setup_profiling(config) is False
    assert profiling._active is False


def test_shutdown_without_start_does_not_touch_the_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stopped: list[bool] = []
    monkeypatch.setattr(pyroscope, "shutdown", lambda: stopped.append(True))

    shutdown_profiling()

    assert stopped == []


def test_shutdown_stops_a_started_agent(
    monkeypatch: pytest.MonkeyPatch, captured: dict[str, Any]
) -> None:
    stopped: list[bool] = []
    monkeypatch.setattr(pyroscope, "shutdown", lambda: stopped.append(True))
    _ = setup_profiling(ObservabilityConfig(service_name="bot", profiling_enabled=True))

    shutdown_profiling()

    assert stopped == [True]
    assert profiling._active is False


def test_shutdown_failure_is_survivable(
    monkeypatch: pytest.MonkeyPatch, captured: dict[str, Any]
) -> None:
    def explode() -> None:
        raise RuntimeError("already gone")

    monkeypatch.setattr(pyroscope, "shutdown", explode)
    _ = setup_profiling(ObservabilityConfig(service_name="bot", profiling_enabled=True))

    shutdown_profiling()

    assert profiling._active is False
