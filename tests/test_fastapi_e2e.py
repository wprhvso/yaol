from collections.abc import Iterator

import pytest
from conftest import SpanCollector
from fastapi import FastAPI
from fastapi.testclient import TestClient
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import StatusCode

from yaol import current_span_id, current_trace_id, instrument_fastapi, span

_TRACEPARENT = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
_REMOTE_TRACE = "0af7651916cd43dd8448eb211c80319c"
_REMOTE_SPAN = "b7ad6b7169203331"


async def _work() -> dict[str, str]:
    with span("work.inner"):
        return {"trace_id": current_trace_id(), "span_id": current_span_id()}


async def _broken() -> dict[str, str]:
    raise RuntimeError("nothing works")


def _build() -> FastAPI:
    app = FastAPI()
    app.add_api_route("/work", _work, methods=["GET"])
    app.add_api_route("/broken", _broken, methods=["GET"])
    return app


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = _build()
    instrument_fastapi(app)
    with TestClient(app, raise_server_exceptions=False) as started:
        yield started
    FastAPIInstrumentor.uninstrument_app(app)


def test_incoming_trace_is_continued(
    client: TestClient, collector: SpanCollector
) -> None:
    response = client.get("/work", headers={"traceparent": _TRACEPARENT})

    assert response.status_code == 200
    assert response.json()["trace_id"] == _REMOTE_TRACE

    server = collector.named("GET /work")
    assert server.parent is not None
    assert format(server.parent.span_id, "016x") == _REMOTE_SPAN
    assert server.attributes is not None
    assert 200 in [
        value for key, value in server.attributes.items() if key.endswith("status_code")
    ]


def test_application_spans_hang_under_the_server_span(
    client: TestClient, collector: SpanCollector
) -> None:
    _ = client.get("/work", headers={"traceparent": _TRACEPARENT})

    inner = collector.named("work.inner")
    server = collector.named("GET /work")
    assert inner.parent is not None
    assert server.context is not None
    assert inner.parent.span_id == server.context.span_id


def test_a_request_without_a_parent_starts_a_trace(
    client: TestClient, collector: SpanCollector
) -> None:
    response = client.get("/work")

    assert response.json()["trace_id"] != _REMOTE_TRACE
    assert collector.named("GET /work").parent is None


def test_failed_requests_are_marked(
    client: TestClient, collector: SpanCollector
) -> None:
    response = client.get("/broken")

    assert response.status_code == 500
    assert collector.named("GET /broken").status.status_code is StatusCode.ERROR
