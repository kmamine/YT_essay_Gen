import pytest

from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError
from essaygen.core.fallback_chain import AllTiersExhaustedError, Tier, run_with_fallback


def make_tier(name, side_effects):
    """side_effects: list of exceptions to raise or a value to return, consumed in order."""
    calls = []

    def call():
        calls.append(name)
        effect = side_effects[len(calls) - 1]
        if isinstance(effect, Exception):
            raise effect
        return effect

    return Tier(name=name, call=call), calls


def test_first_tier_success_returns_result_and_tier_name():
    tier, calls = make_tier("nano_banana", ["image-bytes"])

    result, tier_name = run_with_fallback([tier])

    assert result == "image-bytes"
    assert tier_name == "nano_banana"
    assert calls == ["nano_banana"]


def test_rate_limit_retries_same_tier_before_advancing():
    sleeps = []
    tier1, calls1 = make_tier("nano_banana", [RateLimitError("429"), RateLimitError("429")])
    tier2, calls2 = make_tier("cloudflare_sdxl", ["fallback-bytes"])

    result, tier_name = run_with_fallback(
        [tier1, tier2], retries={"nano_banana": 2}, sleep=sleeps.append
    )

    assert result == "fallback-bytes"
    assert tier_name == "cloudflare_sdxl"
    assert calls1 == ["nano_banana", "nano_banana"]
    assert len(sleeps) == 1


def test_quota_exhausted_advances_immediately_without_retry():
    tier1, calls1 = make_tier("nano_banana", [QuotaExhaustedError("quota")])
    tier2, calls2 = make_tier("cloudflare_sdxl", ["fallback-bytes"])

    result, tier_name = run_with_fallback([tier1, tier2], retries={"nano_banana": 5})

    assert result == "fallback-bytes"
    assert calls1 == ["nano_banana"]


def test_transient_error_retries_then_advances():
    tier1, calls1 = make_tier("nano_banana", [TransientError("timeout"), TransientError("timeout")])
    tier2, calls2 = make_tier("cloudflare_sdxl", ["fallback-bytes"])

    result, tier_name = run_with_fallback(
        [tier1, tier2], retries={"nano_banana": 2}, sleep=lambda s: None
    )

    assert result == "fallback-bytes"
    assert calls1 == ["nano_banana", "nano_banana"]


def test_fatal_error_advances_immediately():
    tier1, calls1 = make_tier("nano_banana", [FatalError("bad request")])
    tier2, calls2 = make_tier("cloudflare_sdxl", ["fallback-bytes"])

    result, tier_name = run_with_fallback([tier1, tier2])

    assert result == "fallback-bytes"
    assert calls1 == ["nano_banana"]


def test_all_tiers_exhausted_raises():
    tier1, _ = make_tier("nano_banana", [QuotaExhaustedError("quota")])
    tier2, _ = make_tier("cloudflare_sdxl", [QuotaExhaustedError("quota")])

    with pytest.raises(AllTiersExhaustedError):
        run_with_fallback([tier1, tier2])
