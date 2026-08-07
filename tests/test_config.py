import os
from collections.abc import Iterator

import pytest

from yaol.config import DEFAULT_OTLP_ENDPOINT, ObservabilityConfig, from_env

_KEYS = (
    "ENV",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "LOG_LEVEL",
    "YAOL_JSON_LOGS",
    "YAOL_EXPORT_LOGS",
    "YAOL_METRIC_INTERVAL_MILLIS",
    "YAOL_PROFILING_ENABLED",
)


@pytest.fixture(autouse=True)
def clean_env() -> Iterator[None]:
    saved = {key: os.environ.pop(key, None) for key in _KEYS}
    yield
    for key, value in saved.items():
        if value is not None:
            os.environ[key] = value
        else:
            _ = os.environ.pop(key, None)


def test_defaults_are_stable() -> None:
    config = ObservabilityConfig(service_name="bot")
    assert config.otlp_endpoint == DEFAULT_OTLP_ENDPOINT
    assert config.json_logs is None
    assert config.profiling_enabled is False


def test_from_env_reads_overrides() -> None:
    os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://172.17.0.1:4317"
    os.environ["ENV"] = "dev"
    os.environ["YAOL_PROFILING_ENABLED"] = "true"
    os.environ["YAOL_METRIC_INTERVAL_MILLIS"] = "5000"

    config = from_env("bot", service_version="1.2.3")

    assert config.otlp_endpoint == "http://172.17.0.1:4317"
    assert config.environment == "dev"
    assert config.profiling_enabled is True
    assert config.metric_interval_millis == 5000
    assert config.service_version == "1.2.3"


def test_invalid_number_falls_back() -> None:
    os.environ["YAOL_METRIC_INTERVAL_MILLIS"] = "not-a-number"
    assert from_env("bot").metric_interval_millis == 30000
