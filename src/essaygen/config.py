from pathlib import Path

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RateLimitConfig(BaseModel):
    rpm: int
    rpd: int


class LLMConfig(BaseModel):
    primary: str = "mistral"
    fallback: list[str] = Field(default_factory=lambda: ["groq", "cerebras"])
    rate_limits: dict[str, RateLimitConfig] = Field(default_factory=dict)


class LocalFluxConfig(BaseModel):
    diffusion_model_path: str | None = None
    vae_path: str | None = None
    clip_l_path: str | None = None
    t5xxl_path: str | None = None
    width: int = 512
    height: int = 512
    cfg_scale: float = 1.0
    sample_steps: int = 4


class StockConfig(BaseModel):
    candidates_per_provider: int = 5


class MusicConfig(BaseModel):
    # "constant": one fixed, quiet volume for the whole runtime (default --
    # duck mode's sidechain behavior was live-reported as inconsistent,
    # either inaudible or overpowering depending on the track). "duck":
    # sidechain-compress the music under narration and recover it in gaps.
    mode: str = "constant"
    min_duration_sec: int = 60


class ImageGenConfig(BaseModel):
    tiers: list[str] = Field(
        default_factory=lambda: ["stock_photo", "nano_banana", "cloudflare_sdxl", "local_flux"]
    )
    retries: dict[str, int] = Field(default_factory=dict)
    local_flux: LocalFluxConfig = Field(default_factory=LocalFluxConfig)
    stock: StockConfig = Field(default_factory=StockConfig)


class VideoConfig(BaseModel):
    aspect_ratio: str = "16:9"
    captions: bool = True
    ken_burns: bool = True
    intro_path: str | None = None
    outro_path: str | None = None
    # "blur": leftover space around a non-matching-aspect-ratio image is
    # filled with a blurred, zoomed copy of the same image (no crop/
    # stretch of the actual photo). "black": solid letterbox/pillarbox
    # bars instead.
    image_fill_mode: str = "blur"
    music_bed_path: str | None = None
    music: MusicConfig = Field(default_factory=MusicConfig)


class PathsConfig(BaseModel):
    projects_root: str = "./projects"
    insight_db: str = "./data/insights.db"


class WikipediaConfig(BaseModel):
    user_agent: str = "EssayGen/0.1 (contact: mohamed.a.kerkouri@gmail.com)"


class TTSConfig(BaseModel):
    voice: str = "alba"
    voice_cache_dir: str = "./data/voice_cache"


class PipelineConfig(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    image_gen: ImageGenConfig = Field(default_factory=ImageGenConfig)
    video: VideoConfig = Field(default_factory=VideoConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    wikipedia: WikipediaConfig = Field(default_factory=WikipediaConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)


def load_pipeline_config(path: Path) -> PipelineConfig:
    if not path.exists():
        return PipelineConfig()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return PipelineConfig.model_validate(raw)


class Secrets(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    google_studio_api_key: str
    mistral_api_key: str | None = None
    llm_model: str | None = None
    groq_api_key: str | None = None
    cerebras_api_key: str | None = None
    cloudflare_account_id: str | None = None
    cloudflare_api_token: str | None = None
    pexels_api_key: str | None = None
    pixabay_api_key: str | None = None
    freesound_api_key: str | None = None


def load_secrets(env_file: Path) -> Secrets:
    return Secrets(_env_file=str(env_file))
