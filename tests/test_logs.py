import logging

from opentelemetry.sdk._logs import LoggingHandler
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

from yaol import logs
from yaol.config import ObservabilityConfig
from yaol.logs import build_handler, setup_logs, shutdown_logs


def _resource() -> Resource:
    return Resource.create({SERVICE_NAME: "bot"})


def test_setup_keeps_the_resource() -> None:
    provider = setup_logs(ObservabilityConfig(service_name="bot"), _resource())

    assert provider.resource.attributes[SERVICE_NAME] == "bot"


def test_handler_is_bound_to_the_provider() -> None:
    provider = setup_logs(ObservabilityConfig(service_name="bot"), _resource())

    handler = build_handler("INFO")

    assert isinstance(handler, LoggingHandler)
    assert handler._logger_provider is provider
    assert handler.level == logging.INFO


def test_handler_accepts_lowercase_levels() -> None:
    _ = setup_logs(ObservabilityConfig(service_name="bot"), _resource())

    assert build_handler("warning").level == logging.WARNING


def test_unknown_level_becomes_notset() -> None:
    _ = setup_logs(ObservabilityConfig(service_name="bot"), _resource())

    assert build_handler("loud").level == logging.NOTSET


def test_default_level_is_notset() -> None:
    _ = setup_logs(ObservabilityConfig(service_name="bot"), _resource())

    assert build_handler().level == logging.NOTSET


def test_shutdown_without_setup_is_silent() -> None:
    shutdown_logs(100)

    assert logs._provider is None


def test_shutdown_is_idempotent() -> None:
    _ = setup_logs(ObservabilityConfig(service_name="bot"), _resource())

    shutdown_logs(100)
    shutdown_logs(100)

    assert logs._provider is None
