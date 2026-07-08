from pathlib import Path

import typer

from essaygen.config import PipelineConfig, Secrets, load_pipeline_config, load_secrets
from essaygen.core.project import ProjectPaths, slugify
from essaygen.core.runner import Runner, StageDef
from essaygen.core.state import ProjectState, load_state, save_state
from essaygen.providers.image.cloudflare_sdxl import CloudflareSDXLProvider
from essaygen.providers.image.local_flux import LocalFluxProvider
from essaygen.providers.image.nano_banana import NanoBananaProvider
from essaygen.providers.image.stock.pexels import PexelsClient
from essaygen.providers.image.stock.pixabay import PixabayClient
from essaygen.providers.image.stock.provider import StockPhotoProvider
from essaygen.providers.llm.mistral import MistralProvider
from essaygen.providers.music.freesound import FreesoundClient
from essaygen.providers.music.provider import MusicBedProvider
from essaygen.providers.tts.pocket_tts import PocketTTSProvider, resolve_voice_cache_path
from essaygen.stages.stage01_research import build_research_stage
from essaygen.stages.stage02_stance import build_stance_stage
from essaygen.stages.stage03_script import build_script_stage
from essaygen.stages.stage04a_tts import build_tts_stage
from essaygen.stages.stage04b_image_gen import build_image_gen_stage
from essaygen.stages.stage05_section_build import build_section_build_stage
from essaygen.stages.stage06_final_merge import build_final_merge_stage

app = typer.Typer()


def build_default_stages(config: PipelineConfig, secrets: Secrets) -> list[StageDef]:
    llm = MistralProvider(api_key=secrets.mistral_api_key, model=secrets.llm_model or "mistral-small-latest")
    voice_cache_path = resolve_voice_cache_path(config.tts.voice, Path(config.tts.voice_cache_dir))
    tts = PocketTTSProvider(voice=config.tts.voice, voice_cache_path=voice_cache_path)
    image_providers = [
        StockPhotoProvider(
            search_clients=[
                PexelsClient(api_key=secrets.pexels_api_key or ""),
                PixabayClient(api_key=secrets.pixabay_api_key or ""),
            ],
            llm=llm,
            aspect_ratio=config.video.aspect_ratio,
            candidates_per_provider=config.image_gen.stock.candidates_per_provider,
        ),
        NanoBananaProvider(api_key=secrets.google_studio_api_key),
        CloudflareSDXLProvider(
            account_id=secrets.cloudflare_account_id or "",
            api_token=secrets.cloudflare_api_token or "",
        ),
        LocalFluxProvider(
            diffusion_model_path=config.image_gen.local_flux.diffusion_model_path,
            vae_path=config.image_gen.local_flux.vae_path,
            clip_l_path=config.image_gen.local_flux.clip_l_path,
            t5xxl_path=config.image_gen.local_flux.t5xxl_path,
            width=config.image_gen.local_flux.width,
            height=config.image_gen.local_flux.height,
            cfg_scale=config.image_gen.local_flux.cfg_scale,
            sample_steps=config.image_gen.local_flux.sample_steps,
        ),
    ]
    music_bed_provider = (
        MusicBedProvider(
            client=FreesoundClient(api_key=secrets.freesound_api_key),
            llm=llm,
            min_duration_sec=config.video.music.min_duration_sec,
        )
        if secrets.freesound_api_key
        else None
    )
    return [
        build_research_stage(user_agent=config.wikipedia.user_agent),
        build_stance_stage(llm),
        build_script_stage(llm),
        build_tts_stage(tts),
        build_image_gen_stage(image_providers, retries=config.image_gen.retries),
        build_section_build_stage(
            aspect_ratio=config.video.aspect_ratio,
            ken_burns=config.video.ken_burns,
            fill_mode=config.video.image_fill_mode,
        ),
        build_final_merge_stage(
            captions=config.video.captions,
            aspect_ratio=config.video.aspect_ratio,
            music_bed_path=config.video.music_bed_path,
            music_bed_provider=music_bed_provider,
            music_mode=config.video.music.mode,
        ),
    ]


