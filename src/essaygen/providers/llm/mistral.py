from typing import Any

from essaygen.providers.llm.errors import translate_provider_error


class MistralProvider:
    name = "mistral"

    def __init__(self, api_key: str, model: str = "mistral-small-latest", client: Any = None):
        self._api_key = api_key
        self._model = model
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            from mistralai.client import Mistral

            self._client = Mistral(api_key=self._api_key)
        return self._client

    def generate(self, prompt: str) -> str:
        try:
            response = self.client.chat.complete(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise translate_provider_error(exc) from exc
        return response.choices[0].message.content
