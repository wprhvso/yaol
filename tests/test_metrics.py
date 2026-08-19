from typing import Any, cast

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from yaol import metrics
from yaol.config import ObservabilityConfig
from yaol.metrics import setup_metrics, shutdown_metrics


def _readers(provider: MeterProvider) -> list[Any]:
    return list(cast("Any", provider)._metric_readers)


def _resource() -> Resource:
    return Resource.create({SERVICE_NAME: "bot"})


def test_setup_registers_a_periodic_reader() -> None:
    provider = setup_metrics(ObservabilityConfig(service_name="bot"), _resource())
    readers = _readers(provider)

    assert len(readers) == 1
    assert isinstance(readers[0], PeriodicExportingMetricReader)


def test_interval_reaches_the_reader() -> None:
    config = ObservabilityConfig(service_name="bot", metric_interval_millis=1500)

    provider = setup_metrics(config, _resource())
    reader = _readers(provider)[0]

    assert isinstance(reader, PeriodicExportingMetricReader)
    assert reader._export_interval_millis == 1500


def test_resource_is_kept() -> None:
    provider = setup_metrics(ObservabilityConfig(service_name="bot"), _resource())

    assert provider._sdk_config.resource.attributes[SERVICE_NAME] == "bot"


def test_shutdown_without_setup_is_silent() -> None:
    shutdown_metrics(100)

    assert metrics._provider is None


def test_shutdown_is_idempotent() -> None:
    _ = setup_metrics(ObservabilityConfig(service_name="bot"), _resource())

    shutdown_metrics(100)
    shutdown_metrics(100)

    assert metrics._provider is None
