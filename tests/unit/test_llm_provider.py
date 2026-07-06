import pytest

from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError
from essaygen.providers.llm.errors import translate_provider_error
from essaygen.providers.llm.mistral import MistralProvider


class FakeError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


@pytest.mark.parametrize(
    "code,message,expected",
    [
        (429, "too many requests", RateLimitError),
        (None, "Rate limit exceeded, slow down", RateLimitError),
        (403, "quota exceeded for project", QuotaExhaustedError),
        (None, "You have exceeded your quota", QuotaExhaustedError),
        (
            429,
            "429 RESOURCE_EXHAUSTED. Quota exceeded for metric: "
            "generativelanguage.googleapis.com/generate_content_free_tier_requests, limit: 0",
            QuotaExhaustedError,
        ),
        (503, "service unavailable", TransientError),
        (None, "request timeout", TransientError),
        (400, "invalid api key", FatalError),
    ],
)
def test_translate_provider_error_maps_to_expected_type(code, message, expected):
    exc = FakeError(message, code=code)

    translated = translate_provider_error(exc)

    assert isinstance(translated, expected)
    assert message in str(translated)


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeChatResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeChat:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def complete(self, model, messages):
        self.calls.append((model, messages))
        if self.error:
            raise self.error
        return self.response


class FakeMistralClient:
    def __init__(self, chat):
        self.chat = chat


def test_mistral_provider_returns_text_on_success():
    client = FakeMistralClient(FakeChat(response=FakeChatResponse("Rome fell due to internal decay.")))
    provider = MistralProvider(api_key="fake-key", client=client)

    result = provider.generate("Write a thesis about Rome's fall.")

    assert result == "Rome fell due to internal decay."
    assert client.chat.calls[0][1] == [{"role": "user", "content": "Write a thesis about Rome's fall."}]


def test_mistral_provider_translates_errors():
    client = FakeMistralClient(FakeChat(error=FakeError("too many requests", code=429)))
    provider = MistralProvider(api_key="fake-key", client=client)

    with pytest.raises(RateLimitError):
        provider.generate("prompt")


def test_mistral_provider_has_expected_name():
    provider = MistralProvider(api_key="fake-key", client=FakeMistralClient(FakeChat()))

    assert provider.name == "mistral"


def test_mistral_provider_lazily_constructs_real_client_when_none_injected():
    # No network call happens at construction time, so this stays a fast,
    # offline test — but it exercises the real import path against the
    # actually-installed mistralai package, which fake-client tests can't.
    from mistralai.client import Mistral

    provider = MistralProvider(api_key="fake-key")

    assert isinstance(provider.client, Mistral)
