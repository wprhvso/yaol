from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
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
