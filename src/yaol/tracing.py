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
    if config.trace_sample_ratio >= 1.0:
        return ParentBased(ALWAYS_ON)
    return ParentBased(TraceIdRatioBased(config.trace_sample_ratio))


def setup_tracing(config: ObservabilityConfig, resource: Resource) -> TracerProvider:
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
    if _provider is None:
        return False
    return _provider.force_flush(timeout_millis)


def shutdown_tracing(timeout_millis: int = 5000) -> None:
    global _provider  # noqa: PLW0603

    if _provider is None:
        return
    _ = _provider.force_flush(timeout_millis)
    _provider.shutdown()
    _provider = None
