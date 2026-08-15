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
    """Inject OpenTelemetry trace and span IDs into the log event dictionary.

    Keyed on context validity rather than on ``is_recording()``: a span
    reconstructed from an incoming ``traceparent`` is a non-recording span, and
    gating on recording would drop the trace id from exactly the logs that need
    to be correlated with the caller's trace.
    """
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
    """Mirror error-level log events onto the active span.

    Handled exceptions are the ones that matter most and the ones a trace
    normally misses: the code logs them and carries on, so the span ends with an
    OK status and the backend shows a healthy trace for a failed request. Every
    ``log.exception`` and ``log.error`` therefore records an exception event and
    sets the span status to ERROR.

    Must run before ``format_exc_info``, which replaces ``exc_info`` with a
    rendered string.
    """
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
