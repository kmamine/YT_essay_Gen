import pytest

from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext
from essaygen.core.state import ProjectState
from essaygen.models.research import Fact, ResearchDoc
from essaygen.models.stance import Stance
from essaygen.stages.stage02_stance import build_stance_prompt, build_stance_stage, parse_stance_response


@pytest.fixture
def paths(tmp_path):
    p = ProjectPaths(projects_root=tmp_path, slug="rome")
    p.ensure_dirs()
    return p


@pytest.fixture
def research_doc():
    return ResearchDoc(
        topic="Fall of Rome",
        facts=[
            Fact(id="fact_01", text="Rome fell in 476 AD.", source_url="https://en.wikipedia.org/wiki/Rome"),
        ],
    )


def test_build_stance_prompt_includes_topic_and_facts(research_doc):
    prompt = build_stance_prompt(research_doc)

    assert "Fall of Rome" in prompt
    assert "Rome fell in 476 AD." in prompt


class FakeLLM:
    name = "fake"

    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_parse_stance_response_parses_plain_json():
    raw = '{"thesis": "Rome rotted from within.", "angle": "Contrarian take."}'

    stance = parse_stance_response(raw)

    assert stance == Stance(thesis="Rome rotted from within.", angle="Contrarian take.")


def test_parse_stance_response_strips_markdown_code_fence():
    raw = '```json\n{"thesis": "Rome rotted from within.", "angle": "Contrarian take."}\n```'

    stance = parse_stance_response(raw)

    assert stance.thesis == "Rome rotted from within."


def test_parse_stance_response_raises_fatal_error_on_invalid_json():
    with pytest.raises(FatalError):
        parse_stance_response("not json at all")


def test_stance_stage_reads_research_and_writes_stance_json(paths, research_doc):
    paths.research_json.write_text(research_doc.model_dump_json())
    llm = FakeLLM('{"thesis": "Rome rotted from within.", "angle": "Contrarian take."}')
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_stance_stage(llm)

    stage.run(ctx)

    assert paths.stance_json.exists()
    stance = Stance.model_validate_json(paths.stance_json.read_text())
    assert stance.thesis == "Rome rotted from within."
    assert "Fall of Rome" in llm.prompts[0]


def test_stance_stage_raises_fatal_error_when_research_missing(paths):
    llm = FakeLLM('{"thesis": "x", "angle": "y"}')
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_stance_stage(llm)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_stance_stage_has_expected_name_and_artifact_path(paths):
    stage = build_stance_stage(FakeLLM("{}"))

    assert stage.name == "stance"
    assert stage.artifact_path(paths) == paths.stance_json
