import logging
import logging.config
import sys
from typing import Any

import structlog

from yaol.config import ObservabilityConfig
from yaol.logs import build_handler
from yaol.processors import SHARED_PROCESSORS


def _renderer(config: ObservabilityConfig) -> Any:
    use_json = config.json_logs
    if use_json is None:
        use_json = not sys.stderr.isatty()
    if use_json:
        return structlog.processors.JSONRenderer()
    return structlog.dev.ConsoleRenderer()


def build_logging_config(config: ObservabilityConfig) -> dict[str, Any]:
    """Build a dictConfig payload wiring stdlib logging into structlog."""
    handlers: dict[str, Any] = {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stdout",
            "formatter": "structlog",
        },
    }
    active = ["console"]

    if config.export_logs:
        handlers["otlp"] = {
            "()": build_handler,
            "level": config.log_level,
        }
        active.append("otlp")

    loggers: dict[str, Any] = {
        "": {"handlers": active, "level": config.log_level, "propagate": False},
    }
    for name, level in config.logger_levels.items():
        loggers[name] = {"handlers": active, "level": level, "propagate": False}

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structlog": {
                "()": structlog.stdlib.ProcessorFormatter,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    _renderer(config),
                ],
                "foreign_pre_chain": SHARED_PROCESSORS,
            },
        },
        "handlers": handlers,
        "loggers": loggers,
    }


def setup_logging(config: ObservabilityConfig) -> None:
    """Configure structlog and the stdlib logging hierarchy."""
    structlog.configure(
        processors=[
            *SHARED_PROCESSORS,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.config.dictConfig(build_logging_config(config))
