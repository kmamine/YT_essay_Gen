import time
from typing import Callable


class TokenBucket:
    def __init__(
        self,
        rate_per_min: float,
        capacity: float | None = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.rate_per_sec = rate_per_min / 60
        self.capacity = capacity if capacity is not None else rate_per_min
        self.clock = clock
        self.tokens = self.capacity
        self._last_check = clock()

    def _refill(self) -> None:
        now = self.clock()
        elapsed = now - self._last_check
        self._last_check = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate_per_sec)

    def try_acquire(self, tokens: float = 1) -> bool:
        self._refill()
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def time_until_available(self, tokens: float = 1) -> float:
        self._refill()
        if self.tokens >= tokens:
            return 0.0
        deficit = tokens - self.tokens
        return deficit / self.rate_per_sec


def backoff_delay(attempt: int, base: float = 1.0, max_delay: float = 60.0) -> float:
    return min(base * (2**attempt), max_delay)
