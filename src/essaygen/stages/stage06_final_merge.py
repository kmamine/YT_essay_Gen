from typing import Callable

from essaygen.assembly.captions import build_cues, render_srt
from essaygen.assembly.ffmpeg_ops import (
    build_caption_burn_command,
    build_caption_filter,
    build_concat_command,
    build_concat_file_content,
    probe_duration_sec,
    resolve_output_dimensions,
    run_ffmpeg,
    write_cue_textfiles,
)
from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext, StageDef
from essaygen.models.script import Script


def build_final_merge_stage(
    captions: bool = True,
    aspect_ratio: str = "16:9",
    probe_duration: Callable = probe_duration_sec,
    ffmpeg_runner: Callable = run_ffmpeg,
) -> StageDef:
    def run(ctx: RunContext) -> None:
        if not ctx.paths.script_json.exists():
            raise FatalError("Cannot run final_merge stage: script.json missing")

        script = Script.model_validate_json(ctx.paths.script_json.read_text(encoding="utf-8"))

        section_paths = []
        for section in script.sections:
            section_path = ctx.paths.sections_dir / f"{section.id}.mp4"
            if not section_path.exists():
                raise FatalError(
                    f"Missing section video for {section.id}; run the section_build stage first"
                )
            section_paths.append(section_path)

        concat_file = ctx.paths.root / "final_concat.txt"
        concat_file.write_text(build_concat_file_content(section_paths), encoding="utf-8")

        merged_path = (ctx.paths.root / "merged.mp4") if captions else ctx.paths.final_mp4
        ffmpeg_runner(build_concat_command(concat_file, merged_path))

        if captions:
            subsections = [sub for section in script.sections for sub in section.subsections]
            narrations = [sub.narration for sub in subsections]
            durations = [probe_duration(ctx.paths.audio_dir / f"{sub.id}.wav") for sub in subsections]
            cues = build_cues(narrations, durations)
            ctx.paths.captions_srt.write_text(render_srt(cues), encoding="utf-8")

            width, height = resolve_output_dimensions(aspect_ratio)
            cue_paths = write_cue_textfiles(
                cues, ctx.paths.root / "caption_cues", width=width, height=height
            )
            filter_str = build_caption_filter(list(zip(cues, cue_paths)), width, height)
            filter_script_path = ctx.paths.root / "caption_filter.txt"
            filter_script_path.write_text(filter_str, encoding="utf-8")
            ffmpeg_runner(
                build_caption_burn_command(merged_path, filter_script_path, ctx.paths.final_mp4)
            )

        ctx.paths.metadata_json.write_text(
            script.youtube_metadata.model_dump_json(indent=2), encoding="utf-8"
        )

    def artifact_path(paths: ProjectPaths):
        return paths.final_mp4

    return StageDef(name="final_merge", run=run, artifact_path=artifact_path)
