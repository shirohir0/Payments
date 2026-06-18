from collections import defaultdict
from threading import Lock

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest


class MetricsRegistry:
    """Process events; authoritative financial state is collected from PostgreSQL."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._counters: dict[str, int] = defaultdict(int)
        self.registry = CollectorRegistry()
        self.events = Counter(
            "payments_events",
            "Application events in this process",
            ["event"],
            registry=self.registry,
        )
        self.requests = Histogram(
            "payments_http_request_duration_seconds",
            "Request duration by route template",
            ["method", "route", "status"],
            registry=self.registry,
        )

    async def inc(self, name: str, value: int = 1) -> None:
        if value < 0:
            raise ValueError("Counters cannot decrease")
        with self._lock:
            self._counters[name] += value
        self.events.labels(event=name).inc(value)

    async def snapshot(self) -> dict[str, int]:
        with self._lock:
            return dict(self._counters)

    def render(self) -> bytes:
        return generate_latest(self.registry)


metrics = MetricsRegistry()
