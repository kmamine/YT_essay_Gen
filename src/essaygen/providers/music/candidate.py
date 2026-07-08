from dataclasses import dataclass


@dataclass
class MusicCandidate:
    id: str
    description: str
    preview_url: str
    duration_sec: float
