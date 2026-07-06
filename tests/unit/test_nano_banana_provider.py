import pytest

from essaygen.core.errors import FatalError, RateLimitError
from essaygen.providers.image.base import ImageRequest
from essaygen.providers.image.nano_banana import NanoBananaProvider


class FakeInlineData:
    def __init__(self, data):
        self.data = data


class FakePart:
    def __init__(self, inline_data=None, text=None):
        self.inline_data = inline_data
        self.text = text


class FakeContent:
    def __init__(self, parts):
        self.parts = parts


class FakeCandidate:
    def __init__(self, parts):
        self.content = FakeContent(parts)


class FakeResponse:
    def __init__(self, parts):
        self.candidates = [FakeCandidate(parts)]


class FakeModels:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def generate_content(self, model, contents):
        self.calls.append((model, contents))
        if self.error:
            raise self.error
        return self.response


class FakeGenaiClient:
    def __init__(self, models):
        self.models = models


class FakeError(Exception):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def test_generate_returns_image_bytes_from_inline_data():
    client = FakeGenaiClient(FakeModels(response=FakeResponse([FakePart(inline_data=FakeInlineData(b"png-bytes"))])))
    provider = NanoBananaProvider(api_key="fake-key", client=client)

    result = provider.generate(ImageRequest(image_prompt="a cat eating a banana", stock_query="cat banana"))

    assert result == b"png-bytes"
    assert client.models.calls[0][1] == "a cat eating a banana"


def test_generate_raises_fatal_error_when_no_image_part_present():
    client = FakeGenaiClient(FakeModels(response=FakeResponse([FakePart(text="I can't do that")])))
    provider = NanoBananaProvider(api_key="fake-key", client=client)

    with pytest.raises(FatalError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))


def test_generate_translates_provider_errors():
    client = FakeGenaiClient(FakeModels(error=FakeError("too many requests", code=429)))
    provider = NanoBananaProvider(api_key="fake-key", client=client)

    with pytest.raises(RateLimitError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))


def test_provider_has_expected_name():
    provider = NanoBananaProvider(api_key="fake-key", client=FakeGenaiClient(FakeModels()))

    assert provider.name == "nano_banana"


def test_lazily_constructs_real_client_when_none_injected():
    # No network call happens at construction time, so this stays a fast,
    # offline test — but it exercises the real import path against the
    # actually-installed google-genai package, which fake-client tests can't.
    from google.genai.client import Client

    provider = NanoBananaProvider(api_key="fake-key")

    assert isinstance(provider.client, Client)
