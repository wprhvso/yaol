import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from conftest import SpanCollector
from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

from yaol import extract_context, instrument_httpx, span

_SEEN: list[dict[str, str]] = []


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:
        _SEEN.append({key.lower(): value for key, value in self.headers.items()})
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        _ = self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002, ARG002
        return


@pytest.fixture
def upstream() -> Iterator[str]:
    _SEEN.clear()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}/ping"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        _SEEN.clear()


@pytest.fixture
def instrumented() -> Iterator[None]:
    instrument_httpx()
    yield
    HTTPXClientInstrumentor().uninstrument()


def test_client_calls_are_traced_and_propagated(
    upstream: str, instrumented: None, collector: SpanCollector
) -> None:
    with span("outer") as outer:
        response = httpx.get(upstream)
        expected = outer.get_span_context().trace_id

    assert response.status_code == 200
    assert "GET" in collector.names()

    carried = extract_context(_SEEN[0])
    assert trace.get_current_span(carried).get_span_context().trace_id == expected


def test_the_upstream_sees_the_client_span_as_its_parent(
    upstream: str, instrumented: None, collector: SpanCollector
) -> None:
    with span("outer"):
        _ = httpx.get(upstream)

    client_span = collector.named("GET")
    carried = extract_context(_SEEN[0])
    assert client_span.context is not None
    assert (
        trace.get_current_span(carried).get_span_context().span_id
        == client_span.context.span_id
    )


def test_uninstrumented_clients_send_no_trace_headers(upstream: str) -> None:
    with span("outer"):
        _ = httpx.get(upstream)

    assert "traceparent" not in _SEEN[0]
