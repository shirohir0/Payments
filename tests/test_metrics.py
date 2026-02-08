import pytest

from app.core.metrics import MetricsRegistry


@pytest.mark.asyncio
async def test_metrics_inc_and_snapshot():
    registry = MetricsRegistry()

    await registry.inc("a")
    await registry.inc("a", 2)
    await registry.inc("b", 5)

    snapshot = await registry.snapshot()

    assert snapshot["a"] == 3
    assert snapshot["b"] == 5
