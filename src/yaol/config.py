import os
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

DEFAULT_OTLP_ENDPOINT: Final = "http://localhost:4317"
DEFAULT_PYROSCOPE_ADDRESS: Final = "http://localhost:4040"

_TRUTHY: Final = ("1", "true", "yes", "on")


@dataclass(frozen=True, slots=True)
class ObservabilityConfig:
    service_name: str
    service_version: str = "0.0.0"
    environment: str = "prod"
    otlp_endpoint: str = DEFAULT_OTLP_ENDPOINT
    otlp_insecure: bool = True
    log_level: str = "INFO"
    json_logs: bool | None = None
    logger_levels: Mapping[str, str] = field(default_factory=dict[str, str])
    export_logs: bool = True
    export_metrics: bool = True
    metric_interval_millis: int = 30000
    resource_attributes: Mapping[str, str] = field(default_factory=dict[str, str])
    profiling_enabled: bool = False
    pyroscope_address: str = DEFAULT_PYROSCOPE_ADDRESS
    pyroscope_sample_rate: int = 100
    pyroscope_oncpu: bool = True
    pyroscope_gil_only: bool = True
    pyroscope_report_pid: bool = False
    pyroscope_report_thread_id: bool = False
    pyroscope_tags: Mapping[str, str] = field(default_factory=dict[str, str])


def _flag(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUTHY


def _text(key: str, default: str) -> str:
    raw = os.environ.get(key)
    return raw or default


def _number(key: str, default: int) -> int:
    raw = os.environ.get(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _json_logs() -> bool | None:
    raw = os.environ.get("YAOL_JSON_LOGS")
    if raw is None:
        return None
    return raw.strip().lower() in _TRUTHY


def from_env(
    service_name: str,
    *,
    service_version: str = "0.0.0",
    environment: Literal["dev", "prod"] | str = "prod",  # noqa: PYI051
) -> ObservabilityConfig:
    return ObservabilityConfig(
        service_name=service_name,
        service_version=service_version,
        environment=_text("ENV", environment),
        otlp_endpoint=_text("OTEL_EXPORTER_OTLP_ENDPOINT", DEFAULT_OTLP_ENDPOINT),
        otlp_insecure=_flag("OTEL_EXPORTER_OTLP_INSECURE", default=True),
        log_level=_text("LOG_LEVEL", "INFO"),
        json_logs=_json_logs(),
        export_logs=_flag("YAOL_EXPORT_LOGS", default=True),
        export_metrics=_flag("YAOL_EXPORT_METRICS", default=True),
        metric_interval_millis=_number("YAOL_METRIC_INTERVAL_MILLIS", 30000),
        profiling_enabled=_flag("YAOL_PROFILING_ENABLED", default=False),
        pyroscope_address=_text("PYROSCOPE_ADDRESS", DEFAULT_PYROSCOPE_ADDRESS),
        pyroscope_sample_rate=_number("PYROSCOPE_SAMPLE_RATE", 100),
    )
