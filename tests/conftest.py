import logging
from collections.abc import Iterator, Sequence

import pytest
import structlog
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from otlp_stub import Collector, running_collector

import yaol
from yaol import logs, metrics, profiling, tracing


class SpanCollector(SpanExporter):
    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None

    def named(self, name: str) -> ReadableSpan:
        return next(span for span in self.spans if span.name == name)

    def names(self) -> list[str]:
        return [span.name for span in self.spans]


class RoutingExporter(SpanExporter):
    def __init__(self) -> None:
        self.targets: list[SpanExporter] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for target in list(self.targets):
            _ = target.export(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        return None


_ROUTER = RoutingExporter()
_COLLECTOR = SpanCollector()


@pytest.fixture(scope="session", autouse=True)
def tracing_provider() -> Iterator[TracerProvider]:
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_ROUTER))
    trace.set_tracer_provider(provider)
    yield provider
    provider.shutdown()


@pytest.fixture
def collector() -> Iterator[SpanCollector]:
    _COLLECTOR.spans.clear()
    _ROUTER.targets.append(_COLLECTOR)
    yield _COLLECTOR
    _ROUTER.targets.remove(_COLLECTOR)
    _COLLECTOR.spans.clear()


@pytest.fixture
def span_router() -> RoutingExporter:
    return _ROUTER


@pytest.fixture
def otlp() -> Iterator[Collector]:
    with running_collector() as collector:
        yield collector


@pytest.fixture(autouse=True)
def provider_state() -> Iterator[None]:
    yield
    tracing.shutdown_tracing(1000)
    metrics.shutdown_metrics(1000)
    logs.shutdown_logs(1000)
    profiling._active = False
    yaol._configured = False


@pytest.fixture
def logging_state() -> Iterator[None]:
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    disabled = logging.root.manager.disable
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    logging.disable(disabled)
    structlog.reset_defaults()
