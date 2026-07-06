import pytest

from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext
from essaygen.core.state import ProjectState
from essaygen.models.research import ResearchDoc
from essaygen.stages.stage01_research import build_research_stage


@pytest.fixture
def paths(tmp_path):
    p = ProjectPaths(projects_root=tmp_path, slug="rome")
    p.ensure_dirs()
    return p


def fake_fetch(topic, user_agent, client=None):
    return (
        "Rome was founded in 753 BC, according to legend and tradition. "
        "It became a republic in 509 BC after the monarchy fell.",
        "https://en.wikipedia.org/wiki/Rome",
    )


def test_research_stage_writes_research_json_with_facts(paths):
    state = ProjectState(topic="Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_research_stage(user_agent="EssayGen/0.1 (test@example.com)", fetch=fake_fetch)

    stage.run(ctx)

    assert paths.research_json.exists()
    doc = ResearchDoc.model_validate_json(paths.research_json.read_text())
    assert doc.topic == "Rome"
    assert len(doc.facts) == 2
    assert doc.facts[0].source_url == "https://en.wikipedia.org/wiki/Rome"


def test_research_stage_raises_fatal_error_when_topic_missing(paths):
    state = ProjectState(topic=None)
    ctx = RunContext(paths=paths, state=state)
    stage = build_research_stage(user_agent="EssayGen/0.1 (test@example.com)", fetch=fake_fetch)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_research_stage_passes_configured_user_agent_to_fetch(paths):
    captured = {}

    def capturing_fetch(topic, user_agent, client=None):
        captured["topic"] = topic
        captured["user_agent"] = user_agent
        return "A sufficiently long sentence about the topic for testing.", "https://en.wikipedia.org/wiki/Rome"

    state = ProjectState(topic="Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_research_stage(user_agent="EssayGen/0.1 (test@example.com)", fetch=capturing_fetch)

    stage.run(ctx)

    assert captured["topic"] == "Rome"
    assert captured["user_agent"] == "EssayGen/0.1 (test@example.com)"


def test_research_stage_has_expected_name_and_artifact_path(paths):
    stage = build_research_stage(user_agent="EssayGen/0.1 (test@example.com)", fetch=fake_fetch)

    assert stage.name == "research"
    assert stage.artifact_path(paths) == paths.research_json


def test_research_stage_writes_non_ascii_facts_without_encoding_error(paths):
    def unicode_fetch(topic, user_agent, client=None):
        return (
            "The word is pronounced ˈRoma with stress on the first syllable in Latin. "
            "The city café culture historically shaped Zągrzębie's identity too.",
            "https://en.wikipedia.org/wiki/Rome",
        )

    state = ProjectState(topic="Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_research_stage(user_agent="EssayGen/0.1 (test@example.com)", fetch=unicode_fetch)

    stage.run(ctx)

    doc = ResearchDoc.model_validate_json(paths.research_json.read_text(encoding="utf-8"))
    assert "ˈRoma" in doc.facts[0].text
