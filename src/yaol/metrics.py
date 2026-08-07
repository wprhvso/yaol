from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from yaol.config import ObservabilityConfig

_provider: MeterProvider | None = None


def setup_metrics(config: ObservabilityConfig, resource: Resource) -> MeterProvider:
    """Configure the global MeterProvider with a periodic OTLP gRPC exporter."""
    global _provider  # noqa: PLW0603

    exporter = OTLPMetricExporter(
        endpoint=config.otlp_endpoint, insecure=config.otlp_insecure
    )
    reader = PeriodicExportingMetricReader(
        exporter, export_interval_millis=config.metric_interval_millis
    )
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)

    _provider = provider
    return provider


def shutdown_metrics(timeout_millis: int = 5000) -> None:
    """Flush pending metrics and shut the provider down."""
    global _provider  # noqa: PLW0603

    if _provider is None:
        return
    _ = _provider.force_flush(timeout_millis)
    _provider.shutdown(timeout_millis=timeout_millis)
    _provider = None
