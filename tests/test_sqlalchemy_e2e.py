from collections.abc import AsyncIterator

import pytest
from conftest import SpanCollector
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from yaol import instrument_sqlalchemy, span


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    _ = pytest.importorskip("aiosqlite")
    created = create_async_engine("sqlite+aiosqlite://")
    instrument_sqlalchemy(created)
    yield created
    SQLAlchemyInstrumentor().uninstrument()
    await created.dispose()


async def test_queries_become_child_spans(
    engine: AsyncEngine, collector: SpanCollector
) -> None:
    with span("checkout") as parent:
        async with engine.connect() as connection:
            result = await connection.execute(text("select 1"))
            value = result.scalar()
        expected = parent.get_span_context().span_id

    assert value == 1

    query = next(item for item in collector.spans if item.name.startswith("SELECT"))
    assert query.parent is not None
    assert query.parent.span_id == expected
    assert query.attributes is not None
    assert "select 1" in query.attributes.values()
