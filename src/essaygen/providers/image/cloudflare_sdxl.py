import base64
from typing import Any

import httpx

from essaygen.core.errors import FatalError, QuotaExhaustedError, RateLimitError, TransientError
from essaygen.providers.image.base import ImageRequest

CLOUDFLARE_API_BASE = "https://api.cloudflare.com/client/v4/accounts"


class CloudflareSDXLProvider:
    name = "cloudflare_sdxl"

    def __init__(self, account_id: str, api_token: str, client: Any = None):
        self._account_id = account_id
        self._api_token = api_token
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = httpx.Client(timeout=60.0)
        return self._client

    def generate(self, request: ImageRequest) -> bytes:
        if not self._account_id or not self._api_token:
            raise FatalError(
                "cloudflare_sdxl is not configured: set CLOUDFLARE_ACCOUNT_ID and "
                "CLOUDFLARE_API_TOKEN in .env"
            )

        url = f"{CLOUDFLARE_API_BASE}/{self._account_id}/ai/run/@cf/stabilityai/stable-diffusion-xl-base-1.0"
        try:
            response = self.client.post(
                url,
                headers={"Authorization": f"Bearer {self._api_token}"},
                json={"prompt": request.image_prompt},
            )
        except (RateLimitError, QuotaExhaustedError, TransientError, FatalError):
            raise
        except Exception as exc:
            raise TransientError(f"Cloudflare request could not be sent: {exc}") from exc

        if response.status_code == 429:
            raise RateLimitError(f"Cloudflare rate limited: {response.text}")
        if response.status_code == 403:
            raise QuotaExhaustedError(f"Cloudflare quota/auth error: {response.text}")
        if response.status_code >= 500:
            raise TransientError(f"Cloudflare server error {response.status_code}: {response.text}")
        if response.status_code >= 400:
            raise FatalError(f"Cloudflare request failed {response.status_code}: {response.text}")

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            payload = response.json()
            return base64.b64decode(payload["result"]["image"])
        return response.content
