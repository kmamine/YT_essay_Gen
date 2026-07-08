import pytest

from essaygen.assembly.thumbnail import build_thumbnail_hook_prompt, parse_thumbnail_hook_response
from essaygen.core.errors import FatalError


def test_build_thumbnail_hook_prompt_includes_title_and_thesis():
    prompt = build_thumbnail_hook_prompt(
        title="The Fall of Rome", thesis="Rome collapsed from within, not from barbarian invasion."
    )

    assert "The Fall of Rome" in prompt
    assert "Rome collapsed from within, not from barbarian invasion." in prompt


def test_build_thumbnail_hook_prompt_instructs_short_punchy_length():
    # YouTube thumbnail text needs to be readable at a small size in a
    # crowded feed -- a full sentence or the video's actual title (often
    # long) doesn't work the same way a punchy few-word hook does.
    prompt = build_thumbnail_hook_prompt(title="t", thesis="t")

    lowered = prompt.lower()
    assert "3-6 word" in lowered or "3 to 6 word" in lowered
    assert "thumbnail" in lowered


def test_parse_thumbnail_hook_response_extracts_hook_field():
    assert parse_thumbnail_hook_response('{"hook": "Rome\'s Fatal Mistake"}') == "Rome's Fatal Mistake"


def test_parse_thumbnail_hook_response_raises_fatal_error_on_invalid_json():
    with pytest.raises(FatalError):
        parse_thumbnail_hook_response("not json")
