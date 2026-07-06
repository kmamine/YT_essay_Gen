from io import BytesIO

import pytest

from essaygen.core.errors import FatalError
from essaygen.providers.image.base import ImageRequest
from essaygen.providers.image.local_flux import LocalFluxProvider


class FakePILImage:
    def __init__(self, payload: bytes):
        self._payload = payload

    def save(self, buffer, format):
        buffer.write(self._payload)


class FakeStableDiffusionClient:
    def __init__(self, images):
        self.images = images
        self.calls = []

    def generate_image(self, prompt, width, height, cfg_scale, sample_steps):
        self.calls.append((prompt, width, height, cfg_scale, sample_steps))
        return self.images


def test_generate_returns_png_bytes_from_first_generated_image():
    client = FakeStableDiffusionClient([FakePILImage(b"png-bytes")])
    provider = LocalFluxProvider(
        diffusion_model_path="models/flux2-klein.gguf",
        vae_path="models/ae.safetensors",
        client=client,
    )

    result = provider.generate(
        ImageRequest(image_prompt="a crumbling roman senate", stock_query="roman senate ruins")
    )

    assert result == b"png-bytes"
    assert client.calls[0][0] == "a crumbling roman senate"


def test_generate_raises_fatal_error_when_not_configured():
    provider = LocalFluxProvider()

    with pytest.raises(FatalError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))


def test_generate_raises_fatal_error_when_vae_path_missing():
    provider = LocalFluxProvider(diffusion_model_path="models/flux2-klein.gguf")

    with pytest.raises(FatalError):
        provider.generate(ImageRequest(image_prompt="prompt", stock_query="query"))


def test_provider_has_expected_name():
    assert LocalFluxProvider().name == "local_flux"
