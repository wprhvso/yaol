from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from yaol.config import ObservabilityConfig

_provider: TracerProvider | None = None


def setup_tracing(config: ObservabilityConfig, resource: Resource) -> TracerProvider:
    """Configure the global TracerProvider with an OTLP gRPC exporter."""
    global _provider  # noqa: PLW0603

    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(
        endpoint=config.otlp_endpoint, insecure=config.otlp_insecure
    )
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    _provider = provider
    return provider


def shutdown_tracing(timeout_millis: int = 5000) -> None:
    """Flush pending spans and shut the provider down."""
    global _provider  # noqa: PLW0603

    if _provider is None:
        return
    _ = _provider.force_flush(timeout_millis)
    _provider.shutdown()
    _provider = None
