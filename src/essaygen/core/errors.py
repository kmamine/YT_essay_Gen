class EssaygenError(Exception):
    pass


class RetryableError(EssaygenError):
    pass


class RateLimitError(RetryableError):
    def __init__(self, message: str, retry_after_sec: float | None = None):
        super().__init__(message)
        self.retry_after_sec = retry_after_sec


class QuotaExhaustedError(RetryableError):
    pass


class TransientError(RetryableError):
    pass


class FatalError(EssaygenError):
    pass
