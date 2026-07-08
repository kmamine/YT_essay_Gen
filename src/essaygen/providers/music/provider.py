from pathlib import Path
from typing import Any

import httpx

from essaygen.providers.llm.base import LLMProvider
from essaygen.providers.music.freesound import FreesoundClient
from essaygen.providers.music.judge import judge_best_music_candidate
from essaygen.providers.music.query import build_music_query_prompt, parse_music_query_response

_DEFAULT_MIN_DURATION_SEC = 60

# Live-verified: LLM-generated mood queries that sound perfectly reasonable
# (e.g. "somber orchestral", "dark historical") frequently return zero
# results -- Freesound's community tag vocabulary is narrower than natural
# language. This fallback is confirmed live to return 600+ hits, used only
# when the LLM's own query choice comes up empty.
_FALLBACK_QUERY = "cinematic ambient"


class MusicBedProvider:
    name = "freesound"

    def __init__(
        self,
        client: FreesoundClient,
        llm: LLMProvider,
        min_duration_sec: int = _DEFAULT_MIN_DURATION_SEC,
        http_client: Any = None,
    ):
        self._client = client
        self._llm = llm
        self._min_duration_sec = min_duration_sec
        self._http_client = http_client

    @property
    def http_client(self) -> Any:
        if self._http_client is None:
            self._http_client = httpx.Client(timeout=30.0)
        return self._http_client

    def fetch_and_cache(self, cache_path: Path, title: str, thesis: str) -> Path | None:
        # Once a track is cached for a project, it's reused for that
        # project's future runs rather than re-fetched/re-judged every time.
        if cache_path.exists():
            return cache_path

        query = parse_music_query_response(
            self._llm.generate(build_music_query_prompt(title, thesis))
        )
        candidates = self._client.search(query, min_duration_sec=self._min_duration_sec)
        if not candidates and query != _FALLBACK_QUERY:
            candidates = self._client.search(
                _FALLBACK_QUERY, min_duration_sec=self._min_duration_sec
            )
        if not candidates:
            return None

        best = judge_best_music_candidate(self._llm, thesis, candidates)
        if best is None:
            return None

        response = self.http_client.get(best.preview_url)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(response.content)
        return cache_path
