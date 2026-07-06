import pytest

from essaygen.core.project import ProjectPaths
from essaygen.core.runner import Runner, StageDef
from essaygen.core.state import ProjectState, load_state


@pytest.fixture
def paths(tmp_path):
    p = ProjectPaths(projects_root=tmp_path, slug="rome")
    p.ensure_dirs()
    return p


def make_stage(name, calls, artifact_path=None, should_fail=False):
    def run(ctx):
        calls.append(name)
        if should_fail:
            raise RuntimeError(f"{name} exploded")
        if artifact_path:
            artifact_path(ctx.paths).write_text("{}")

    return StageDef(name=name, run=run, artifact_path=artifact_path)


def test_runner_executes_stages_in_order(paths):
    calls = []
    stages = [make_stage("research", calls), make_stage("stance", calls), make_stage("script", calls)]
    runner = Runner(stages)
    state = ProjectState()

    runner.execute(paths, state)

    assert calls == ["research", "stance", "script"]
    assert state.is_stage_done("research")
    assert state.is_stage_done("stance")
    assert state.is_stage_done("script")


def test_runner_skips_stage_already_marked_done(paths):
    calls = []
    stages = [make_stage("research", calls), make_stage("stance", calls)]
    runner = Runner(stages)
    state = ProjectState()
    state.mark_stage_done("research")

    runner.execute(paths, state)

    assert calls == ["stance"]


def test_runner_reruns_stage_if_artifact_missing_despite_state_done(paths):
    calls = []
    artifact_path = lambda p: p.research_json
    stages = [make_stage("research", calls, artifact_path=artifact_path)]
    runner = Runner(stages)
    state = ProjectState()
    state.mark_stage_done("research", artifact="research.json")
    # artifact file does not actually exist on disk -> drift

    runner.execute(paths, state)

    assert calls == ["research"]
    assert paths.research_json.exists()


def test_runner_skips_already_done_stage_whose_artifact_path_function_returns_none(paths):
    # Regression test: several real stages (tts, image_gen, section_build)
    # define artifact_path as a function that always returns None (no single
    # artifact file to check — resumability is tracked per-unit instead),
    # rather than passing artifact_path=None to StageDef directly. The old
    # _artifact_ok only checked "is the function itself None", so calling
    # the function and getting None back crashed with
    # AttributeError: 'NoneType' object has no attribute 'exists'.
    calls = []

    def always_none_artifact_path(paths):
        return None

    stages = [make_stage("tts", calls, artifact_path=always_none_artifact_path)]
    runner = Runner(stages)
    state = ProjectState()
    state.mark_stage_done("tts")

    runner.execute(paths, state)

    assert calls == []


def test_runner_respects_from_stage_and_to_stage_bounds(paths):
    calls = []
    stages = [
        make_stage("research", calls),
        make_stage("stance", calls),
        make_stage("script", calls),
        make_stage("assemble", calls),
    ]
    runner = Runner(stages)
    state = ProjectState()

    runner.execute(paths, state, from_stage="stance", to_stage="script")

    assert calls == ["stance", "script"]


def test_runner_persists_state_to_disk_after_each_stage(paths):
    calls = []
    stages = [make_stage("research", calls)]
    runner = Runner(stages)
    state = ProjectState()

    runner.execute(paths, state)

    restored = load_state(paths.state_json)
    assert restored.is_stage_done("research")


def test_runner_marks_stage_failed_and_reraises_on_error(paths):
    calls = []
    stages = [make_stage("research", calls, should_fail=True)]
    runner = Runner(stages)
    state = ProjectState()

    with pytest.raises(RuntimeError, match="research exploded"):
        runner.execute(paths, state)

    assert not state.is_stage_done("research")
    restored = load_state(paths.state_json)
    assert restored.stages["research"].status.value == "failed"
    assert "research exploded" in restored.stages["research"].last_error
