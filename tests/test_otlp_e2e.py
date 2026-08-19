import logging
from collections.abc import Iterator

import pytest
from conftest import RoutingExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.proto.trace.v1.trace_pb2 import Status
from otlp_stub import Collector

from yaol import build_resource
from yaol.config import ObservabilityConfig
from yaol.context import record_exception, span
from yaol.logs import build_handler, setup_logs, shutdown_logs
from yaol.metrics import setup_metrics
from yaol.tracing import setup_tracing


@pytest.fixture
def wired(otlp: Collector, span_router: RoutingExporter) -> Iterator[Collector]:
    exporter = OTLPSpanExporter(endpoint=otlp.endpoint, insecure=True)
    span_router.targets.append(exporter)
    yield otlp
    span_router.targets.remove(exporter)
    exporter.shutdown()


def _config(endpoint: str) -> ObservabilityConfig:
    return ObservabilityConfig(
        service_name="checkout",
        service_version="9.9.9",
        environment="test",
        otlp_endpoint=endpoint,
    )


def test_spans_travel_over_the_wire(wired: Collector) -> None:
    with span("checkout", {"order.id": 17}) as parent:
        expected = parent.get_span_context()
        with span("charge"):
            pass

    exported = wired.sink.span_named("checkout")
    child = wired.sink.span_named("charge")

    assert exported.trace_id.hex() == format(expected.trace_id, "032x")
    assert child.parent_span_id.hex() == format(expected.span_id, "016x")
    assert any(
        item.key == "order.id" and item.value.int_value == 17
        for item in exported.attributes
    )


def test_failures_travel_with_their_exception(wired: Collector) -> None:
    with span("checkout"):
        record_exception(ValueError("card declined"))

    exported = wired.sink.span_named("checkout")

    assert exported.status.code == Status.STATUS_CODE_ERROR
    assert exported.status.message == "ValueError"
    assert [event.name for event in exported.events] == ["exception"]


def test_configured_resource_travels_with_the_spans(otlp: Collector) -> None:
    config = _config(otlp.endpoint)
    provider = setup_tracing(config, build_resource(config))

    with provider.get_tracer("app").start_as_current_span("job"):
        pass
    _ = provider.force_flush(5000)

    attributes = otlp.sink.resource_attributes()
    assert otlp.sink.span_named("job").name == "job"
    assert attributes["service.name"] == "checkout"
    assert attributes["service.version"] == "9.9.9"
    assert attributes["deployment.environment"] == "test"


def test_dropped_spans_never_reach_the_collector(otlp: Collector) -> None:
    config = ObservabilityConfig(
        service_name="checkout",
        otlp_endpoint=otlp.endpoint,
        trace_sample_ratio=0.0,
    )
    provider = setup_tracing(config, build_resource(config))

    with provider.get_tracer("app").start_as_current_span("job"):
        pass
    _ = provider.force_flush(5000)

    assert otlp.sink.spans == []


def test_logs_travel_over_the_wire(otlp: Collector) -> None:
    config = _config(otlp.endpoint)
    _ = setup_logs(config, build_resource(config))
    logger = logging.getLogger("checkout.e2e")
    logger.propagate = False
    handler = build_handler("INFO")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    try:
        with span("job") as active:
            logger.warning("payment_retried")
            expected = format(active.get_span_context().trace_id, "032x")
    finally:
        logger.removeHandler(handler)

    shutdown_logs(5000)

    record = otlp.sink.log_with_body("payment_retried")
    assert record.severity_text == "WARNING"
    assert record.trace_id.hex() == expected
    assert otlp.sink.resource_attributes()["service.name"] == "checkout"


def test_metrics_travel_over_the_wire(otlp: Collector) -> None:
    config = _config(otlp.endpoint)
    provider = setup_metrics(config, build_resource(config))

    counter = provider.get_meter("app").create_counter("orders")
    counter.add(3)
    _ = provider.force_flush(5000)

    metric = otlp.sink.metric_named("orders")
    assert metric.sum.data_points[0].as_int == 3
    assert otlp.sink.resource_attributes()["service.name"] == "checkout"
