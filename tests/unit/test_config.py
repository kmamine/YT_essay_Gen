import pytest
from pydantic import ValidationError

from essaygen.config import Secrets, load_pipeline_config, load_secrets


def test_load_pipeline_config_returns_defaults_when_file_missing(tmp_path):
    config = load_pipeline_config(tmp_path / "does-not-exist.yaml")

    assert config.video.aspect_ratio == "16:9"
    assert config.video.captions is True
    assert config.video.ken_burns is True
    assert config.image_gen.tiers == ["stock_photo", "nano_banana", "cloudflare_sdxl", "local_flux"]
    assert config.image_gen.stock.candidates_per_provider == 5
    assert config.paths.projects_root == "./projects"
    assert "@" in config.wikipedia.user_agent
    assert config.llm.primary == "mistral"
    assert config.tts.voice == "alba"
    assert config.tts.voice_cache_dir == "./data/voice_cache"
    assert config.image_gen.local_flux.diffusion_model_path is None
    assert config.image_gen.local_flux.vae_path is None
    assert config.image_gen.local_flux.sample_steps == 4


def test_load_pipeline_config_parses_local_flux_paths(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "image_gen:\n"
        "  local_flux:\n"
        "    diffusion_model_path: models/flux2-klein.gguf\n"
        "    vae_path: models/ae.safetensors\n"
        "    sample_steps: 8\n"
    )

    config = load_pipeline_config(config_path)

    assert config.image_gen.local_flux.diffusion_model_path == "models/flux2-klein.gguf"
    assert config.image_gen.local_flux.vae_path == "models/ae.safetensors"
    assert config.image_gen.local_flux.sample_steps == 8


def test_load_pipeline_config_parses_tts_voice_override(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text('tts:\n  voice: "./voices/my_reference.wav"\n  voice_cache_dir: "./cache"\n')

    config = load_pipeline_config(config_path)

    assert config.tts.voice == "./voices/my_reference.wav"
    assert config.tts.voice_cache_dir == "./cache"


def test_load_pipeline_config_parses_wikipedia_user_agent_override(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text('wikipedia:\n  user_agent: "CustomBot/1.0 (me@example.com)"\n')

    config = load_pipeline_config(config_path)

    assert config.wikipedia.user_agent == "CustomBot/1.0 (me@example.com)"


def test_load_pipeline_config_parses_yaml_file(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
llm:
  primary: mistral
  fallback: [groq, cerebras]
  rate_limits:
    mistral: {rpm: 12, rpd: 1400}
image_gen:
  tiers: [nano_banana, cloudflare_sdxl, local_flux]
  retries: {nano_banana: 2, cloudflare_sdxl: 2, local_flux: 1}
video:
  aspect_ratio: "9:16"
  captions: false
  ken_burns: true
paths:
  projects_root: "./projects"
  insight_db: "./data/insights.db"
"""
    )

    config = load_pipeline_config(config_path)

    assert config.llm.primary == "mistral"
    assert config.llm.fallback == ["groq", "cerebras"]
    assert config.llm.rate_limits["mistral"].rpm == 12
    assert config.image_gen.retries["nano_banana"] == 2
    assert config.video.aspect_ratio == "9:16"
    assert config.video.captions is False


def test_load_secrets_reads_from_env_file(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("GOOGLE_STUDIO_API_KEY=test-key-123\n")

    secrets = load_secrets(env_path)

    assert secrets.google_studio_api_key == "test-key-123"
    assert secrets.groq_api_key is None
    assert secrets.mistral_api_key is None
    assert secrets.pexels_api_key is None
    assert secrets.pixabay_api_key is None


def test_load_secrets_reads_stock_photo_keys_when_present(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text(
        "GOOGLE_STUDIO_API_KEY=test-key-123\n"
        "PEXELS_API_KEY=pexels-key-456\n"
        "PIXABAY_API_KEY=pixabay-key-789\n"
    )

    secrets = load_secrets(env_path)

    assert secrets.pexels_api_key == "pexels-key-456"
    assert secrets.pixabay_api_key == "pixabay-key-789"


def test_load_secrets_reads_mistral_api_key_when_present(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("GOOGLE_STUDIO_API_KEY=test-key-123\nMISTRAL_API_KEY=mistral-key-456\n")

    secrets = load_secrets(env_path)

    assert secrets.mistral_api_key == "mistral-key-456"


def test_load_secrets_reads_llm_model_override_when_present(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("GOOGLE_STUDIO_API_KEY=test-key-123\nLLM_MODEL=mistral-large-latest\n")

    secrets = load_secrets(env_path)

    assert secrets.llm_model == "mistral-large-latest"


def test_load_secrets_llm_model_defaults_to_none(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("GOOGLE_STUDIO_API_KEY=test-key-123\n")

    secrets = load_secrets(env_path)

    assert secrets.llm_model is None


def test_secrets_missing_required_key_raises(tmp_path):
    env_path = tmp_path / ".env"
    env_path.write_text("GROQ_API_KEY=only-groq\n")

    with pytest.raises(ValidationError):
        load_secrets(env_path)
