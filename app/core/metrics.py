import asyncio
from collections import defaultdict


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._counters: dict[str, int] = defaultdict(int)

    async def inc(self, name: str, value: int = 1) -> None:
        async with self._lock:
            self._counters[name] += value

    async def snapshot(self) -> dict[str, int]:
        async with self._lock:
            return dict(self._counters)


metrics = MetricsRegistry()
