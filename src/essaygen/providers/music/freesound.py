from typing import Any

import httpx

from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError
from essaygen.providers.music.candidate import MusicCandidate

FREESOUND_SEARCH_URL = "https://freesound.org/apiv2/search/text/"

_DEFAULT_MIN_DURATION_SEC = 60


class FreesoundClient:
    name = "freesound"

    def __init__(self, api_key: str, client: Any = None):
        self._api_key = api_key
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def search(
        self,
        query: str,
        per_page: int = 10,
        min_duration_sec: int = _DEFAULT_MIN_DURATION_SEC,
    ) -> list[MusicCandidate]:
        if not self._api_key:
            raise FatalError("freesound is not configured: set FREESOUND_API_KEY in .env")

        try:
            response = self.client.get(
                FREESOUND_SEARCH_URL,
                params={
                    "query": query,
                    "token": self._api_key,
                    "filter": f'license:"Creative Commons 0" duration:[{min_duration_sec} TO *]',
                    "fields": "id,name,tags,license,previews,duration",
                    "page_size": per_page,
                },
            )
        except Exception as exc:
            raise TransientError(f"Freesound request could not be sent: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitError(f"Freesound rate limited: {response.text}")
        if response.status_code in (401, 403):
            raise QuotaExhaustedError(f"Freesound quota/auth error: {response.text}")
        if response.status_code >= 500:
            raise TransientError(f"Freesound server error {response.status_code}: {response.text}")
        if response.status_code >= 400:
            raise FatalError(f"Freesound request failed {response.status_code}: {response.text}")

        payload = response.json()
        candidates = []
        for result in payload.get("results", []):
            tags = ", ".join(result.get("tags") or [])
            description = result.get("name", "")
            if tags:
                description = f"{description} ({tags})"
            candidates.append(
                MusicCandidate(
                    id=f"freesound:{result['id']}",
                    description=description,
                    preview_url=result["previews"]["preview-hq-mp3"],
                    duration_sec=result["duration"],
                )
            )
        return candidates
