from essaygen.providers.llm.parsing import extract_json_object


def build_music_query_prompt(title: str, thesis: str) -> str:
    return (
        f'A video essay titled "{title}" argues: "{thesis}"\n\n'
        "Generate a short background-music search query capturing the "
        "video's mood/genre. The query MUST be 2-3 words only -- longer "
        "phrases reliably return zero results from the music search API. "
        "Use common, generic genre/production descriptors that are likely "
        'to appear as music tags -- e.g. "dark ambient", "epic orchestral", '
        '"dramatic cinematic", "ambient drone" -- rather than literary or '
        'emotional words like "somber", "historical", or "documentary", '
        "which frequently return zero results even though they sound "
        'reasonable. Respond ONLY with JSON matching this shape: '
        '{"query": "<2-3 word mood/genre phrase>"}'
    )


def parse_music_query_response(raw: str) -> str:
    return extract_json_object(raw)["query"]
