import pytest

from essaygen.core.errors import FatalError
from essaygen.providers.wikipedia.client import (
    extract_facts,
    fetch_article_extract,
    split_into_sentences,
)


def test_split_into_sentences_splits_on_sentence_boundaries():
    text = "Rome was founded in 753 BC. It became a republic in 509 BC. Then it fell in 476 AD."

    sentences = split_into_sentences(text)

    assert sentences == [
        "Rome was founded in 753 BC.",
        "It became a republic in 509 BC.",
        "Then it fell in 476 AD.",
    ]


def test_split_into_sentences_ignores_section_headings():
    text = "\n\n== Etymology ==\n\nRome was founded in 753 BC, according to tradition.\n\n== History ==\n\nIt became a republic in 509 BC, a major shift."

    sentences = split_into_sentences(text)

    assert all(not s.startswith("==") for s in sentences)
    assert "Rome was founded in 753 BC, according to tradition." in sentences


def test_split_into_sentences_filters_short_fragments():
    text = "Ok. This is a properly long sentence about Roman history and its founding."

    sentences = split_into_sentences(text)

    assert "Ok." not in sentences
    assert "This is a properly long sentence about Roman history and its founding." in sentences


def test_extract_facts_assigns_sequential_ids_and_source_url():
    text = "Rome was founded in 753 BC, according to legend and tradition. It became a republic in 509 BC after the monarchy fell."

    facts = extract_facts(text, source_url="https://en.wikipedia.org/wiki/Rome")

    assert facts[0].id == "fact_01"
    assert facts[1].id == "fact_02"
    assert all(f.source_url == "https://en.wikipedia.org/wiki/Rome" for f in facts)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, params=None, headers=None):
        self.calls.append((url, params, headers))
        return FakeResponse(self.payload)


def test_fetch_article_extract_sends_descriptive_user_agent_and_parses_result():
    payload = {
        "query": {
            "pages": {
                "12345": {
                    "extract": "Rome was founded in 753 BC.",
                    "fullurl": "https://en.wikipedia.org/wiki/Rome",
                }
            }
        }
    }
    client = FakeClient(payload)

    text, url = fetch_article_extract("Rome", user_agent="EssayGen/0.1 (test@example.com)", client=client)

    assert text == "Rome was founded in 753 BC."
    assert url == "https://en.wikipedia.org/wiki/Rome"
    _, params, headers = client.calls[0]
    assert headers["User-Agent"] == "EssayGen/0.1 (test@example.com)"
    assert params["exintro"] == 1


def test_fetch_article_extract_raises_fatal_error_when_article_missing():
    payload = {"query": {"pages": {"-1": {"missing": ""}}}}
    client = FakeClient(payload)

    with pytest.raises(FatalError):
        fetch_article_extract("NotARealTopicXYZ", user_agent="EssayGen/0.1 (test@example.com)", client=client)
