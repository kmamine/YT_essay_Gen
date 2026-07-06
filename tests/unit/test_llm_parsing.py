import pytest

from essaygen.core.errors import FatalError
from essaygen.providers.llm.parsing import extract_json_object


def test_extract_json_object_parses_plain_json():
    assert extract_json_object('{"best_id": "x"}') == {"best_id": "x"}


def test_extract_json_object_strips_code_fences():
    assert extract_json_object('```json\n{"best_id": "x"}\n```') == {"best_id": "x"}


def test_extract_json_object_raises_fatal_error_on_invalid_json():
    with pytest.raises(FatalError):
        extract_json_object("not json")


def test_extract_json_object_tolerates_literal_newlines_inside_string_values():
    # Live-verified: Mistral (mistral-large-latest) frequently returns a
    # free-text reasoning field containing literal, unescaped newlines
    # inside the JSON string value (e.g. numbered multi-line reasoning),
    # which is technically invalid strict JSON and previously raised
    # FatalError even though the structure was otherwise well-formed.
    raw = '{"reason": "line one\nline two", "best_id": "pexels:1"}'

    assert extract_json_object(raw) == {"reason": "line one\nline two", "best_id": "pexels:1"}
