from dataclasses import dataclass


@dataclass
class StockCandidate:
    id: str
    description: str
    image_url: str
