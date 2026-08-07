from typing import Final

import structlog
from opentelemetry.sdk.resources import (
    DEPLOYMENT_ENVIRONMENT,
    SERVICE_NAME,
    SERVICE_VERSION,
    Resource,
)

from yaol.config import (
    DEFAULT_OTLP_ENDPOINT,
    DEFAULT_PYROSCOPE_ADDRESS,
    ObservabilityConfig,
    from_env,
)
from yaol.context import UNKNOWN_TRACE_ID, current_span_id, current_trace_id, span
from yaol.instrument import (
    instrument_aiohttp,
    instrument_asyncpg,
    instrument_runtime,
    instrument_sqlalchemy,
)
from yaol.log_config import build_logging_config, setup_logging
from yaol.logs import setup_logs, shutdown_logs
from yaol.metrics import setup_metrics, shutdown_metrics
from yaol.processors import SHARED_PROCESSORS, inject_otel_vars
from yaol.profiling import setup_profiling, shutdown_profiling
from yaol.tracing import setup_tracing, shutdown_tracing

__all__ = [
    "DEFAULT_OTLP_ENDPOINT",
    "DEFAULT_PYROSCOPE_ADDRESS",
    "SHARED_PROCESSORS",
    "UNKNOWN_TRACE_ID",
    "ObservabilityConfig",
    "build_logging_config",
    "current_span_id",
    "current_trace_id",
    "from_env",
    "inject_otel_vars",
    "instrument_aiohttp",
    "instrument_asyncpg",
    "instrument_runtime",
    "instrument_sqlalchemy",
    "setup",
    "shutdown",
    "span",
]

log: Final = structlog.get_logger("yaol")

_configured = False


def build_resource(config: ObservabilityConfig) -> Resource:
    """Build the OpenTelemetry resource describing this service."""
    attributes: dict[str, str] = {
        SERVICE_NAME: config.service_name,
        SERVICE_VERSION: config.service_version,
        DEPLOYMENT_ENVIRONMENT: config.environment,
        **dict(config.resource_attributes),
    }
    return Resource.create(attributes=attributes)


def setup(config: ObservabilityConfig) -> None:
    """Initialize tracing, metrics, logs, logging and profiling."""
    global _configured  # noqa: PLW0603

    if _configured:
        log.warning("observability_already_configured", service=config.service_name)
        return

    resource = build_resource(config)

    _ = setup_tracing(config, resource)
    if config.export_metrics:
        _ = setup_metrics(config, resource)
    if config.export_logs:
        _ = setup_logs(config, resource)

    setup_logging(config)
    _ = setup_profiling(config)

    _configured = True
    log.info(
        "observability_configured",
        service=config.service_name,
        version=config.service_version,
        endpoint=config.otlp_endpoint,
    )


def shutdown(timeout_millis: int = 5000) -> None:
    """Flush every signal and tear the providers down."""
    global _configured  # noqa: PLW0603

    shutdown_profiling()
    shutdown_tracing(timeout_millis)
    shutdown_metrics(timeout_millis)
    shutdown_logs(timeout_millis)

    _configured = False
