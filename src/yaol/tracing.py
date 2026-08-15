from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_ON,
    ParentBased,
    Sampler,
    TraceIdRatioBased,
)

from yaol.config import ObservabilityConfig

_provider: TracerProvider | None = None


def build_sampler(config: ObservabilityConfig) -> Sampler:
    """Build the sampler, keeping every trace unless a ratio is configured.

    The decision is parent-based so a sampled caller is never truncated halfway
    through: once the first service keeps a trace, every downstream service
    keeps its part of it too.
    """
    if config.trace_sample_ratio >= 1.0:
        return ParentBased(ALWAYS_ON)
    return ParentBased(TraceIdRatioBased(config.trace_sample_ratio))


def setup_tracing(config: ObservabilityConfig, resource: Resource) -> TracerProvider:
    """Configure the global TracerProvider with an OTLP gRPC exporter."""
    global _provider  # noqa: PLW0603

    provider = TracerProvider(resource=resource, sampler=build_sampler(config))
    if config.export_traces:
        exporter = OTLPSpanExporter(
            endpoint=config.otlp_endpoint, insecure=config.otlp_insecure
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                exporter,
                max_queue_size=config.span_queue_size,
                schedule_delay_millis=config.span_schedule_delay_millis,
                max_export_batch_size=config.span_export_batch_size,
            )
        )
    trace.set_tracer_provider(provider)

    _provider = provider
    return provider


def force_flush(timeout_millis: int = 5000) -> bool:
    """Push buffered spans to the collector without tearing the provider down.

    Worth calling before the process is about to die in a way ``shutdown`` will
    not survive, so the spans describing the crash are not lost with it.
    """
    if _provider is None:
        return False
    return _provider.force_flush(timeout_millis)


def shutdown_tracing(timeout_millis: int = 5000) -> None:
    """Flush pending spans and shut the provider down."""
    global _provider  # noqa: PLW0603

    if _provider is None:
        return
    _ = _provider.force_flush(timeout_millis)
    _provider.shutdown()
    _provider = None
