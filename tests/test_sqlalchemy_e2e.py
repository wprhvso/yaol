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
            result = await connection.execute(text("SELECT 1"))
            value = result.scalar()
        expected = parent.get_span_context().span_id

    assert value == 1

    queries = [item for item in collector.spans if item.name.startswith("SELECT")]
    assert [item.name for item in collector.spans] != []
    assert len(queries) == 1
    parent = queries[0].parent
    assert parent is not None
    assert parent.span_id == expected
    assert queries[0].attributes is not None
    assert "SELECT 1" in queries[0].attributes.values()
