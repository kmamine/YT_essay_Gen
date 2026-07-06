import pytest

from essaygen.core.errors import FatalError
from essaygen.providers.image.base import ImageRequest
from essaygen.providers.image.stock.candidate import StockCandidate
from essaygen.providers.image.stock.provider import StockPhotoProvider


class FakeSearchClient:
    def __init__(self, name, candidates=None, error=None):
        self.name = name
        self.candidates = candidates or []
        self.error = error
        self.calls = []

    def search(self, query, aspect_ratio, per_page=5):
        self.calls.append((query, aspect_ratio, per_page))
        if self.error:
            raise self.error
        return self.candidates


class FakeLLM:
    name = "fake"

    def __init__(self, response):
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


class FakeHttpResponse:
    def __init__(self, content):
        self.content = content


class FakeHttpClient:
    def __init__(self, content=b"image-bytes"):
        self.content = content
        self.calls = []

    def get(self, url):
        self.calls.append(url)
        return FakeHttpResponse(self.content)


CANDIDATE_A = StockCandidate(id="pexels:1", description="roman senate ruins", image_url="https://x/1.jpg")
CANDIDATE_B = StockCandidate(id="pixabay:2", description="modern office", image_url="https://x/2.jpg")


def test_generate_pools_candidates_from_all_search_clients_for_judge():
    pexels = FakeSearchClient("pexels", candidates=[CANDIDATE_A])
    pixabay = FakeSearchClient("pixabay", candidates=[CANDIDATE_B])
    llm = FakeLLM('{"best_id": "pixabay:2"}')
    http_client = FakeHttpClient()
    provider = StockPhotoProvider(
        search_clients=[pexels, pixabay], llm=llm, http_client=http_client
    )

    provider.generate(ImageRequest(image_prompt="prompt", stock_query="roman senate ruins"))

    assert pexels.calls == [("roman senate ruins", "16:9", 5)]
    assert pixabay.calls == [("roman senate ruins", "16:9", 5)]


def test_generate_passes_configured_candidates_per_provider():
    pexels = FakeSearchClient("pexels", candidates=[CANDIDATE_A])
    llm = FakeLLM('{"best_id": "pexels:1"}')
    provider = StockPhotoProvider(
        search_clients=[pexels],
        llm=llm,
        http_client=FakeHttpClient(),
        candidates_per_provider=8,
    )

    provider.generate(ImageRequest(image_prompt="prompt", stock_query="roman senate ruins"))

    assert pexels.calls == [("roman senate ruins", "16:9", 8)]


def test_generate_returns_image_bytes_for_judge_chosen_candidate():
    pexels = FakeSearchClient("pexels", candidates=[CANDIDATE_A])
    llm = FakeLLM('{"best_id": "pexels:1"}')
    http_client = FakeHttpClient(content=b"the-actual-photo-bytes")
    provider = StockPhotoProvider(search_clients=[pexels], llm=llm, http_client=http_client)

    result = provider.generate(ImageRequest(image_prompt="prompt", stock_query="roman senate ruins"))

    assert result == b"the-actual-photo-bytes"
    assert http_client.calls == ["https://x/1.jpg"]


def test_generate_raises_fatal_error_when_no_candidates_found_across_all_sources():
    pexels = FakeSearchClient("pexels", candidates=[])
    pixabay = FakeSearchClient("pixabay", candidates=[])
    llm = FakeLLM('{"best_id": null}')
    provider = StockPhotoProvider(search_clients=[pexels, pixabay], llm=llm, http_client=FakeHttpClient())

    with pytest.raises(FatalError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="obscure query"))


def test_generate_raises_fatal_error_when_judge_finds_no_match():
    pexels = FakeSearchClient("pexels", candidates=[CANDIDATE_A, CANDIDATE_B])
    llm = FakeLLM('{"best_id": null}')
    provider = StockPhotoProvider(search_clients=[pexels], llm=llm, http_client=FakeHttpClient())

    with pytest.raises(FatalError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="obscure query"))


def test_generate_skips_search_client_that_raises_and_continues_with_others():
    failing = FakeSearchClient("pexels", error=FatalError("pexels not configured"))
    working = FakeSearchClient("pixabay", candidates=[CANDIDATE_B])
    llm = FakeLLM('{"best_id": "pixabay:2"}')
    http_client = FakeHttpClient(content=b"pixabay-bytes")
    provider = StockPhotoProvider(search_clients=[failing, working], llm=llm, http_client=http_client)

    result = provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))

    assert result == b"pixabay-bytes"


def test_provider_has_expected_name():
    provider = StockPhotoProvider(search_clients=[], llm=FakeLLM("{}"), http_client=FakeHttpClient())

    assert provider.name == "stock_photo"
