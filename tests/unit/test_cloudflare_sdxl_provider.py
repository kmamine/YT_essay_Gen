import base64

import pytest

from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError
from essaygen.providers.image.base import ImageRequest
from essaygen.providers.image.cloudflare_sdxl import CloudflareSDXLProvider


class FakeResponse:
    def __init__(self, status_code=200, content=b"", headers=None, json_payload=None, text=""):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self._json_payload = json_payload
        self.text = text

    def json(self):
        return self._json_payload


class FakeHttpClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def post(self, url, headers=None, json=None):
        self.calls.append((url, headers, json))
        return self.response


def test_generate_returns_raw_bytes_for_binary_response():
    client = FakeHttpClient(FakeResponse(status_code=200, content=b"raw-png-bytes", headers={"content-type": "image/png"}))
    provider = CloudflareSDXLProvider(account_id="acct123", api_token="tok456", client=client)

    result = provider.generate(ImageRequest(image_prompt="a cat eating a banana", stock_query="cat banana"))

    assert result == b"raw-png-bytes"
    url, headers, json_body = client.calls[0]
    assert "acct123" in url
    assert headers["Authorization"] == "Bearer tok456"
    assert json_body == {"prompt": "a cat eating a banana"}


def test_generate_decodes_base64_for_json_response():
    encoded = base64.b64encode(b"decoded-png-bytes").decode()
    client = FakeHttpClient(
        FakeResponse(
            status_code=200,
            headers={"content-type": "application/json"},
            json_payload={"result": {"image": encoded}},
        )
    )
    provider = CloudflareSDXLProvider(account_id="acct123", api_token="tok456", client=client)

    result = provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))

    assert result == b"decoded-png-bytes"


def test_generate_raises_rate_limit_error_on_429():
    client = FakeHttpClient(FakeResponse(status_code=429, text="slow down"))
    provider = CloudflareSDXLProvider(account_id="acct123", api_token="tok456", client=client)

    with pytest.raises(RateLimitError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))


def test_generate_raises_quota_exhausted_on_403():
    client = FakeHttpClient(FakeResponse(status_code=403, text="forbidden"))
    provider = CloudflareSDXLProvider(account_id="acct123", api_token="tok456", client=client)

    with pytest.raises(QuotaExhaustedError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))


def test_generate_raises_transient_error_on_5xx():
    client = FakeHttpClient(FakeResponse(status_code=503, text="unavailable"))
    provider = CloudflareSDXLProvider(account_id="acct123", api_token="tok456", client=client)

    with pytest.raises(TransientError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))


def test_generate_raises_fatal_error_on_other_4xx():
    client = FakeHttpClient(FakeResponse(status_code=400, text="bad request"))
    provider = CloudflareSDXLProvider(account_id="acct123", api_token="tok456", client=client)

    with pytest.raises(FatalError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))


def test_provider_has_expected_name():
    provider = CloudflareSDXLProvider(
        account_id="acct123", api_token="tok456", client=FakeHttpClient(FakeResponse())
    )

    assert provider.name == "cloudflare_sdxl"


class ExplodingHttpClient:
    """Fails loudly if ever touched, to prove the not-configured guard runs
    before any network interaction — not just that some request happens to
    return an error status."""

    def post(self, *args, **kwargs):
        raise AssertionError("should not reach the network when not configured")


def test_generate_raises_fatal_error_when_account_id_missing():
    provider = CloudflareSDXLProvider(account_id="", api_token="tok456", client=ExplodingHttpClient())

    with pytest.raises(FatalError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))


def test_generate_raises_fatal_error_when_api_token_missing():
    provider = CloudflareSDXLProvider(account_id="acct123", api_token="", client=ExplodingHttpClient())

    with pytest.raises(FatalError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))


class RaisingHttpClient:
    def post(self, url, headers=None, json=None):
        raise ValueError("Illegal header value b'Bearer '")


def test_generate_translates_unexpected_transport_errors_into_transient_error():
    provider = CloudflareSDXLProvider(account_id="acct123", api_token="tok456", client=RaisingHttpClient())

    with pytest.raises(TransientError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))
