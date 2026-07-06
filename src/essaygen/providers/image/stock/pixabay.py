from typing import Any

import httpx

from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError
from essaygen.providers.image.stock.candidate import StockCandidate

PIXABAY_SEARCH_URL = "https://pixabay.com/api/"

_ORIENTATION_MAP = {"16:9": "horizontal", "9:16": "vertical"}
_MIN_PER_PAGE = 3


class PixabayClient:
    name = "pixabay"

    def __init__(self, api_key: str, client: Any = None):
        self._api_key = api_key
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def search(self, query: str, aspect_ratio: str, per_page: int = 5) -> list[StockCandidate]:
        if not self._api_key:
            raise FatalError("pixabay is not configured: set PIXABAY_API_KEY in .env")

        orientation = _ORIENTATION_MAP.get(aspect_ratio, "horizontal")
        try:
            response = self.client.get(
                PIXABAY_SEARCH_URL,
                params={
                    "key": self._api_key,
                    "q": query,
                    # "all" (not "photo"): includes illustrations/paintings,
                    # which are often the closest available match for
                    # historical events with no photographic record
                    "image_type": "all",
                    "orientation": orientation,
                    "per_page": max(per_page, _MIN_PER_PAGE),
                },
            )
        except Exception as exc:
            raise TransientError(f"Pixabay request could not be sent: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitError(f"Pixabay rate limited: {response.text}")
        if response.status_code in (401, 403):
            raise QuotaExhaustedError(f"Pixabay quota/auth error: {response.text}")
        if response.status_code >= 500:
            raise TransientError(f"Pixabay server error {response.status_code}: {response.text}")
        if response.status_code >= 400:
            raise FatalError(f"Pixabay request failed {response.status_code}: {response.text}")

        payload = response.json()
        return [
            StockCandidate(
                id=f"pixabay:{hit['id']}",
                description=hit.get("tags") or "",
                image_url=hit["largeImageURL"],
            )
            for hit in payload.get("hits", [])
        ]
