from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

log = structlog.get_logger("yaol")


def instrument_sqlalchemy(engine: "AsyncEngine") -> None:
    """Add OpenTelemetry instrumentation to a SQLAlchemy AsyncEngine."""
    from opentelemetry.instrumentation.sqlalchemy import (
        SQLAlchemyInstrumentor,
    )

    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


def instrument_aiohttp() -> None:
    """Add OpenTelemetry instrumentation to the aiohttp client."""
    from opentelemetry.instrumentation.aiohttp_client import (
        AioHttpClientInstrumentor,
    )

    AioHttpClientInstrumentor().instrument()


def instrument_httpx() -> None:
    """Add OpenTelemetry instrumentation to the httpx client.

    Patches httpx globally, so clients built inside third-party SDKs — the
    OpenAI SDK among them — are covered without reaching into them.
    """
    from opentelemetry.instrumentation.httpx import (
        HTTPXClientInstrumentor,
    )

    HTTPXClientInstrumentor().instrument()


def instrument_fastapi(app: "FastAPI", **kwargs: Any) -> None:
    """Add OpenTelemetry instrumentation to a FastAPI application.

    The server span continues the caller's trace from the incoming
    ``traceparent`` header, which is what joins a client and a service into one
    trace.
    """
    from opentelemetry.instrumentation.fastapi import (
        FastAPIInstrumentor,
    )

    FastAPIInstrumentor.instrument_app(app, **kwargs)


def instrument_redis() -> None:
    """Add OpenTelemetry instrumentation to the redis client."""
    from opentelemetry.instrumentation.redis import (
        RedisInstrumentor,
    )

    RedisInstrumentor().instrument()


def instrument_asyncpg() -> None:
    """Add OpenTelemetry instrumentation to the asyncpg driver."""
    from opentelemetry.instrumentation.asyncpg import (
        AsyncPGInstrumentor,
    )

    AsyncPGInstrumentor().instrument()


def instrument_runtime() -> None:
    """Add OpenTelemetry instrumentation to Python runtime metrics."""
    from opentelemetry.instrumentation.system_metrics import (
        SystemMetricsInstrumentor,
    )

    SystemMetricsInstrumentor().instrument()
