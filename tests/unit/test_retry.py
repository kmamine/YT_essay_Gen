from essaygen.core.retry import TokenBucket, backoff_delay


class FakeClock:
    def __init__(self, start: float = 0.0):
        self.now = start

    def advance(self, seconds: float) -> None:
        self.now += seconds

    def __call__(self) -> float:
        return self.now


def test_token_bucket_starts_full_and_allows_immediate_acquire():
    clock = FakeClock()
    bucket = TokenBucket(rate_per_min=60, clock=clock)

    assert bucket.try_acquire() is True


def test_token_bucket_denies_when_empty():
    clock = FakeClock()
    bucket = TokenBucket(rate_per_min=60, capacity=1, clock=clock)

    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False


def test_token_bucket_refills_over_time():
    clock = FakeClock()
    bucket = TokenBucket(rate_per_min=60, capacity=1, clock=clock)
    assert bucket.try_acquire() is True
    assert bucket.try_acquire() is False

    clock.advance(1.0)

    assert bucket.try_acquire() is True


def test_time_until_available_zero_when_tokens_available():
    clock = FakeClock()
    bucket = TokenBucket(rate_per_min=60, clock=clock)

    assert bucket.time_until_available() == 0.0


def test_time_until_available_positive_when_empty():
    clock = FakeClock()
    bucket = TokenBucket(rate_per_min=60, capacity=1, clock=clock)
    bucket.try_acquire()

    wait = bucket.time_until_available()

    assert wait == 1.0


def test_backoff_delay_grows_exponentially():
    assert backoff_delay(0, base=1.0) == 1.0
    assert backoff_delay(1, base=1.0) == 2.0
    assert backoff_delay(2, base=1.0) == 4.0


def test_backoff_delay_capped_at_max():
    assert backoff_delay(10, base=1.0, max_delay=30.0) == 30.0
