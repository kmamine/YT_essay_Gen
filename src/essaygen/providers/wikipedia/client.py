import re

import httpx

from essaygen.core.errors import FatalError
from essaygen.models.research import Fact

WIKI_API_URL = "https://en.wikipedia.org/w/api.php"

_HEADING_RE = re.compile(r"^\s*=+.*=+\s*$")
_SENTENCE_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'])")
_MIN_SENTENCE_LENGTH = 20


def split_into_sentences(text: str) -> list[str]:
    sentences: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or _HEADING_RE.match(line):
            continue
        for chunk in _SENTENCE_BOUNDARY_RE.split(line):
            chunk = chunk.strip()
            if len(chunk) >= _MIN_SENTENCE_LENGTH:
                sentences.append(chunk)
    return sentences


def extract_facts(text: str, source_url: str) -> list[Fact]:
    sentences = split_into_sentences(text)
    return [
        Fact(id=f"fact_{i:02d}", text=sentence, source_url=source_url)
        for i, sentence in enumerate(sentences, start=1)
    ]


def fetch_article_extract(
    topic: str, user_agent: str, client: httpx.Client | None = None
) -> tuple[str, str]:
    owns_client = client is None
    http_client = client or httpx.Client(timeout=15.0)
    try:
        response = http_client.get(
            WIKI_API_URL,
            params={
                "action": "query",
                "prop": "extracts|info",
                "explaintext": 1,
                "exintro": 1,
                "inprop": "url",
                "redirects": 1,
                "titles": topic,
                "format": "json",
            },
            headers={"User-Agent": user_agent},
        )
        response.raise_for_status()
        data = response.json()
        page = next(iter(data["query"]["pages"].values()))
        if "missing" in page:
            raise FatalError(f"Wikipedia article not found for topic: {topic!r}")
        return page["extract"], page["fullurl"]
    finally:
        if owns_client:
            http_client.close()
