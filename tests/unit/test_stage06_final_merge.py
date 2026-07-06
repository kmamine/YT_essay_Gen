import json
from pathlib import Path

import pytest

from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext
from essaygen.core.state import ProjectState
from essaygen.models.script import Script, Section, Subsection, YoutubeMetadata
from essaygen.stages.stage06_final_merge import build_final_merge_stage


@pytest.fixture
def paths(tmp_path):
    p = ProjectPaths(projects_root=tmp_path, slug="rome")
    p.ensure_dirs()
    return p


@pytest.fixture
def script():
    return Script(
        title="t",
        thesis="t",
        youtube_metadata=YoutubeMetadata(title="YT Title", description="YT Desc", tags=["rome"]),
        sections=[
            Section(
                id="sec_01",
                title="Section One",
                subsections=[
                    Subsection(
                        id="sec_01_sub_01",
                        narration="First narration.",
                        claim="c1",
                        evidence="e1",
                        evidence_ref="fact_01",
                        image_prompt="p1",
                        stock_query="q1",
                    )
                ],
            ),
            Section(
                id="sec_02",
                title="Section Two",
                subsections=[
                    Subsection(
                        id="sec_02_sub_01",
                        narration="Second narration.",
                        claim="c2",
                        evidence="e2",
                        evidence_ref="fact_02",
                        image_prompt="p2",
                        stock_query="q2",
                    )
                ],
            ),
        ],
    )


def touch_section_videos(paths, script):
    for section in script.sections:
        (paths.sections_dir / f"{section.id}.mp4").write_bytes(b"fake-section-video")
    for section in script.sections:
        for sub in section.subsections:
            (paths.audio_dir / f"{sub.id}.wav").write_bytes(b"fake-wav")


def test_final_merge_concats_burns_captions_and_writes_metadata(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=True,
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    assert len(ffmpeg_calls) == 2  # concat + caption burn
    assert ffmpeg_calls[1][-1] == str(paths.final_mp4)
    assert paths.captions_srt.exists()
    srt_content = paths.captions_srt.read_text(encoding="utf-8")
    assert "First narration." in srt_content
    assert "Second narration." in srt_content
    metadata = json.loads(paths.metadata_json.read_text(encoding="utf-8"))
    assert metadata["title"] == "YT Title"

    # burn command uses drawtext (not `subtitles`, which needs libass and is
    # unavailable in conda-forge's Windows ffmpeg builds), fed via textfile=
    # so narration text with apostrophes/colons doesn't need inline escaping.
    # The filter graph itself is read from a file via -filter_script:v
    # (not inline -vf) since many cues can exceed Windows' command-line
    # length limit.
    assert "-filter_script:v" in ffmpeg_calls[1]
    filter_script_path = Path(ffmpeg_calls[1][ffmpeg_calls[1].index("-filter_script:v") + 1])
    burn_filter = filter_script_path.read_text(encoding="utf-8")
    assert "drawtext" in burn_filter
    assert "subtitles" not in burn_filter
    assert "textfile=" in burn_filter
    cue_files = list((paths.root / "caption_cues").glob("*.txt"))
    assert len(cue_files) == 2
    assert metadata["tags"] == ["rome"]


def test_final_merge_skips_caption_burn_when_captions_disabled(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=False,
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    assert len(ffmpeg_calls) == 1  # concat only
    assert ffmpeg_calls[0][-1] == str(paths.final_mp4)
    assert not paths.captions_srt.exists()


def test_final_merge_raises_fatal_error_when_section_video_missing(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(probe_duration=lambda path: 3.0, ffmpeg_runner=lambda args: None)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_final_merge_raises_fatal_error_when_script_missing(paths):
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(probe_duration=lambda path: 3.0, ffmpeg_runner=lambda args: None)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_final_merge_stage_has_expected_name_and_artifact_path(paths):
    stage = build_final_merge_stage(probe_duration=lambda path: 3.0, ffmpeg_runner=lambda args: None)

    assert stage.name == "final_merge"
    assert stage.artifact_path(paths) == paths.final_mp4
