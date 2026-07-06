import json

from essaygen.core.errors import FatalError
from essaygen.core.fallback_chain import Tier, run_with_fallback
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext, StageDef
from essaygen.core.state import save_state
from essaygen.models.script import Script
from essaygen.providers.image.base import ImageClient, ImageRequest


def build_image_gen_stage(
    providers: list[ImageClient], retries: dict[str, int] | None = None
) -> StageDef:
    def run(ctx: RunContext) -> None:
        if not ctx.paths.script_json.exists():
            raise FatalError("Cannot run image_gen stage: script.json missing")

        script = Script.model_validate_json(ctx.paths.script_json.read_text(encoding="utf-8"))

        for section in script.sections:
            for subsection in section.subsections:
                unit = ctx.state.get_unit_status("subsections", subsection.id)
                if unit.get("image") == "done":
                    continue

                request = ImageRequest(
                    image_prompt=subsection.image_prompt, stock_query=subsection.stock_query
                )
                tiers = [
                    Tier(name=provider.name, call=_make_call(provider, request))
                    for provider in providers
                ]
                image_bytes, tier_name = run_with_fallback(tiers, retries=retries)

                image_path = ctx.paths.images_dir / f"{subsection.id}.png"
                image_path.write_bytes(image_bytes)

                meta_path = ctx.paths.images_dir / f"{subsection.id}.meta.json"
                meta_path.write_text(json.dumps({"tier": tier_name}), encoding="utf-8")

                ctx.state.set_unit_status(
                    "subsections", subsection.id, **{**unit, "image": "done", "image_tier": tier_name}
                )
                save_state(ctx.paths.state_json, ctx.state)

    def artifact_path(paths: ProjectPaths):
        return None

    return StageDef(name="image_gen", run=run, artifact_path=artifact_path)


def _make_call(provider: ImageClient, request: ImageRequest):
    def call() -> bytes:
        return provider.generate(request)

    return call
