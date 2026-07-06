from pathlib import Path

from essaygen.core.project import ProjectPaths, slugify


def test_slugify_lowercases_and_hyphenates():
    assert slugify("Fall of Rome") == "fall-of-rome"


def test_slugify_strips_punctuation():
    assert slugify("Rome's Fall: A Reassessment!") == "romes-fall-a-reassessment"


def test_slugify_collapses_repeated_whitespace():
    assert slugify("Rome   Fall") == "rome-fall"


def test_project_paths_resolve_under_slug_directory(tmp_path):
    paths = ProjectPaths(projects_root=tmp_path, slug="fall-of-rome")

    assert paths.root == tmp_path / "fall-of-rome"
    assert paths.state_json == tmp_path / "fall-of-rome" / "state.json"
    assert paths.research_json == tmp_path / "fall-of-rome" / "research.json"
    assert paths.script_json == tmp_path / "fall-of-rome" / "script.json"
    assert paths.audio_dir == tmp_path / "fall-of-rome" / "audio"
    assert paths.images_dir == tmp_path / "fall-of-rome" / "images"
    assert paths.captions_srt == tmp_path / "fall-of-rome" / "captions.srt"
    assert paths.sections_dir == tmp_path / "fall-of-rome" / "sections"
    assert paths.final_mp4 == tmp_path / "fall-of-rome" / "final.mp4"
    assert paths.metadata_json == tmp_path / "fall-of-rome" / "metadata.json"
    assert paths.video_id_txt == tmp_path / "fall-of-rome" / "video_id.txt"
    assert paths.tracking_dir == tmp_path / "fall-of-rome" / "tracking"
    assert paths.insight_json == tmp_path / "fall-of-rome" / "insight.json"


def test_ensure_dirs_creates_all_subdirectories(tmp_path):
    paths = ProjectPaths(projects_root=tmp_path, slug="fall-of-rome")

    paths.ensure_dirs()

    assert paths.audio_dir.is_dir()
    assert paths.images_dir.is_dir()
    assert paths.sections_dir.is_dir()
    assert paths.tracking_dir.is_dir()
