import json

import pytest

from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext
from essaygen.core.state import ProjectState
from essaygen.models.research import Fact, ResearchDoc
from essaygen.models.script import Script
from essaygen.models.stance import Stance
from essaygen.stages.stage03_script import build_script_prompt, build_script_stage, parse_script_response


@pytest.fixture
def paths(tmp_path):
    p = ProjectPaths(projects_root=tmp_path, slug="rome")
    p.ensure_dirs()
    return p


@pytest.fixture
def research_doc():
    return ResearchDoc(
        topic="Fall of Rome",
        facts=[Fact(id="fact_01", text="Rome fell in 476 AD.", source_url="https://en.wikipedia.org/wiki/Rome")],
    )


@pytest.fixture
def stance():
    return Stance(thesis="Rome rotted from within.", angle="Contrarian take.")


SCRIPT_JSON = {
    "title": "Rome Didn't Fall. It Quit.",
    "thesis": "Rome rotted from within.",
    "youtube_metadata": {
        "title": "Why Rome ACTUALLY Fell",
        "description": "A video essay.",
        "tags": ["rome", "history"],
    },
    "sections": [
        {
            "id": "sec_01",
            "title": "The Myth of Conquest",
            "subsections": [
                {
                    "id": "sec_01_sub_01",
                    "narration": "Rome did not fall to barbarians.",
                    "claim": "Institutional decay caused the collapse.",
                    "evidence": "Rome fell in 476 AD after prolonged internal crisis.",
                    "evidence_ref": "fact_01",
                    "image_prompt": "Crumbling senate building",
                    "stock_query": "roman senate ruins",
                }
            ],
        }
    ],
}


def test_build_script_prompt_includes_topic_thesis_and_fact_ids(research_doc, stance):
    prompt = build_script_prompt(research_doc, stance)

    assert "Fall of Rome" in prompt
    assert "Rome rotted from within." in prompt
    assert "fact_01" in prompt


def test_build_script_prompt_requests_stock_query_field(research_doc, stance):
    prompt = build_script_prompt(research_doc, stance)

    assert "stock_query" in prompt


def test_parse_script_response_parses_plain_json():
    script = parse_script_response(json.dumps(SCRIPT_JSON))

    assert script.title == "Rome Didn't Fall. It Quit."
    assert script.sections[0].subsections[0].evidence_ref == "fact_01"


def test_parse_script_response_strips_markdown_code_fence():
    raw = "```json\n" + json.dumps(SCRIPT_JSON) + "\n```"

    script = parse_script_response(raw)

    assert script.title == "Rome Didn't Fall. It Quit."


def test_parse_script_response_raises_fatal_error_on_invalid_json():
    with pytest.raises(FatalError):
        parse_script_response("not json")


class FakeLLM:
    name = "fake"

    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_script_stage_reads_research_and_stance_and_writes_script_json(paths, research_doc, stance):
    paths.research_json.write_text(research_doc.model_dump_json())
    paths.stance_json.write_text(stance.model_dump_json())
    llm = FakeLLM(json.dumps(SCRIPT_JSON))
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_script_stage(llm)

    stage.run(ctx)

    assert paths.script_json.exists()
    script = Script.model_validate_json(paths.script_json.read_text())
    assert script.title == "Rome Didn't Fall. It Quit."


def test_script_stage_raises_fatal_error_when_research_missing(paths, stance):
    paths.stance_json.write_text(stance.model_dump_json())
    llm = FakeLLM(json.dumps(SCRIPT_JSON))
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_script_stage(llm)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_script_stage_raises_fatal_error_when_stance_missing(paths, research_doc):
    paths.research_json.write_text(research_doc.model_dump_json())
    llm = FakeLLM(json.dumps(SCRIPT_JSON))
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_script_stage(llm)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_script_stage_has_expected_name_and_artifact_path(paths):
    stage = build_script_stage(FakeLLM("{}"))

    assert stage.name == "script"
    assert stage.artifact_path(paths) == paths.script_json
