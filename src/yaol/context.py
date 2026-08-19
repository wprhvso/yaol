from collections.abc import Generator, Iterable, Mapping
from contextlib import contextmanager
from typing import Final

import structlog
from opentelemetry import context as context_api
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.trace import Link, Span, SpanKind, Status, StatusCode
from opentelemetry.util.types import AttributeValue

UNKNOWN_TRACE_ID: Final = "unknown"

_tracer: Final = trace.get_tracer("yaol")


def current_trace_id() -> str:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.trace_id, "032x") if ctx.is_valid else UNKNOWN_TRACE_ID


def current_span_id() -> str:
    ctx = trace.get_current_span().get_span_context()
    return format(ctx.span_id, "016x") if ctx.is_valid else UNKNOWN_TRACE_ID


def capture() -> Context:
    return context_api.get_current()


def link(context: Context | None) -> Link | None:
    if context is None:
        return None
    span_context = trace.get_current_span(context).get_span_context()
    return Link(span_context) if span_context.is_valid else None


def links(contexts: Iterable[Context]) -> list[Link]:
    return [built for context in contexts if (built := link(context)) is not None]


@contextmanager
def attached(context: Context | None) -> Generator[None]:
    if context is None:
        yield
        return

    token = context_api.attach(context)
    try:
        yield
    finally:
        context_api.detach(token)


@contextmanager
def detached() -> Generator[None]:
    token = context_api.attach(Context())
    try:
        yield
    finally:
        context_api.detach(token)


@contextmanager
def span(
    name: str,
    attributes: Mapping[str, AttributeValue] | None = None,
    *,
    kind: SpanKind = SpanKind.INTERNAL,
    context: Context | None = None,
    span_links: Iterable[Link] | None = None,
    bind_trace_id: bool = True,
) -> Generator[Span]:
    with _tracer.start_as_current_span(
        name,
        context=context,
        kind=kind,
        attributes=attributes,
        links=list(span_links) if span_links is not None else None,
        record_exception=False,
        set_status_on_exception=False,
    ) as active:
        bound = bind_trace_id and active.get_span_context().is_valid
        if bound:
            trace_id = format(active.get_span_context().trace_id, "032x")
            structlog.contextvars.bind_contextvars(trace_id=trace_id)
        try:
            yield active
        except GeneratorExit:
            raise
        except BaseException as error:
            active.record_exception(error, escaped=True)
            active.set_status(Status(StatusCode.ERROR, type(error).__name__))
            raise
        finally:
            if bound:
                structlog.contextvars.unbind_contextvars("trace_id")


def record_exception(
    error: BaseException,
    *,
    escaped: bool = False,
    attributes: Mapping[str, AttributeValue] | None = None,
) -> None:
    active = trace.get_current_span()
    if not active.is_recording():
        return
    active.record_exception(error, attributes=attributes, escaped=escaped)
    active.set_status(Status(StatusCode.ERROR, type(error).__name__))


def fail(description: str) -> None:
    active = trace.get_current_span()
    if active.is_recording():
        active.set_status(Status(StatusCode.ERROR, description))
