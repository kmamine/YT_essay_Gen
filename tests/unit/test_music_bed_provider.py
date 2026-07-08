from essaygen.providers.music.candidate import MusicCandidate
from essaygen.providers.music.provider import MusicBedProvider


class FakeFreesoundClient:
    def __init__(self, candidates):
        self.candidates = candidates
        self.search_calls = []

    def search(self, query, **kwargs):
        self.search_calls.append((query, kwargs))
        return self.candidates


class FakeLLM:
    name = "fake"

    def __init__(self, responses):
        # queue of responses returned in call order: first the query-gen
        # call, then the judge call
        self._responses = list(responses)
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self._responses.pop(0)


class FakeHttpResponse:
    def __init__(self, content):
        self.content = content


class FakeHttpClient:
    def __init__(self, content=b"fake-mp3-bytes"):
        self.content = content
        self.get_calls = []

    def get(self, url):
        self.get_calls.append(url)
        return FakeHttpResponse(self.content)


CANDIDATES = [
    MusicCandidate(
        id="freesound:111",
        description="Somber Cello Drone",
        preview_url="https://freesound.org/data/previews/111-hq.mp3",
        duration_sec=120.5,
    ),
    MusicCandidate(
        id="freesound:222",
        description="Happy Ukulele Pop",
        preview_url="https://freesound.org/data/previews/222-hq.mp3",
        duration_sec=90.0,
    ),
]


def test_fetch_and_cache_returns_existing_cache_without_searching_or_calling_llm(tmp_path):
    cache_path = tmp_path / "music_bed.mp3"
    cache_path.write_bytes(b"already-cached")
    client = FakeFreesoundClient(CANDIDATES)
    llm = FakeLLM([])
    provider = MusicBedProvider(client=client, llm=llm, http_client=FakeHttpClient())

    result = provider.fetch_and_cache(cache_path, title="t", thesis="t")

    assert result == cache_path
    assert client.search_calls == []
    assert llm.prompts == []


def test_fetch_and_cache_generates_query_then_judges_and_downloads_best_match(tmp_path):
    cache_path = tmp_path / "nested" / "music_bed.mp3"
    client = FakeFreesoundClient(CANDIDATES)
    llm = FakeLLM(['{"query": "somber orchestral"}', '{"best_id": "freesound:111"}'])
    http_client = FakeHttpClient(content=b"real-mp3-bytes")
    provider = MusicBedProvider(client=client, llm=llm, http_client=http_client)

    result = provider.fetch_and_cache(
        cache_path, title="The Fall of Rome", thesis="Rome fell from within."
    )

    assert result == cache_path
    assert cache_path.read_bytes() == b"real-mp3-bytes"
    assert client.search_calls[0][0] == "somber orchestral"
    assert http_client.get_calls == ["https://freesound.org/data/previews/111-hq.mp3"]


def test_fetch_and_cache_returns_none_when_no_candidates_found(tmp_path):
    cache_path = tmp_path / "music_bed.mp3"
    client = FakeFreesoundClient([])
    llm = FakeLLM(['{"query": "somber orchestral"}'])
    provider = MusicBedProvider(client=client, llm=llm, http_client=FakeHttpClient())

    result = provider.fetch_and_cache(cache_path, title="t", thesis="t")

    assert result is None
    assert not cache_path.exists()


def test_fetch_and_cache_returns_none_when_judge_rejects_all_candidates(tmp_path):
    cache_path = tmp_path / "music_bed.mp3"
    client = FakeFreesoundClient(CANDIDATES)
    llm = FakeLLM(['{"query": "somber orchestral"}', '{"best_id": null}'])
    provider = MusicBedProvider(client=client, llm=llm, http_client=FakeHttpClient())

    result = provider.fetch_and_cache(cache_path, title="t", thesis="t")

    assert result is None
    assert not cache_path.exists()


class FakeFreesoundClientPerQuery:
    def __init__(self, candidates_by_query):
        self.candidates_by_query = candidates_by_query
        self.search_calls = []

    def search(self, query, **kwargs):
        self.search_calls.append(query)
        return self.candidates_by_query.get(query, [])


def test_fetch_and_cache_retries_with_fallback_query_when_llm_query_finds_nothing(tmp_path):
    # Live-verified: LLM-generated mood words that sound reasonable (e.g.
    # "somber orchestral", "dark historical") frequently return zero
    # results -- Freesound's community tag vocabulary is narrower than
    # natural language. A hardcoded, confirmed-high-yield fallback query
    # keeps music from being silently skipped just from word-choice luck.
    cache_path = tmp_path / "music_bed.mp3"
    client = FakeFreesoundClientPerQuery({"somber orchestral": [], "cinematic ambient": CANDIDATES})
    llm = FakeLLM(['{"query": "somber orchestral"}', '{"best_id": "freesound:111"}'])
    http_client = FakeHttpClient(content=b"fallback-bytes")
    provider = MusicBedProvider(client=client, llm=llm, http_client=http_client)

    result = provider.fetch_and_cache(cache_path, title="t", thesis="t")

    assert result == cache_path
    assert cache_path.read_bytes() == b"fallback-bytes"
    assert client.search_calls == ["somber orchestral", "cinematic ambient"]


def test_fetch_and_cache_passes_min_duration_sec_to_search(tmp_path):
    cache_path = tmp_path / "music_bed.mp3"
    client = FakeFreesoundClient(CANDIDATES)
    llm = FakeLLM(['{"query": "somber orchestral"}', '{"best_id": "freesound:111"}'])
    provider = MusicBedProvider(
        client=client, llm=llm, min_duration_sec=45, http_client=FakeHttpClient()
    )

    provider.fetch_and_cache(cache_path, title="t", thesis="t")

    assert client.search_calls[0][1]["min_duration_sec"] == 45
