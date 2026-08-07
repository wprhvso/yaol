from yaol.config import ObservabilityConfig
from yaol.log_config import build_logging_config


def test_otlp_handler_is_optional() -> None:
    config = ObservabilityConfig(service_name="bot", export_logs=False)
    payload = build_logging_config(config)
    assert "otlp" not in payload["handlers"]
    assert payload["loggers"][""]["handlers"] == ["console"]


def test_logger_levels_are_applied() -> None:
    config = ObservabilityConfig(
        service_name="bot",
        logger_levels={"sqlalchemy.engine": "WARNING"},
    )
    payload = build_logging_config(config)
    assert payload["loggers"]["sqlalchemy.engine"]["level"] == "WARNING"
    assert "otlp" in payload["loggers"]["sqlalchemy.engine"]["handlers"]


def test_json_logs_flag_is_respected() -> None:
    payload = build_logging_config(
        ObservabilityConfig(service_name="bot", json_logs=True)
    )
    renderer = payload["formatters"]["structlog"]["processors"][1]
    assert type(renderer).__name__ == "JSONRenderer"
