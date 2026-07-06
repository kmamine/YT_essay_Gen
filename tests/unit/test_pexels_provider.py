import pytest

from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError
from essaygen.providers.image.stock.pexels import PexelsClient


class FakeResponse:
    def __init__(self, status_code=200, json_payload=None, text=""):
        self.status_code = status_code
        self._json_payload = json_payload or {}
        self.text = text

    def json(self):
        return self._json_payload


class FakeHttpClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def get(self, url, headers=None, params=None):
        self.calls.append((url, headers, params))
        return self.response


PEXELS_PAYLOAD = {
    "photos": [
        {
            "id": 123,
            "alt": "A crumbling ancient senate building",
            "src": {"large": "https://images.pexels.com/photos/123/large.jpg"},
        },
        {
            "id": 456,
            "alt": "Roman ruins at sunset",
            "src": {"large": "https://images.pexels.com/photos/456/large.jpg"},
        },
    ]
}


def test_search_returns_candidates_with_id_description_and_url():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=PEXELS_PAYLOAD))
    provider = PexelsClient(api_key="fake-key", client=client)

    candidates = provider.search("roman senate ruins", aspect_ratio="16:9")

    assert len(candidates) == 2
    assert candidates[0].id == "pexels:123"
    assert candidates[0].description == "A crumbling ancient senate building"
    assert candidates[0].image_url == "https://images.pexels.com/photos/123/large.jpg"


def test_search_sends_api_key_header_and_query_params():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=PEXELS_PAYLOAD))
    provider = PexelsClient(api_key="fake-key", client=client)

    provider.search("roman senate ruins", aspect_ratio="9:16")

    url, headers, params = client.calls[0]
    assert headers["Authorization"] == "fake-key"
    assert params["query"] == "roman senate ruins"
    assert params["orientation"] == "portrait"


def test_search_maps_16_9_to_landscape_orientation():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=PEXELS_PAYLOAD))
    provider = PexelsClient(api_key="fake-key", client=client)

    provider.search("query", aspect_ratio="16:9")

    _, _, params = client.calls[0]
    assert params["orientation"] == "landscape"


def test_search_raises_fatal_error_when_not_configured():
    provider = PexelsClient(api_key="")

    with pytest.raises(FatalError):
        provider.search("query", aspect_ratio="16:9")


def test_search_raises_rate_limit_error_on_429():
    client = FakeHttpClient(FakeResponse(status_code=429, text="slow down"))
    provider = PexelsClient(api_key="fake-key", client=client)

    with pytest.raises(RateLimitError):
        provider.search("query", aspect_ratio="16:9")


def test_search_raises_quota_exhausted_on_401():
    client = FakeHttpClient(FakeResponse(status_code=401, text="unauthorized"))
    provider = PexelsClient(api_key="fake-key", client=client)

    with pytest.raises(QuotaExhaustedError):
        provider.search("query", aspect_ratio="16:9")


def test_search_raises_transient_error_on_5xx():
    client = FakeHttpClient(FakeResponse(status_code=503, text="unavailable"))
    provider = PexelsClient(api_key="fake-key", client=client)

    with pytest.raises(TransientError):
        provider.search("query", aspect_ratio="16:9")


def test_search_raises_fatal_error_on_other_4xx():
    client = FakeHttpClient(FakeResponse(status_code=400, text="bad request"))
    provider = PexelsClient(api_key="fake-key", client=client)

    with pytest.raises(FatalError):
        provider.search("query", aspect_ratio="16:9")


class RaisingHttpClient:
    def get(self, url, headers=None, params=None):
        raise ValueError("boom")


def test_search_translates_unexpected_transport_errors_into_transient_error():
    provider = PexelsClient(api_key="fake-key", client=RaisingHttpClient())

    with pytest.raises(TransientError):
        provider.search("query", aspect_ratio="16:9")


def test_search_returns_empty_list_when_no_photos_found():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload={"photos": []}))
    provider = PexelsClient(api_key="fake-key", client=client)

    candidates = provider.search("query", aspect_ratio="16:9")

    assert candidates == []
