from typing import TYPE_CHECKING, Any, Final

import structlog

if TYPE_CHECKING:
    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncEngine

log = structlog.get_logger("yaol")

_HOST_METRIC_PREFIX: Final = "system."


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


def instrument_runtime(*, system_metrics: bool = True) -> None:
    from opentelemetry.instrumentation.system_metrics import (
        _DEFAULT_CONFIG,
        SystemMetricsInstrumentor,
    )

    if system_metrics:
        SystemMetricsInstrumentor().instrument()
        return

    config: dict[str, list[str] | None] = {
        metric: labels
        for metric, labels in _DEFAULT_CONFIG.items()
        if not metric.startswith(_HOST_METRIC_PREFIX)
    }
    SystemMetricsInstrumentor(config=config).instrument()
