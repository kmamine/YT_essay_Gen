import pytest

from essaygen.core.errors import FatalError
from essaygen.providers.image.stock.candidate import StockCandidate
from essaygen.providers.image.stock.judge import (
    build_judge_prompt,
    judge_best_candidate,
    parse_judge_response,
)


@pytest.fixture
def candidates():
    return [
        StockCandidate(id="pexels:1", description="a crumbling roman senate", image_url="https://x/1.jpg"),
        StockCandidate(id="pixabay:2", description="a modern office building", image_url="https://x/2.jpg"),
    ]


def test_build_judge_prompt_includes_query_and_candidate_ids(candidates):
    prompt = build_judge_prompt("roman senate ruins", candidates)

    assert "roman senate ruins" in prompt
    assert "pexels:1" in prompt
    assert "pixabay:2" in prompt


def test_build_judge_prompt_instructs_leniency_toward_closest_match(candidates):
    # A literal photo often doesn't exist for historical events (e.g. "Roman
    # soldiers flogging a woman, ancient Britain") — the judge should prefer
    # the closest available candidate (painting, illustration, or an
    # atmospheric/mood match) over defaulting to "none qualify", since the
    # generation fallback tiers aren't reliably available.
    prompt = build_judge_prompt("roman senate ruins", candidates)

    lowered = prompt.lower()
    assert "painting" in lowered or "illustration" in lowered
    assert "closest" in lowered or "atmosphere" in lowered or "mood" in lowered


def test_build_judge_prompt_last_resort_tier_accepts_loose_era_match(candidates):
    # Regression test: live-verified a segment about a grim historical
    # execution scene, where the only candidates were tonally mismatched
    # (Christian crucifix statues, cheerful Colosseum tourism photos) — the
    # judge kept saying "none qualify" even though a same-era/culture photo
    # (e.g. a Roman arena/gladiator shot) is a reasonable last-resort
    # background image. The last tier must not require tonal precision.
    prompt = build_judge_prompt("roman senate ruins", candidates)

    lowered = prompt.lower()
    assert "last resort" in lowered or "regardless of tone" in lowered or "tonal" in lowered


def test_build_judge_prompt_last_resort_tier_ignores_geographic_region_mismatch(candidates):
    # Regression test: live-verified query "Roman crucifixion ancient
    # Britain" against real candidates that included genuinely Roman-era
    # photos (Colosseum, gladiator arena, Roman theatre ruins) — all set in
    # Italy/Jordan, not Britain. The judge still said "none qualify",
    # apparently reading "same era/culture/setting" as requiring the exact
    # country/region to match too. The last-resort tier must make clear
    # that empire/civilization-level relevance is enough even when the
    # specific country/region differs from the one named in the query.
    prompt = build_judge_prompt("roman senate ruins", candidates)

    lowered = prompt.lower()
    assert "empire" in lowered or "civilization" in lowered
    assert "region" in lowered or "country" in lowered


def test_build_judge_prompt_requests_reasoning_field_before_best_id(candidates):
    # Live-verified: asking for {"best_id": ...} only (no reasoning space)
    # made the judge give up and say null on a case it solved correctly when
    # asked to reason step-by-step through the tiers first. Requesting a
    # "reason" field ahead of "best_id" in the JSON schema gives the model
    # room for chain-of-thought while staying valid, parseable JSON.
    prompt = build_judge_prompt("roman senate ruins", candidates)

    lowered = prompt.lower()
    assert '"reason"' in lowered
    assert lowered.index('"reason"') < lowered.index('"best_id"')


def test_build_judge_prompt_welcomes_maps_3d_and_abstract_art(candidates):
    # User asked for more creative/permissive candidate acceptance: maps,
    # 3D renders, and abstract art should be explicitly welcomed alongside
    # photos/paintings/illustrations, not just tolerated as an afterthought.
    prompt = build_judge_prompt("roman senate ruins", candidates)

    lowered = prompt.lower()
    assert "map" in lowered
    assert "3d" in lowered or "3-d" in lowered
    assert "abstract" in lowered


def test_build_judge_prompt_establishes_priority_order_favoring_specific_photos(candidates):
    # Regression test: live-verified the leniency instruction alone caused
    # the judge to pick a generic illustration/mascot over clearly-better,
    # specific, on-topic real photos that were also in the candidate pool.
    # The prompt must establish an explicit priority: a specific real photo
    # beats a generic illustration, which beats a merely atmospheric match.
    prompt = build_judge_prompt("roman senate ruins", candidates)

    lowered = prompt.lower()
    assert "specific" in lowered
    assert "generic" in lowered or "prefer" in lowered


def test_parse_judge_response_returns_best_id():
    assert parse_judge_response('{"best_id": "pexels:1"}') == "pexels:1"


def test_parse_judge_response_returns_none_when_judge_finds_no_match():
    assert parse_judge_response('{"best_id": null}') is None


def test_parse_judge_response_raises_fatal_error_on_invalid_json():
    with pytest.raises(FatalError):
        parse_judge_response("not json")


class FakeLLM:
    name = "fake"

    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_judge_best_candidate_returns_matching_candidate(candidates):
    llm = FakeLLM('{"best_id": "pexels:1"}')

    best = judge_best_candidate(llm, "roman senate ruins", candidates)

    assert best is candidates[0]


def test_judge_best_candidate_matches_when_llm_drops_id_prefix(candidates):
    # Same bug class live-verified in the music judge: the LLM sometimes
    # drops the "provider:" prefix and returns just the bare numeric
    # suffix (e.g. "1" instead of "pexels:1"). Strict equality would then
    # find no match and silently return None even though the LLM clearly
    # meant that candidate.
    llm = FakeLLM('{"best_id": "1"}')

    best = judge_best_candidate(llm, "roman senate ruins", candidates)

    assert best is candidates[0]


def test_judge_best_candidate_returns_none_when_llm_finds_no_match(candidates):
    llm = FakeLLM('{"best_id": null}')

    best = judge_best_candidate(llm, "roman senate ruins", candidates)

    assert best is None


def test_judge_best_candidate_returns_none_when_llm_picks_unknown_id(candidates):
    llm = FakeLLM('{"best_id": "nonexistent:99"}')

    best = judge_best_candidate(llm, "roman senate ruins", candidates)

    assert best is None


def test_judge_best_candidate_skips_llm_call_when_no_candidates():
    llm = FakeLLM('{"best_id": null}')

    best = judge_best_candidate(llm, "roman senate ruins", [])

    assert best is None
    assert llm.prompts == []
