import pytest

from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext
from essaygen.core.state import ProjectState
from essaygen.models.script import Script, Section, Subsection, YoutubeMetadata
from essaygen.stages.stage05_section_build import build_section_build_stage


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
        youtube_metadata=YoutubeMetadata(title="t", description="d", tags=["t"]),
        sections=[
            Section(
                id="sec_01",
                title="Section One",
                subsections=[
                    Subsection(
                        id="sec_01_sub_01",
                        narration="n1",
                        claim="c1",
                        evidence="e1",
                        evidence_ref="fact_01",
                        image_prompt="p1",
                        stock_query="q1",
                    ),
                    Subsection(
                        id="sec_01_sub_02",
                        narration="n2",
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


def touch_subsection_media(paths, sub_id):
    (paths.audio_dir / f"{sub_id}.wav").write_bytes(b"fake-wav")
    (paths.images_dir / f"{sub_id}.png").write_bytes(b"fake-png")


def test_section_build_stage_runs_ffmpeg_per_clip_and_concats_section(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_subsection_media(paths, "sec_01_sub_01")
    touch_subsection_media(paths, "sec_01_sub_02")
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_section_build_stage(
        probe_duration=lambda path: 4.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    # 2 clip commands + 1 concat command
    assert len(ffmpeg_calls) == 3
    clip_output_args = [c[-1] for c in ffmpeg_calls[:2]]
    assert str(paths.sections_dir / "sec_01_sub_01_clip.mp4") in clip_output_args
    assert str(paths.sections_dir / "sec_01_sub_02_clip.mp4") in clip_output_args
    assert ffmpeg_calls[2][-1] == str(paths.sections_dir / "sec_01.mp4")


def test_section_build_stage_varies_pan_direction_across_clips(paths, script):
    # Each clip should get a different Ken Burns pan variant so consecutive
    # subsections don't all pan in the exact same direction.
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_subsection_media(paths, "sec_01_sub_01")
    touch_subsection_media(paths, "sec_01_sub_02")
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_section_build_stage(
        probe_duration=lambda path: 4.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    filter_1 = ffmpeg_calls[0][ffmpeg_calls[0].index("-filter_complex") + 1]
    filter_2 = ffmpeg_calls[1][ffmpeg_calls[1].index("-filter_complex") + 1]
    assert filter_1 != filter_2


def test_section_build_stage_raises_fatal_error_when_audio_missing(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    (paths.images_dir / "sec_01_sub_01.png").write_bytes(b"fake-png")
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_section_build_stage(probe_duration=lambda path: 4.0, ffmpeg_runner=lambda args: None)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_section_build_stage_raises_fatal_error_when_image_missing(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    (paths.audio_dir / "sec_01_sub_01.wav").write_bytes(b"fake-wav")
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_section_build_stage(probe_duration=lambda path: 4.0, ffmpeg_runner=lambda args: None)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_section_build_stage_raises_fatal_error_when_script_missing(paths):
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_section_build_stage(probe_duration=lambda path: 4.0, ffmpeg_runner=lambda args: None)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_section_build_stage_has_expected_name():
    stage = build_section_build_stage(probe_duration=lambda path: 4.0, ffmpeg_runner=lambda args: None)

    assert stage.name == "section_build"
