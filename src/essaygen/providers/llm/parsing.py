import json
import re

from essaygen.core.errors import FatalError

_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json_object(raw: str) -> dict:
    stripped = _CODE_FENCE_RE.sub("", raw.strip()).strip()
    try:
        return json.loads(stripped, strict=False)
    except json.JSONDecodeError as exc:
        raise FatalError(f"LLM response was not valid JSON: {exc}") from exc
