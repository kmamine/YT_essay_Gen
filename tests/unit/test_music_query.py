import pytest

from essaygen.core.errors import FatalError
from essaygen.providers.music.query import build_music_query_prompt, parse_music_query_response


def test_build_music_query_prompt_includes_title_and_thesis():
    prompt = build_music_query_prompt(
        title="The Fall of Rome", thesis="Rome collapsed from within, not from barbarian invasion."
    )

    assert "The Fall of Rome" in prompt
    assert "Rome collapsed from within, not from barbarian invasion." in prompt


def test_build_music_query_prompt_instructs_short_query_length():
    # Live-verified: Freesound's text search appears to require every query
    # word to match, so a 5-word query returned 0 results while a 3-word one
    # returned 100+. The prompt must make this constraint explicit so the
    # LLM doesn't generate an overly descriptive phrase.
    prompt = build_music_query_prompt(title="t", thesis="t")

    lowered = prompt.lower()
    assert "2-3 word" in lowered or "2 to 3 word" in lowered
    assert "zero results" in lowered or "no results" in lowered


def test_build_music_query_prompt_prefers_common_genre_words():
    # Live-verified: literary/emotional words that sound reasonable
    # ("somber", "historical", "documentary") frequently return zero
    # results on Freesound, while common genre/production descriptors
    # ("dark", "ambient", "cinematic", "orchestral", "epic", "dramatic",
    # "drone") reliably return hundreds of hits. Nudge the LLM toward the
    # latter category instead of literary word choices.
    prompt = build_music_query_prompt(title="t", thesis="t")

    lowered = prompt.lower()
    assert "common" in lowered or "generic" in lowered
    assert "ambient" in lowered and "cinematic" in lowered


def test_parse_music_query_response_extracts_query_field():
    assert parse_music_query_response('{"query": "somber orchestral"}') == "somber orchestral"


def test_parse_music_query_response_raises_fatal_error_on_invalid_json():
    with pytest.raises(FatalError):
        parse_music_query_response("not json")
