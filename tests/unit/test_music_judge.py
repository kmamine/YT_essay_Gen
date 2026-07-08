import pytest

from essaygen.core.errors import FatalError
from essaygen.providers.music.candidate import MusicCandidate
from essaygen.providers.music.judge import (
    build_music_judge_prompt,
    judge_best_music_candidate,
    parse_music_judge_response,
)


@pytest.fixture
def candidates():
    return [
        MusicCandidate(
            id="freesound:1",
            description="Somber Cello Drone (dark, minor, cinematic)",
            preview_url="https://x/1.mp3",
            duration_sec=120.0,
        ),
        MusicCandidate(
            id="freesound:2",
            description="Happy Ukulele Pop (upbeat, cheerful, dance)",
            preview_url="https://x/2.mp3",
            duration_sec=90.0,
        ),
    ]


def test_build_music_judge_prompt_includes_thesis_and_candidate_ids(candidates):
    prompt = build_music_judge_prompt("Rome fell from within.", candidates)

    assert "Rome fell from within." in prompt
    assert "freesound:1" in prompt
    assert "freesound:2" in prompt


def test_build_music_judge_prompt_instructs_tonal_not_literal_match(candidates):
    prompt = build_music_judge_prompt("Rome fell from within.", candidates)

    lowered = prompt.lower()
    assert "tone" in lowered or "mood" in lowered
    assert "doesn't need to be about the topic" in lowered or "not about the topic" in lowered


def test_parse_music_judge_response_returns_best_id():
    assert parse_music_judge_response('{"best_id": "freesound:1"}') == "freesound:1"


def test_parse_music_judge_response_returns_none_when_no_match():
    assert parse_music_judge_response('{"best_id": null}') is None


def test_parse_music_judge_response_raises_fatal_error_on_invalid_json():
    with pytest.raises(FatalError):
        parse_music_judge_response("not json")


class FakeLLM:
    name = "fake"

    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_judge_best_music_candidate_returns_matching_candidate(candidates):
    llm = FakeLLM('{"best_id": "freesound:1"}')

    best = judge_best_music_candidate(llm, "Rome fell from within.", candidates)

    assert best is candidates[0]


def test_judge_best_music_candidate_returns_none_when_llm_finds_no_match(candidates):
    llm = FakeLLM('{"best_id": null}')

    best = judge_best_music_candidate(llm, "Rome fell from within.", candidates)

    assert best is None


def test_judge_best_music_candidate_matches_when_llm_drops_id_prefix(candidates):
    # Live-verified: asked to pick from candidates with ids like
    # "freesound:855301", Mistral sometimes returns just the bare numeric
    # suffix ("855301") in best_id, dropping the provider prefix. Strict
    # equality then finds no match and silently returns None even though
    # the LLM clearly meant that candidate.
    llm = FakeLLM('{"best_id": "1"}')

    best = judge_best_music_candidate(llm, "Rome fell from within.", candidates)

    assert best is candidates[0]


def test_judge_best_music_candidate_returns_none_when_llm_picks_unknown_id(candidates):
    llm = FakeLLM('{"best_id": "nonexistent:99"}')

    best = judge_best_music_candidate(llm, "Rome fell from within.", candidates)

    assert best is None


def test_judge_best_music_candidate_skips_llm_call_when_no_candidates():
    llm = FakeLLM('{"best_id": null}')

    best = judge_best_music_candidate(llm, "Rome fell from within.", [])

    assert best is None
    assert llm.prompts == []
