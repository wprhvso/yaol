import sys
from typing import Final

import structlog
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from structlog.types import EventDict, Processor, WrappedLogger

_FAILURE_METHODS: Final = frozenset({"error", "critical", "exception", "fatal"})


def inject_otel_vars(
    _logger: WrappedLogger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


def _exception_of(event_dict: EventDict) -> BaseException | None:
    exc_info = event_dict.get("exc_info")

    if isinstance(exc_info, BaseException):
        return exc_info
    if isinstance(exc_info, tuple):
        error = exc_info[1]
        return error if isinstance(error, BaseException) else None
    if exc_info:
        return sys.exc_info()[1]
    return None


def record_failures(
    _logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    if method_name not in _FAILURE_METHODS:
        return event_dict

    span = trace.get_current_span()
    if not span.is_recording():
        return event_dict

    event = event_dict.get("event")
    description = event if isinstance(event, str) else method_name

    error = _exception_of(event_dict)
    if error is not None:
        span.record_exception(error, attributes={"log.event": description})

    span.set_status(Status(StatusCode.ERROR, description))
    return event_dict


SHARED_PROCESSORS: Final[list[Processor]] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.stdlib.ExtraAdder(),
    inject_otel_vars,
    record_failures,
    structlog.processors.TimeStamper(fmt="iso"),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
    structlog.processors.UnicodeDecoder(),
]
