import pytest

from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError
from essaygen.providers.image.stock.pixabay import PixabayClient


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

    def get(self, url, params=None):
        self.calls.append((url, params))
        return self.response


PIXABAY_PAYLOAD = {
    "hits": [
        {
            "id": 789,
            "tags": "roman, senate, ruins, ancient",
            "largeImageURL": "https://pixabay.com/photos/789/large.jpg",
        },
        {
            "id": 987,
            "tags": "rome, architecture",
            "largeImageURL": "https://pixabay.com/photos/987/large.jpg",
        },
    ]
}


def test_search_returns_candidates_with_id_description_and_url():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=PIXABAY_PAYLOAD))
    provider = PixabayClient(api_key="fake-key", client=client)

    candidates = provider.search("roman senate ruins", aspect_ratio="16:9")

    assert len(candidates) == 2
    assert candidates[0].id == "pixabay:789"
    assert candidates[0].description == "roman, senate, ruins, ancient"
    assert candidates[0].image_url == "https://pixabay.com/photos/789/large.jpg"


def test_search_sends_api_key_and_query_params():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=PIXABAY_PAYLOAD))
    provider = PixabayClient(api_key="fake-key", client=client)

    provider.search("roman senate ruins", aspect_ratio="9:16")

    _, params = client.calls[0]
    assert params["key"] == "fake-key"
    assert params["q"] == "roman senate ruins"
    assert params["orientation"] == "vertical"


def test_search_includes_illustrations_and_paintings_not_just_photos():
    # Some segments (e.g. historical events with no photographic record)
    # have no real photo but may have a painting/illustration that's a much
    # better stand-in than falling through to a currently-nonfunctional
    # generation tier — so search across all image types, not just "photo".
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=PIXABAY_PAYLOAD))
    provider = PixabayClient(api_key="fake-key", client=client)

    provider.search("roman senate ruins", aspect_ratio="16:9")

    _, params = client.calls[0]
    assert params["image_type"] == "all"


def test_search_maps_16_9_to_horizontal_orientation():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=PIXABAY_PAYLOAD))
    provider = PixabayClient(api_key="fake-key", client=client)

    provider.search("query", aspect_ratio="16:9")

    _, params = client.calls[0]
    assert params["orientation"] == "horizontal"


def test_search_enforces_pixabay_minimum_per_page_of_3():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=PIXABAY_PAYLOAD))
    provider = PixabayClient(api_key="fake-key", client=client)

    provider.search("query", aspect_ratio="16:9", per_page=1)

    _, params = client.calls[0]
    assert params["per_page"] == 3


def test_search_raises_fatal_error_when_not_configured():
    provider = PixabayClient(api_key="")

    with pytest.raises(FatalError):
        provider.search("query", aspect_ratio="16:9")


def test_search_raises_rate_limit_error_on_429():
    client = FakeHttpClient(FakeResponse(status_code=429, text="slow down"))
    provider = PixabayClient(api_key="fake-key", client=client)

    with pytest.raises(RateLimitError):
        provider.search("query", aspect_ratio="16:9")


def test_search_raises_quota_exhausted_on_401():
    client = FakeHttpClient(FakeResponse(status_code=401, text="unauthorized"))
    provider = PixabayClient(api_key="fake-key", client=client)

    with pytest.raises(QuotaExhaustedError):
        provider.search("query", aspect_ratio="16:9")


def test_search_raises_transient_error_on_5xx():
    client = FakeHttpClient(FakeResponse(status_code=503, text="unavailable"))
    provider = PixabayClient(api_key="fake-key", client=client)

    with pytest.raises(TransientError):
        provider.search("query", aspect_ratio="16:9")


def test_search_raises_fatal_error_on_other_4xx():
    client = FakeHttpClient(FakeResponse(status_code=400, text="bad request"))
    provider = PixabayClient(api_key="fake-key", client=client)

    with pytest.raises(FatalError):
        provider.search("query", aspect_ratio="16:9")


class RaisingHttpClient:
    def get(self, url, params=None):
        raise ValueError("boom")


def test_search_translates_unexpected_transport_errors_into_transient_error():
    provider = PixabayClient(api_key="fake-key", client=RaisingHttpClient())

    with pytest.raises(TransientError):
        provider.search("query", aspect_ratio="16:9")


def test_search_returns_empty_list_when_no_hits_found():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload={"hits": []}))
    provider = PixabayClient(api_key="fake-key", client=client)

    candidates = provider.search("query", aspect_ratio="16:9")

    assert candidates == []
