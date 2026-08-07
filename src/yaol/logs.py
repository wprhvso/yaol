import logging

from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from yaol.config import ObservabilityConfig

_provider: LoggerProvider | None = None


def setup_logs(config: ObservabilityConfig, resource: Resource) -> LoggerProvider:
    """Configure the global LoggerProvider with an OTLP gRPC exporter."""
    global _provider  # noqa: PLW0603

    provider = LoggerProvider(resource=resource)
    exporter = OTLPLogExporter(
        endpoint=config.otlp_endpoint, insecure=config.otlp_insecure
    )
    provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    set_logger_provider(provider)

    _provider = provider
    return provider


def build_handler(level: str) -> LoggingHandler:
    """Build a stdlib logging handler that forwards records over OTLP."""
    numeric = logging.getLevelNamesMapping().get(level.upper(), logging.NOTSET)
    return LoggingHandler(level=numeric, logger_provider=_provider)


def shutdown_logs(timeout_millis: int = 5000) -> None:
    """Flush pending log records and shut the provider down."""
    global _provider  # noqa: PLW0603

    if _provider is None:
        return
    _ = _provider.force_flush(timeout_millis)
    _provider.shutdown()
    _provider = None
