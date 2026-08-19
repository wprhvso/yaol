from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

log = structlog.get_logger("yaol")


def instrument_sqlalchemy(engine: "AsyncEngine") -> None:
    from opentelemetry.instrumentation.sqlalchemy import (
        SQLAlchemyInstrumentor,
    )

    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)


def instrument_aiohttp() -> None:
    from opentelemetry.instrumentation.aiohttp_client import (
        AioHttpClientInstrumentor,
    )

    AioHttpClientInstrumentor().instrument()


def instrument_httpx() -> None:
    from opentelemetry.instrumentation.httpx import (
        HTTPXClientInstrumentor,
    )

    HTTPXClientInstrumentor().instrument()


def instrument_fastapi(app: "FastAPI", **kwargs: Any) -> None:
    from opentelemetry.instrumentation.fastapi import (
        FastAPIInstrumentor,
    )

    FastAPIInstrumentor.instrument_app(app, **kwargs)


def instrument_redis() -> None:
    from opentelemetry.instrumentation.redis import (
        RedisInstrumentor,
    )

    RedisInstrumentor().instrument()


def instrument_asyncpg() -> None:
    from opentelemetry.instrumentation.asyncpg import (
        AsyncPGInstrumentor,
    )

    AsyncPGInstrumentor().instrument()


def instrument_runtime() -> None:
    from opentelemetry.instrumentation.system_metrics import (
        SystemMetricsInstrumentor,
    )

    SystemMetricsInstrumentor().instrument()
