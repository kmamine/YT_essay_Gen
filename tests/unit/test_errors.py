import pytest

from essaygen.core.errors import (
    EssaygenError,
    FatalError,
    QuotaExhaustedError,
    RateLimitError,
    RetryableError,
    TransientError,
)


@pytest.mark.parametrize("cls", [RateLimitError, QuotaExhaustedError, TransientError])
def test_retryable_subclasses_are_retryable_and_essaygen_errors(cls):
    err = cls("provider failed")

    assert isinstance(err, RetryableError)
    assert isinstance(err, EssaygenError)


def test_fatal_error_is_not_retryable():
    err = FatalError("bad api key")

    assert isinstance(err, EssaygenError)
    assert not isinstance(err, RetryableError)


def test_rate_limit_error_carries_optional_retry_after():
    err = RateLimitError("too many requests", retry_after_sec=30)

    assert err.retry_after_sec == 30
    assert str(err) == "too many requests"


def test_rate_limit_error_retry_after_defaults_to_none():
    err = RateLimitError("too many requests")

    assert err.retry_after_sec is None
