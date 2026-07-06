from typing import Any

from essaygen.core.errors import FatalError
from essaygen.providers.image.base import ImageRequest
from essaygen.providers.llm.errors import translate_provider_error


class NanoBananaProvider:
    name = "nano_banana"

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-image", client: Any = None):
        self._api_key = api_key
        self._model = model
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            from google import genai

            self._client = genai.Client(api_key=self._api_key)
        return self._client

    def generate(self, request: ImageRequest) -> bytes:
        try:
            response = self.client.models.generate_content(
                model=self._model, contents=request.image_prompt
            )
        except Exception as exc:
            raise translate_provider_error(exc) from exc

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                return part.inline_data.data

        raise FatalError("Nano Banana response contained no image data")