def _resolve_projects_root(projects_root: str | None) -> Path:
    if projects_root is not None:
        return Path(projects_root)
    config = load_pipeline_config(Path("config.yaml"))
    return Path(config.paths.projects_root)


@app.command()
def new(
    topic: str,
    slug: str = typer.Option(None, "--slug"),
    projects_root: str = typer.Option(None, "--projects-root"),
) -> None:
    root = _resolve_projects_root(projects_root)
    resolved_slug = slug or slugify(topic)
    paths = ProjectPaths(projects_root=root, slug=resolved_slug)
    paths.ensure_dirs()
    save_state(paths.state_json, ProjectState(topic=topic))
    typer.echo(f"Created project '{resolved_slug}' at {paths.root}")


@app.command()
def status(
    slug: str,
    projects_root: str = typer.Option(None, "--projects-root"),
) -> None:
    root = _resolve_projects_root(projects_root)
    paths = ProjectPaths(projects_root=root, slug=slug)
    if not paths.state_json.exists():
        typer.echo(f"No project found for slug '{slug}'")
        raise typer.Exit(code=1)

    state = load_state(paths.state_json)
    if not state.stages:
        typer.echo("No stages have been run yet.")
        return
    for name, stage in state.stages.items():
        typer.echo(f"{name}: {stage.status.value}")


@app.command()
def run(
    slug: str,
    from_stage: str = typer.Option(None, "--from-stage"),
    to_stage: str = typer.Option(None, "--to-stage"),
    projects_root: str = typer.Option(None, "--projects-root"),
    config_path: str = typer.Option("config.yaml", "--config"),
    env_file: str = typer.Option(".env", "--env-file"),
) -> None:
    root = _resolve_projects_root(projects_root)
    paths = ProjectPaths(projects_root=root, slug=slug)
    if not paths.state_json.exists():
        typer.echo(f"No project found for slug '{slug}'")
        raise typer.Exit(code=1)

    config = load_pipeline_config(Path(config_path))
    secrets = load_secrets(Path(env_file))
    state = load_state(paths.state_json)
    stages = build_default_stages(config, secrets)
    pipeline_runner = Runner(stages)

    try:
        pipeline_runner.execute(paths, state, from_stage=from_stage, to_stage=to_stage)
    except Exception as exc:
        typer.echo(f"Pipeline run failed: {exc}")
        raise typer.Exit(code=1)

    typer.echo(f"Pipeline run complete for '{slug}'.")


@app.command()
def resume(
    slug: str,
    projects_root: str = typer.Option(None, "--projects-root"),
    config_path: str = typer.Option("config.yaml", "--config"),
    env_file: str = typer.Option(".env", "--env-file"),
) -> None:
    run(
        slug,
        from_stage=None,
        to_stage=None,
        projects_root=projects_root,
        config_path=config_path,
        env_file=env_file,
    )


@app.command()
def publish(
    slug: str,
    video_id: str = typer.Option(..., "--video-id"),
    projects_root: str = typer.Option(None, "--projects-root"),
) -> None:
    root = _resolve_projects_root(projects_root)
    paths = ProjectPaths(projects_root=root, slug=slug)
    if not paths.state_json.exists():
        typer.echo(f"No project found for slug '{slug}'")
        raise typer.Exit(code=1)
    if not paths.final_mp4.exists():
        typer.echo(
            f"No final.mp4 found for '{slug}' — run the pipeline through final_merge first"
        )
        raise typer.Exit(code=1)

    paths.video_id_txt.write_text(video_id, encoding="utf-8")
    typer.echo(f"Recorded video_id '{video_id}' for project '{slug}'")


@app.command(name="list")
def list_projects(
    projects_root: str = typer.Option(None, "--projects-root"),
) -> None:
    root = _resolve_projects_root(projects_root)
    if not root.exists():
        typer.echo("No projects yet.")
        return
    slugs = sorted(p.name for p in root.iterdir() if p.is_dir())
    if not slugs:
        typer.echo("No projects yet.")
        return
    for slug in slugs:
        typer.echo(slug)


if __name__ == "__main__":
    app()
