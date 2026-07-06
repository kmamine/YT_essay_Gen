from typing import Any

import httpx

from essaygen.core.errors import FatalError
from essaygen.providers.image.base import ImageRequest
from essaygen.providers.image.stock.candidate import StockCandidate
from essaygen.providers.image.stock.judge import judge_best_candidate
from essaygen.providers.llm.base import LLMProvider


class StockPhotoProvider:
    name = "stock_photo"

    def __init__(
        self,
        search_clients: list[Any],
        llm: LLMProvider,
        aspect_ratio: str = "16:9",
        candidates_per_provider: int = 5,
        http_client: Any = None,
    ):
        self._search_clients = search_clients
        self._llm = llm
        self._aspect_ratio = aspect_ratio
        self._candidates_per_provider = candidates_per_provider
        self._http_client = http_client

    @property
    def http_client(self) -> Any:
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=30.0)
        return self._http_client

    def _pool_candidates(self, query: str) -> list[StockCandidate]:
        candidates: list[StockCandidate] = []
        for search_client in self._search_clients:
            try:
                candidates.extend(
                    search_client.search(
                        query, self._aspect_ratio, per_page=self._candidates_per_provider
                    )
                )
            except Exception:
                continue
        return candidates

    def generate(self, request: ImageRequest) -> bytes:
        candidates = self._pool_candidates(request.stock_query)
        best = judge_best_candidate(self._llm, request.stock_query, candidates)
        if best is None:
            raise FatalError(
                f"no stock photo met the relevance bar for query: {request.stock_query!r}"
            )

        response = self.http_client.get(best.image_url)
        return response.content
