from dataclasses import dataclass
from typing import Protocol


@dataclass
class ImageRequest:
    image_prompt: str
    stock_query: str


class ImageClient(Protocol):
    name: str

    def generate(self, request: ImageRequest) -> bytes: ...
