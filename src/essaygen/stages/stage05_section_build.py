from typing import Callable

from essaygen.assembly.ffmpeg_ops import (
    build_concat_command,
    build_concat_file_content,
    build_image_clip_command,
    probe_duration_sec,
    resolve_output_dimensions,
    run_ffmpeg,
)
from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext, StageDef
from essaygen.models.script import Script


def build_section_build_stage(
    aspect_ratio: str = "16:9",
    ken_burns: bool = True,
    fill_mode: str = "blur",
    probe_duration: Callable = probe_duration_sec,
    ffmpeg_runner: Callable = run_ffmpeg,
) -> StageDef:
    def run(ctx: RunContext) -> None:
        if not ctx.paths.script_json.exists():
            raise FatalError("Cannot run section_build stage: script.json missing")

        script = Script.model_validate_json(ctx.paths.script_json.read_text(encoding="utf-8"))
        width, height = resolve_output_dimensions(aspect_ratio)

        pan_variant = 0
        for section in script.sections:
            clip_paths = []
            for subsection in section.subsections:
                audio_path = ctx.paths.audio_dir / f"{subsection.id}.wav"
                image_path = ctx.paths.images_dir / f"{subsection.id}.png"
                if not audio_path.exists():
                    raise FatalError(f"Missing audio for {subsection.id}; run the tts stage first")
                if not image_path.exists():
                    raise FatalError(
                        f"Missing image for {subsection.id}; run the image_gen stage first"
                    )

                duration = probe_duration(audio_path)
                clip_path = ctx.paths.sections_dir / f"{subsection.id}_clip.mp4"
                ffmpeg_runner(
                    build_image_clip_command(
                        image_path=image_path,
                        audio_path=audio_path,
                        output_path=clip_path,
                        duration_sec=duration,
                        width=width,
                        height=height,
                        ken_burns=ken_burns,
                        pan_variant=pan_variant,
                        fill_mode=fill_mode,
                    )
                )
                clip_paths.append(clip_path)
                pan_variant += 1

            concat_file = ctx.paths.sections_dir / f"{section.id}_concat.txt"
            concat_file.write_text(build_concat_file_content(clip_paths), encoding="utf-8")
            section_output = ctx.paths.sections_dir / f"{section.id}.mp4"
            ffmpeg_runner(build_concat_command(concat_file, section_output))

    def artifact_path(paths: ProjectPaths):
        return None

    return StageDef(name="section_build", run=run, artifact_path=artifact_path)
