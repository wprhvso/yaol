from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

from yaol import tracing
from yaol.config import ObservabilityConfig
from yaol.tracing import build_sampler, force_flush, setup_tracing, shutdown_tracing


def _resource() -> Resource:
    return Resource.create({SERVICE_NAME: "bot"})


def _processors(provider: TracerProvider) -> list[SpanProcessor]:
    return list(provider._active_span_processor._span_processors)


def test_full_sampling_never_drops() -> None:
    sampler = build_sampler(ObservabilityConfig(service_name="bot"))

    assert isinstance(sampler, ParentBased)
    assert sampler.get_description().startswith("ParentBased{root:AlwaysOnSampler")


def test_partial_sampling_uses_the_ratio() -> None:
    config = ObservabilityConfig(service_name="bot", trace_sample_ratio=0.25)
    sampler = build_sampler(config)

    assert isinstance(sampler, ParentBased)
    assert TraceIdRatioBased(0.25).get_description() in sampler.get_description()


def test_setup_attaches_a_batch_processor() -> None:
    config = ObservabilityConfig(service_name="bot")

    provider = setup_tracing(config, _resource())

    assert any(
        isinstance(processor, BatchSpanProcessor) for processor in _processors(provider)
    )


def test_export_can_be_disabled() -> None:
    config = ObservabilityConfig(service_name="bot", export_traces=False)

    provider = setup_tracing(config, _resource())

    assert _processors(provider) == []


def test_batch_settings_reach_the_processor() -> None:
    config = ObservabilityConfig(
        service_name="bot",
        span_queue_size=64,
        span_schedule_delay_millis=100,
        span_export_batch_size=8,
    )

    provider = setup_tracing(config, _resource())
    processor = next(
        item for item in _processors(provider) if isinstance(item, BatchSpanProcessor)
    )
    settings = processor._batch_processor

    assert settings._max_queue_size == 64
    assert settings._max_export_batch_size == 8
    assert settings._schedule_delay_millis == 100


def test_resource_is_kept() -> None:
    provider = setup_tracing(ObservabilityConfig(service_name="bot"), _resource())

    assert provider.resource.attributes[SERVICE_NAME] == "bot"


def test_flush_without_setup_is_false() -> None:
    shutdown_tracing(100)

    assert force_flush(100) is False


def test_flush_after_setup_is_true() -> None:
    _ = setup_tracing(
        ObservabilityConfig(service_name="bot", export_traces=False), _resource()
    )

    assert force_flush(1000) is True


def test_shutdown_is_idempotent() -> None:
    _ = setup_tracing(
        ObservabilityConfig(service_name="bot", export_traces=False), _resource()
    )

    shutdown_tracing(100)
    shutdown_tracing(100)

    assert tracing._provider is None
