from essaygen.providers.llm.base import LLMProvider
from essaygen.providers.llm.parsing import extract_json_object
from essaygen.providers.music.candidate import MusicCandidate


def build_music_judge_prompt(thesis: str, candidates: list[MusicCandidate]) -> str:
    candidates_block = "\n".join(
        f"- id: {c.id}, description: {c.description}, duration: {c.duration_sec:.0f}s"
        for c in candidates
    )
    return (
        f'A video essay argues: "{thesis}"\n\n'
        "Candidate background-music tracks found (name and tags):\n"
        f"{candidates_block}\n\n"
        "Pick the track whose tone/mood best fits this video as a background "
        "bed -- it doesn't need to be about the topic literally, just tonally "
        "appropriate (e.g. a somber, minor-key, or ambient track suits a grim "
        "topic; upbeat/cheerful pop, dance, or comedic tracks are almost "
        "always a mismatch as a bed for serious narration and should be "
        "avoided unless every candidate is like that). Reject a candidate "
        "only if every option is a clear tonal mismatch. Pick the single "
        'best-fitting candidate\'s id. Respond ONLY with JSON matching this '
        'shape: {"best_id": "<id>"} or {"best_id": null}'
    )


def parse_music_judge_response(raw: str) -> str | None:
    return extract_json_object(raw).get("best_id")


def judge_best_music_candidate(
    llm: LLMProvider, thesis: str, candidates: list[MusicCandidate]
) -> MusicCandidate | None:
    if not candidates:
        return None

    prompt = build_music_judge_prompt(thesis, candidates)
    best_id = parse_music_judge_response(llm.generate(prompt))
    if best_id is None:
        return None

    for candidate in candidates:
        # Live-verified: the LLM sometimes drops the "provider:" prefix and
        # returns just the bare numeric suffix (e.g. "855301" instead of
        # "freesound:855301") -- match on either form rather than silently
        # treating that as "no match found".
        if candidate.id == best_id or candidate.id.rsplit(":", 1)[-1] == best_id:
            return candidate
    return None
