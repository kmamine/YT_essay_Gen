from io import BytesIO
from typing import Any

from essaygen.core.errors import FatalError
from essaygen.providers.image.base import ImageRequest


class LocalFluxProvider:
    name = "local_flux"

    def __init__(
        self,
        diffusion_model_path: str | None = None,
        vae_path: str | None = None,
        clip_l_path: str | None = None,
        t5xxl_path: str | None = None,
        width: int = 512,
        height: int = 512,
        cfg_scale: float = 1.0,
        sample_steps: int = 4,
        client: Any = None,
    ):
        self._diffusion_model_path = diffusion_model_path
        self._vae_path = vae_path
        self._clip_l_path = clip_l_path
        self._t5xxl_path = t5xxl_path
        self._width = width
        self._height = height
        self._cfg_scale = cfg_scale
        self._sample_steps = sample_steps
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            if not self._diffusion_model_path or not self._vae_path:
                raise FatalError(
                    "local_flux is not configured: set image_gen.local_flux.diffusion_model_path "
                    "and vae_path in config.yaml (download FLUX.2-klein-4B-GGUF weights + VAE "
                    "first). The exact companion text-encoder files FLUX.2 needs (vs. FLUX.1's "
                    "CLIP+T5 pair) are unconfirmed as of writing — verify against "
                    "stable-diffusion.cpp's FLUX.2 documentation before relying on this tier."
                )
            from stable_diffusion_cpp import StableDiffusion

            kwargs = {
                "diffusion_model_path": self._diffusion_model_path,
                "vae_path": self._vae_path,
            }
            if self._clip_l_path:
                kwargs["clip_l_path"] = self._clip_l_path
            if self._t5xxl_path:
                kwargs["t5xxl_path"] = self._t5xxl_path
            self._client = StableDiffusion(**kwargs)
        return self._client

    def generate(self, request: ImageRequest) -> bytes:
        images = self.client.generate_image(
            prompt=request.image_prompt,
            width=self._width,
            height=self._height,
            cfg_scale=self._cfg_scale,
            sample_steps=self._sample_steps,
        )
        buffer = BytesIO()
        images[0].save(buffer, format="PNG")
        return buffer.getvalue()
