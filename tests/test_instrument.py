from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor

from yaol.instrument import instrument_fastapi, instrument_runtime


@pytest.fixture
def app() -> Iterator[FastAPI]:
    application = FastAPI()
    yield application
    if _instrumented(application):
        FastAPIInstrumentor.uninstrument_app(application)


def _instrumented(app: FastAPI) -> bool:
    return getattr(app, "_is_instrumented_by_opentelemetry", False) is True


def test_fastapi_app_is_instrumented(app: FastAPI) -> None:
    instrument_fastapi(app)

    assert _instrumented(app) is True


def test_fastapi_keyword_arguments_are_forwarded(app: FastAPI) -> None:
    instrument_fastapi(app, excluded_urls="health")

    assert _instrumented(app) is True


def test_runtime_metrics_can_be_switched_on_and_off() -> None:
    instrumentor = SystemMetricsInstrumentor()
    try:
        instrument_runtime()
        assert instrumentor.is_instrumented_by_opentelemetry is True
    finally:
        instrumentor.uninstrument()

    assert instrumentor.is_instrumented_by_opentelemetry is False


def test_runtime_metrics_can_leave_out_the_host_wide_ones() -> None:
    instrumentor = SystemMetricsInstrumentor()
    default = set(instrumentor._config)
    try:
        instrument_runtime(system_metrics=False)
        collected = set(instrumentor._config)

        assert instrumentor.is_instrumented_by_opentelemetry is True
        assert collected != default
        assert any(name.startswith("system.") for name in default)
        assert not any(name.startswith("system.") for name in collected)
        assert "process.runtime.cpu.time" in collected
    finally:
        instrumentor.uninstrument()


def test_aiohttp_client_can_be_instrumented() -> None:
    _ = pytest.importorskip("aiohttp")
    from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor

    from yaol.instrument import instrument_aiohttp

    instrumentor = AioHttpClientInstrumentor()
    try:
        instrument_aiohttp()
        assert instrumentor.is_instrumented_by_opentelemetry is True
    finally:
        instrumentor.uninstrument()


def test_redis_can_be_instrumented() -> None:
    _ = pytest.importorskip("redis")
    from opentelemetry.instrumentation.redis import RedisInstrumentor

    from yaol.instrument import instrument_redis

    instrumentor = RedisInstrumentor()
    try:
        instrument_redis()
        assert instrumentor.is_instrumented_by_opentelemetry is True
    finally:
        instrumentor.uninstrument()


def test_asyncpg_can_be_instrumented() -> None:
    _ = pytest.importorskip("asyncpg")
    from opentelemetry.instrumentation.asyncpg import AsyncPGInstrumentor

    from yaol.instrument import instrument_asyncpg

    instrumentor = AsyncPGInstrumentor()
    try:
        instrument_asyncpg()
        assert instrumentor.is_instrumented_by_opentelemetry is True
    finally:
        instrumentor.uninstrument()
