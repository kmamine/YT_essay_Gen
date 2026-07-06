from typing import Any

import httpx

from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError
from essaygen.providers.image.stock.candidate import StockCandidate

PEXELS_SEARCH_URL = "https://api.pexels.com/v1/search"

_ORIENTATION_MAP = {"16:9": "landscape", "9:16": "portrait"}


class PexelsClient:
    name = "pexels"

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
            raise FatalError("pexels is not configured: set PEXELS_API_KEY in .env")

        orientation = _ORIENTATION_MAP.get(aspect_ratio, "landscape")
        try:
            response = self.client.get(
                PEXELS_SEARCH_URL,
                headers={"Authorization": self._api_key},
                params={"query": query, "orientation": orientation, "per_page": per_page},
            )
        except Exception as exc:
            raise TransientError(f"Pexels request could not be sent: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitError(f"Pexels rate limited: {response.text}")
        if response.status_code in (401, 403):
            raise QuotaExhaustedError(f"Pexels quota/auth error: {response.text}")
        if response.status_code >= 500:
            raise TransientError(f"Pexels server error {response.status_code}: {response.text}")
        if response.status_code >= 400:
            raise FatalError(f"Pexels request failed {response.status_code}: {response.text}")

        payload = response.json()
        return [
            StockCandidate(
                id=f"pexels:{photo['id']}",
                description=photo.get("alt") or "",
                image_url=photo["src"]["large"],
            )
            for photo in payload.get("photos", [])
        ]
