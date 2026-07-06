from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError

_TRANSIENT_KEYWORDS = ("timeout", "unavailable", "temporarily")
_RATE_LIMIT_KEYWORDS = ("rate limit", "too many requests")
_QUOTA_KEYWORDS = ("quota",)


def translate_provider_error(exc: Exception) -> Exception:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    message = str(exc)
    lowered = message.lower()

    # Quota keywords are checked first and independently of status code:
    # some providers (Google) reuse HTTP 429 for both true rate-limiting and
    # hard quota exhaustion, and the two need different fallback-chain
    # handling (retry-then-advance vs. advance-immediately-and-cache).
    if any(kw in lowered for kw in _QUOTA_KEYWORDS) or code == 403:
        return QuotaExhaustedError(message)
    if code == 429 or any(kw in lowered for kw in _RATE_LIMIT_KEYWORDS):
        return RateLimitError(message)
    if code in (500, 502, 503, 504) or any(kw in lowered for kw in _TRANSIENT_KEYWORDS):
        return TransientError(message)
    return FatalError(message)
