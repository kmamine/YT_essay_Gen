import pytest

from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError
from essaygen.providers.music.freesound import FreesoundClient


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


FREESOUND_PAYLOAD = {
    "results": [
        {
            "id": 111,
            "name": "Ambient Cinematic Pad",
            "tags": ["ambient", "cinematic", "pad", "documentary"],
            "license": "Creative Commons 0",
            "duration": 120.5,
            "previews": {
                "preview-hq-mp3": "https://freesound.org/data/previews/111-hq.mp3",
                "preview-lq-mp3": "https://freesound.org/data/previews/111-lq.mp3",
            },
        },
        {
            "id": 222,
            "name": "Dark Drone Loop",
            "tags": ["drone", "dark", "loop"],
            "license": "Creative Commons 0",
            "duration": 90.0,
            "previews": {
                "preview-hq-mp3": "https://freesound.org/data/previews/222-hq.mp3",
                "preview-lq-mp3": "https://freesound.org/data/previews/222-lq.mp3",
            },
        },
    ]
}


def test_search_returns_candidates_with_id_description_url_and_duration():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=FREESOUND_PAYLOAD))
    provider = FreesoundClient(api_key="fake-key", client=client)

    candidates = provider.search("cinematic ambient background")

    assert len(candidates) == 2
    assert candidates[0].id == "freesound:111"
    assert candidates[0].description == "Ambient Cinematic Pad (ambient, cinematic, pad, documentary)"
    assert candidates[0].preview_url == "https://freesound.org/data/previews/111-hq.mp3"
    assert candidates[0].duration_sec == 120.5


def test_search_sends_token_and_filters_to_cc0_license():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=FREESOUND_PAYLOAD))
    provider = FreesoundClient(api_key="fake-key", client=client)

    provider.search("cinematic ambient background")

    _, _, params = client.calls[0]
    assert params["token"] == "fake-key"
    assert params["query"] == "cinematic ambient background"
    assert 'license:"Creative Commons 0"' in params["filter"]


def test_search_filters_by_minimum_duration_to_avoid_short_stingers():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=FREESOUND_PAYLOAD))
    provider = FreesoundClient(api_key="fake-key", client=client)

    provider.search("cinematic ambient background", min_duration_sec=45)

    _, _, params = client.calls[0]
    assert "duration:[45 TO *]" in params["filter"]


def test_search_requests_preview_and_license_fields():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload=FREESOUND_PAYLOAD))
    provider = FreesoundClient(api_key="fake-key", client=client)

    provider.search("cinematic ambient background")

    _, _, params = client.calls[0]
    assert "previews" in params["fields"]
    assert "license" in params["fields"]
    assert "duration" in params["fields"]


def test_search_raises_fatal_error_when_not_configured():
    provider = FreesoundClient(api_key="")

    with pytest.raises(FatalError):
        provider.search("query")


def test_search_raises_rate_limit_error_on_429():
    client = FakeHttpClient(FakeResponse(status_code=429, text="slow down"))
    provider = FreesoundClient(api_key="fake-key", client=client)

    with pytest.raises(RateLimitError):
        provider.search("query")


def test_search_raises_quota_exhausted_on_401():
    client = FakeHttpClient(FakeResponse(status_code=401, text="unauthorized"))
    provider = FreesoundClient(api_key="fake-key", client=client)

    with pytest.raises(QuotaExhaustedError):
        provider.search("query")


def test_search_raises_transient_error_on_5xx():
    client = FakeHttpClient(FakeResponse(status_code=503, text="unavailable"))
    provider = FreesoundClient(api_key="fake-key", client=client)

    with pytest.raises(TransientError):
        provider.search("query")


def test_search_raises_fatal_error_on_other_4xx():
    client = FakeHttpClient(FakeResponse(status_code=400, text="bad request"))
    provider = FreesoundClient(api_key="fake-key", client=client)

    with pytest.raises(FatalError):
        provider.search("query")


class RaisingHttpClient:
    def get(self, url, headers=None, params=None):
        raise ValueError("boom")


def test_search_translates_unexpected_transport_errors_into_transient_error():
    provider = FreesoundClient(api_key="fake-key", client=RaisingHttpClient())

    with pytest.raises(TransientError):
        provider.search("query")


def test_search_returns_empty_list_when_no_results_found():
    client = FakeHttpClient(FakeResponse(status_code=200, json_payload={"results": []}))
    provider = FreesoundClient(api_key="fake-key", client=client)

    candidates = provider.search("query")

    assert candidates == []
