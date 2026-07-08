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


def test_final_merge_mixes_music_bed_and_burns_captions(paths, script, tmp_path):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    music_path = tmp_path / "bed.mp3"
    music_path.write_bytes(b"fake-music")
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=True,
        music_bed_path=str(music_path),
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    assert len(ffmpeg_calls) == 3  # concat + music mix + caption burn
    music_mix_call = ffmpeg_calls[1]
    assert str(music_path) in music_mix_call
    assert "-filter_complex" in music_mix_call
    caption_burn_call = ffmpeg_calls[2]
    assert caption_burn_call[-1] == str(paths.final_mp4)
    # caption burn must read from the music-mixed video, not the plain concat
    burn_input = caption_burn_call[caption_burn_call.index("-i") + 1]
    music_mix_output = music_mix_call[-1]
    assert burn_input == music_mix_output


def test_final_merge_mixes_music_bed_without_captions(paths, script, tmp_path):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    music_path = tmp_path / "bed.mp3"
    music_path.write_bytes(b"fake-music")
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=False,
        music_bed_path=str(music_path),
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    assert len(ffmpeg_calls) == 2  # concat + music mix (mixing directly to final_mp4)
    music_mix_call = ffmpeg_calls[1]
    assert music_mix_call[-1] == str(paths.final_mp4)


def test_final_merge_skips_music_mix_when_not_configured(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=True,
        music_bed_path=None,
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    assert len(ffmpeg_calls) == 2  # concat + caption burn only, no music mix call


def test_final_merge_raises_fatal_error_when_music_bed_path_missing(paths, script, tmp_path):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=True,
        music_bed_path=str(tmp_path / "does_not_exist.mp3"),
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: None,
    )

    with pytest.raises(FatalError):
        stage.run(ctx)


class FakeMusicBedProvider:
    def __init__(self, cached_path):
        self.cached_path = cached_path
        self.fetch_calls = []

    def fetch_and_cache(self, cache_path, title, thesis):
        self.fetch_calls.append((cache_path, title, thesis))
        return self.cached_path


def test_final_merge_fetches_and_mixes_music_via_provider_when_no_explicit_path(
    paths, script, tmp_path
):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    cached_music = tmp_path / "cached_bed.mp3"
    cached_music.write_bytes(b"cached")
    provider = FakeMusicBedProvider(cached_path=cached_music)
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=True,
        music_bed_provider=provider,
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    # cache path is computed per-project (under the project's own root),
    # not supplied externally -- and the script's title/thesis are passed
    # through so the provider can pick a track that tonally fits this
    # specific video, not a fixed generic query
    assert len(provider.fetch_calls) == 1
    cache_path, title, thesis = provider.fetch_calls[0]
    assert cache_path == paths.root / "music_bed.mp3"
    assert title == script.title
    assert thesis == script.thesis
    assert len(ffmpeg_calls) == 3  # concat + music mix + caption burn
    music_mix_call = ffmpeg_calls[1]
    assert str(cached_music) in music_mix_call


def test_final_merge_skips_music_when_provider_finds_no_candidates(paths, script, tmp_path):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    provider = FakeMusicBedProvider(cached_path=None)
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=True,
        music_bed_provider=provider,
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    assert len(ffmpeg_calls) == 2  # concat + caption burn only, no music mix call


def test_final_merge_prefers_explicit_music_bed_path_over_provider(paths, script, tmp_path):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    explicit_music = tmp_path / "explicit_bed.mp3"
    explicit_music.write_bytes(b"explicit")
    provider = FakeMusicBedProvider(cached_path=tmp_path / "should_not_be_used.mp3")
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=True,
        music_bed_path=str(explicit_music),
        music_bed_provider=provider,
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    assert provider.fetch_calls == []
    music_mix_call = ffmpeg_calls[1]
    assert str(explicit_music) in music_mix_call


def test_final_merge_passes_music_mode_to_mix_command(paths, script, tmp_path):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    explicit_music = tmp_path / "explicit_bed.mp3"
    explicit_music.write_bytes(b"explicit")
    ffmpeg_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=True,
        music_bed_path=str(explicit_music),
        music_mode="duck",
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: ffmpeg_calls.append(args),
    )

    stage.run(ctx)

    music_mix_call = ffmpeg_calls[1]
    filter_complex = music_mix_call[music_mix_call.index("-filter_complex") + 1]
    assert "sidechaincompress" in filter_complex


class FakeLLM:
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.response


def test_final_merge_generates_thumbnail_from_first_subsection_image(paths, script, tmp_path):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    (paths.images_dir / "sec_01_sub_01.png").write_bytes(b"fake-image")
    llm = FakeLLM('{"hook": "Rome\'s Fatal Mistake"}')
    render_calls = []
    font_path = tmp_path / "font.ttf"
    font_path.write_bytes(b"fake-font")
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=False,
        llm=llm,
        thumbnail_font_path=str(font_path),
        thumbnail_renderer=lambda *args, **kwargs: render_calls.append((args, kwargs)),
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: None,
    )

    stage.run(ctx)

    assert len(render_calls) == 1
    args, kwargs = render_calls[0]
    assert args[0] == paths.images_dir / "sec_01_sub_01.png"
    assert args[1] == "Rome's Fatal Mistake"
    assert args[2] == paths.thumbnail_jpg
    assert args[3] == font_path
    assert any("t" in p for p in llm.prompts)  # hook prompt was actually sent


def test_final_merge_skips_thumbnail_when_llm_not_provided(paths, script, tmp_path):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    (paths.images_dir / "sec_01_sub_01.png").write_bytes(b"fake-image")
    render_calls = []
    font_path = tmp_path / "font.ttf"
    font_path.write_bytes(b"fake-font")
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=False,
        thumbnail_font_path=str(font_path),
        thumbnail_renderer=lambda *args, **kwargs: render_calls.append((args, kwargs)),
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: None,
    )

    stage.run(ctx)

    assert render_calls == []


def test_final_merge_skips_thumbnail_when_font_path_not_provided(paths, script, tmp_path):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    touch_section_videos(paths, script)
    (paths.images_dir / "sec_01_sub_01.png").write_bytes(b"fake-image")
    llm = FakeLLM('{"hook": "Hook"}')
    render_calls = []
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_final_merge_stage(
        captions=False,
        llm=llm,
        thumbnail_renderer=lambda *args, **kwargs: render_calls.append((args, kwargs)),
        probe_duration=lambda path: 3.0,
        ffmpeg_runner=lambda args: None,
    )

    stage.run(ctx)

    assert render_calls == []


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
