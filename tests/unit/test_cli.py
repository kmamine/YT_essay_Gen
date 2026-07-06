from typer.testing import CliRunner

import essaygen.cli as cli_module
from essaygen.cli import app
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import StageDef
from essaygen.core.state import ProjectState, load_state, save_state

runner = CliRunner()


def fake_stage(name, calls, should_fail=False):
    def run(ctx):
        calls.append(name)
        if should_fail:
            raise RuntimeError(f"{name} exploded")

    return StageDef(name=name, run=run, artifact_path=None)


def test_new_creates_project_directory_and_state_file(tmp_path):
    result = runner.invoke(app, ["new", "Fall of Rome", "--projects-root", str(tmp_path)])

    assert result.exit_code == 0
    paths = ProjectPaths(projects_root=tmp_path, slug="fall-of-rome")
    assert paths.state_json.exists()
    assert "fall-of-rome" in result.output


def test_new_persists_topic_into_state(tmp_path):
    runner.invoke(app, ["new", "Fall of Rome", "--projects-root", str(tmp_path)])

    paths = ProjectPaths(projects_root=tmp_path, slug="fall-of-rome")
    state = load_state(paths.state_json)
    assert state.topic == "Fall of Rome"


def test_new_uses_provided_slug_override(tmp_path):
    result = runner.invoke(
        app, ["new", "Fall of Rome", "--slug", "custom-slug", "--projects-root", str(tmp_path)]
    )

    assert result.exit_code == 0
    paths = ProjectPaths(projects_root=tmp_path, slug="custom-slug")
    assert paths.state_json.exists()


def test_status_reports_missing_project(tmp_path):
    result = runner.invoke(app, ["status", "unknown-slug", "--projects-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "No project found" in result.output


def test_status_reports_stage_statuses(tmp_path):
    paths = ProjectPaths(projects_root=tmp_path, slug="fall-of-rome")
    paths.ensure_dirs()
    state = ProjectState()
    state.mark_stage_done("research", artifact="research.json")
    save_state(paths.state_json, state)

    result = runner.invoke(app, ["status", "fall-of-rome", "--projects-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "research: done" in result.output


def test_list_shows_no_projects_message_when_empty(tmp_path):
    result = runner.invoke(app, ["list", "--projects-root", str(tmp_path)])

    assert result.exit_code == 0
    assert "No projects yet" in result.output


def test_list_shows_created_project_slugs(tmp_path):
    runner.invoke(app, ["new", "Fall of Rome", "--projects-root", str(tmp_path)])
    runner.invoke(app, ["new", "Rise of Byzantium", "--projects-root", str(tmp_path)])

    result = runner.invoke(app, ["list", "--projects-root", str(tmp_path)])

    assert "fall-of-rome" in result.output
    assert "rise-of-byzantium" in result.output


def test_run_executes_stages_and_reports_completion(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli_module,
        "build_default_stages",
        lambda config, secrets: [fake_stage("research", calls), fake_stage("stance", calls)],
    )
    runner.invoke(app, ["new", "Fall of Rome", "--projects-root", str(tmp_path)])

    result = runner.invoke(app, ["run", "fall-of-rome", "--projects-root", str(tmp_path)])

    assert result.exit_code == 0
    assert calls == ["research", "stance"]
    assert "complete" in result.output.lower()


def test_run_reports_missing_project(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "build_default_stages", lambda config, secrets: [])

    result = runner.invoke(app, ["run", "unknown-slug", "--projects-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "No project found" in result.output


def test_run_reports_failure_when_stage_raises(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli_module,
        "build_default_stages",
        lambda config, secrets: [fake_stage("research", calls, should_fail=True)],
    )
    runner.invoke(app, ["new", "Fall of Rome", "--projects-root", str(tmp_path)])

    result = runner.invoke(app, ["run", "fall-of-rome", "--projects-root", str(tmp_path)])

    assert result.exit_code == 1
    assert "failed" in result.output.lower()


def test_run_respects_from_stage_and_to_stage_options(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli_module,
        "build_default_stages",
        lambda config, secrets: [
            fake_stage("research", calls),
            fake_stage("stance", calls),
            fake_stage("script", calls),
        ],
    )
    runner.invoke(app, ["new", "Fall of Rome", "--projects-root", str(tmp_path)])

    runner.invoke(
        app,
        [
            "run",
            "fall-of-rome",
            "--projects-root",
            str(tmp_path),
            "--from-stage",
            "stance",
            "--to-stage",
            "stance",
        ],
    )

    assert calls == ["stance"]


def test_publish_records_video_id_when_final_mp4_exists(tmp_path):
    runner.invoke(app, ["new", "Fall of Rome", "--projects-root", str(tmp_path)])
    paths = ProjectPaths(projects_root=tmp_path, slug="fall-of-rome")
    paths.final_mp4.write_bytes(b"fake-final-video")

    result = runner.invoke(
        app, ["publish", "fall-of-rome", "--video-id", "abc123", "--projects-root", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert paths.video_id_txt.read_text(encoding="utf-8") == "abc123"
    assert "abc123" in result.output


def test_publish_reports_missing_project(tmp_path):
    result = runner.invoke(
        app, ["publish", "unknown-slug", "--video-id", "abc123", "--projects-root", str(tmp_path)]
    )

    assert result.exit_code == 1
    assert "No project found" in result.output


def test_publish_reports_missing_final_mp4(tmp_path):
    runner.invoke(app, ["new", "Fall of Rome", "--projects-root", str(tmp_path)])

    result = runner.invoke(
        app, ["publish", "fall-of-rome", "--video-id", "abc123", "--projects-root", str(tmp_path)]
    )

    assert result.exit_code == 1
    assert "final.mp4" in result.output.lower()


def test_resume_runs_only_incomplete_stages(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        cli_module,
        "build_default_stages",
        lambda config, secrets: [fake_stage("research", calls), fake_stage("stance", calls)],
    )
    runner.invoke(app, ["new", "Fall of Rome", "--projects-root", str(tmp_path)])
    paths = ProjectPaths(projects_root=tmp_path, slug="fall-of-rome")
    state = load_state(paths.state_json)
    state.mark_stage_done("research")
    save_state(paths.state_json, state)

    result = runner.invoke(app, ["resume", "fall-of-rome", "--projects-root", str(tmp_path)])

    assert result.exit_code == 0
    assert calls == ["stance"]
