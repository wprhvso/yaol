from collections.abc import Generator, Mapping
from contextlib import contextmanager
from typing import Final

import structlog
from opentelemetry import trace
from opentelemetry.trace import Span
from opentelemetry.util.types import AttributeValue

UNKNOWN_TRACE_ID: Final = "unknown"

_tracer: Final = trace.get_tracer("yaol")


def current_trace_id() -> str:
    """Return the trace id of the active span, or a placeholder."""
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else UNKNOWN_TRACE_ID


def current_span_id() -> str:
    """Return the span id of the active span, or a placeholder."""
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.span_id, "016x") if ctx.is_valid else UNKNOWN_TRACE_ID


@contextmanager
def span(
    name: str,
    attributes: Mapping[str, AttributeValue] | None = None,
    *,
    bind_trace_id: bool = True,
) -> Generator[Span]:
    """Start a span and optionally bind its trace id into the structlog context."""
    with _tracer.start_as_current_span(name, attributes=attributes) as active:
        if not bind_trace_id:
            yield active
            return

        trace_id = format(active.get_span_context().trace_id, "032x")
        structlog.contextvars.bind_contextvars(trace_id=trace_id)
        try:
            yield active
        finally:
            structlog.contextvars.unbind_contextvars("trace_id")
