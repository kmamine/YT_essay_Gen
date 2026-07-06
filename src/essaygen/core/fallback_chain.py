import time
from dataclasses import dataclass
from typing import Any, Callable

from essaygen.core.errors import (
    FatalError,
    QuotaExhaustedError,
    RateLimitError,
    TransientError,
)
from essaygen.core.retry import backoff_delay


class AllTiersExhaustedError(FatalError):
    pass


@dataclass
class Tier:
    name: str
    call: Callable[[], Any]


def run_with_fallback(
    tiers: list[Tier],
    retries: dict[str, int] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[Any, str]:
    retries = retries or {}
    last_exc: Exception | None = None

    for tier in tiers:
        max_attempts = retries.get(tier.name, 1)
        attempt = 0
        while attempt < max_attempts:
            attempt += 1
            try:
                return tier.call(), tier.name
            except QuotaExhaustedError as exc:
                last_exc = exc
                break
            except FatalError as exc:
                last_exc = exc
                break
            except (RateLimitError, TransientError) as exc:
                last_exc = exc
                if attempt >= max_attempts:
                    break
                sleep(backoff_delay(attempt - 1))

    raise AllTiersExhaustedError(f"all tiers exhausted: {last_exc}") from last_exc
