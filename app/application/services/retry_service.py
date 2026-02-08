import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


async def retry_with_backoff(
    operation: Callable[[], Awaitable[None]],
    *,
    max_attempts: int,
    base_delay: float,
) -> None:
    attempt = 0
    while True:
        try:
            await operation()
            return
        except Exception as exc:  # noqa: BLE001 - intentional retry wrapper
            attempt += 1
            if attempt >= max_attempts:
                logger.exception("Retry attempts exhausted", extra={"attempts": attempt})
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning(
                "Retrying operation",
                extra={"attempt": attempt, "delay": delay, "error": str(exc)},
            )
            await asyncio.sleep(delay)
