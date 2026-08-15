from collections.abc import Iterator, Sequence

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)


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


_COLLECTOR = SpanCollector()


@pytest.fixture(scope="session", autouse=True)
def _provider() -> None:
    # A ProxyTracer caches the provider it resolves to on first use, so the
    # global provider has to be installed once for the whole session rather
    # than swapped per test.
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(_COLLECTOR))
    trace.set_tracer_provider(provider)


@pytest.fixture
def collector() -> Iterator[SpanCollector]:
    _COLLECTOR.spans.clear()
    yield _COLLECTOR
    _COLLECTOR.spans.clear()
