from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext, StageDef
from essaygen.core.state import save_state
from essaygen.models.script import Script
from essaygen.providers.tts.pocket_tts import PocketTTSProvider


def build_tts_stage(tts: PocketTTSProvider) -> StageDef:
    def run(ctx: RunContext) -> None:
        if not ctx.paths.script_json.exists():
            raise FatalError("Cannot run tts stage: script.json missing")

        script = Script.model_validate_json(ctx.paths.script_json.read_text(encoding="utf-8"))

        for section in script.sections:
            for subsection in section.subsections:
                unit = ctx.state.get_unit_status("subsections", subsection.id)
                if unit.get("tts") == "done":
                    continue

                output_path = ctx.paths.audio_dir / f"{subsection.id}.wav"
                tts.synthesize(subsection.narration, output_path)

                ctx.state.set_unit_status("subsections", subsection.id, **{**unit, "tts": "done"})
                save_state(ctx.paths.state_json, ctx.state)

    def artifact_path(paths: ProjectPaths):
        return None

    return StageDef(name="tts", run=run, artifact_path=artifact_path)
