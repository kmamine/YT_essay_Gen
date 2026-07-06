from essaygen.providers.image.stock.candidate import StockCandidate
from essaygen.providers.llm.base import LLMProvider
from essaygen.providers.llm.parsing import extract_json_object


def build_judge_prompt(stock_query: str, candidates: list[StockCandidate]) -> str:
    candidates_block = "\n".join(f"- id: {c.id}, description: {c.description}" for c in candidates)
    return (
        f'A video segment needs a visual matching this search: "{stock_query}"\n\n'
        "Candidate images found (photos, paintings, illustrations, maps, "
        "3D renders, and abstract art — be creative, all of these media "
        "types are equally welcome candidates, not just photos):\n"
        f"{candidates_block}\n\n"
        "Judge in this priority order, and pick from the HIGHEST tier that has "
        "a usable candidate. A candidate does NOT need to depict every literal "
        "detail of the query (e.g. the exact action described) — matching the "
        "right era, culture, subjects, and setting is enough to qualify; don't "
        "reject a good real photo just because one specific detail isn't shown:\n"
        "1. A real photo of the right era/culture/subjects/setting (e.g. "
        "Roman-era soldiers/reenactors for a Roman military query) — always "
        "prefer this over a generic illustration if one is available, even if "
        "the illustration looks superficially closer to the query's wording.\n"
        "2. A painting, illustration, map, 3D render, or abstract artwork "
        "that specifically depicts or evokes the scene, subject, or theme "
        "(not just a generic mascot/clipart of the general topic).\n"
        "3. Last resort: any candidate from the same broader civilization or "
        "empire as the query, used purely as a background/atmosphere image — "
        "accept this regardless of tone/mood mismatch AND regardless of "
        "exact country/region mismatch. The specific country or city named "
        "in the query does NOT need to match: a Colosseum or gladiator-arena "
        "photo taken in Rome, Italy is an acceptable background for a "
        "'Roman Britain' query, because Roman Britain was part of the same "
        "Roman Empire and shares its visual culture — do not reject it just "
        "because the photo's setting is Italy rather than Britain. Only "
        "empire/civilization-level relevance is required at this tier, not "
        "region-level or tonal precision.\n"
        "Only say none qualify if every candidate belongs to a clearly "
        "different civilization, era, or culture entirely (e.g. modern-day "
        "office buildings, or Egyptian imagery, for a Roman-era query). A "
        "mismatch limited to country/region within the same empire, or to "
        "tone/mood, is never grounds to say none qualify.\n"
        "Before answering, reason step-by-step through tiers 1, 2, then 3 "
        "against the actual candidates listed above, and put that reasoning "
        'in a "reason" field. Respond ONLY with JSON matching this shape: '
        '{"reason": "<your step-by-step reasoning through the tiers>", '
        '"best_id": "<id>"} or {"reason": "<reasoning>", "best_id": null}'
    )


def parse_judge_response(raw: str) -> str | None:
    return extract_json_object(raw).get("best_id")


def judge_best_candidate(
    llm: LLMProvider, stock_query: str, candidates: list[StockCandidate]
) -> StockCandidate | None:
    if not candidates:
        return None

    prompt = build_judge_prompt(stock_query, candidates)
    best_id = parse_judge_response(llm.generate(prompt))
    if best_id is None:
        return None

    for candidate in candidates:
        if candidate.id == best_id:
            return candidate
    return None
