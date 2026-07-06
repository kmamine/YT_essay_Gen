import pytest

from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext
from essaygen.core.state import ProjectState, load_state
from essaygen.models.script import Script, Section, Subsection, YoutubeMetadata
from essaygen.stages.stage04a_tts import build_tts_stage


@pytest.fixture
def paths(tmp_path):
    p = ProjectPaths(projects_root=tmp_path, slug="rome")
    p.ensure_dirs()
    return p


@pytest.fixture
def script():
    return Script(
        title="Rome Didn't Fall. It Quit.",
        thesis="Rome rotted from within.",
        youtube_metadata=YoutubeMetadata(title="t", description="d", tags=["t"]),
        sections=[
            Section(
                id="sec_01",
                title="Section One",
                subsections=[
                    Subsection(
                        id="sec_01_sub_01",
                        narration="First narration line.",
                        claim="c1",
                        evidence="e1",
                        evidence_ref="fact_01",
                        image_prompt="p1",
                        stock_query="q1",
                    ),
                    Subsection(
                        id="sec_01_sub_02",
                        narration="Second narration line.",
                        claim="c2",
                        evidence="e2",
                        evidence_ref="fact_02",
                        image_prompt="p2",
                        stock_query="q2",
                    ),
                ],
            )
        ],
    )


class FakeTTS:
    name = "fake_tts"

    def __init__(self):
        self.calls = []

    def synthesize(self, text, output_path):
        self.calls.append((text, output_path))
        output_path.write_text("fake-wav-bytes")


def test_tts_stage_synthesizes_each_subsection_and_writes_audio_files(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    tts = FakeTTS()
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_tts_stage(tts)

    stage.run(ctx)

    assert (paths.audio_dir / "sec_01_sub_01.wav").exists()
    assert (paths.audio_dir / "sec_01_sub_02.wav").exists()
    assert [text for text, _ in tts.calls] == ["First narration line.", "Second narration line."]
    assert state.get_unit_status("subsections", "sec_01_sub_01")["tts"] == "done"


def test_tts_stage_skips_already_completed_units_on_resume(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    tts = FakeTTS()
    state = ProjectState(topic="Fall of Rome")
    state.set_unit_status("subsections", "sec_01_sub_01", tts="done")
    ctx = RunContext(paths=paths, state=state)
    stage = build_tts_stage(tts)

    stage.run(ctx)

    assert [text for text, _ in tts.calls] == ["Second narration line."]


def test_tts_stage_persists_progress_after_each_subsection(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    tts = FakeTTS()
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_tts_stage(tts)

    stage.run(ctx)

    restored = load_state(paths.state_json)
    assert restored.get_unit_status("subsections", "sec_01_sub_02")["tts"] == "done"


def test_tts_stage_raises_fatal_error_when_script_missing(paths):
    tts = FakeTTS()
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_tts_stage(tts)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_tts_stage_has_expected_name(paths):
    stage = build_tts_stage(FakeTTS())

    assert stage.name == "tts"
