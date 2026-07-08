import re
from dataclasses import dataclass
from pathlib import Path


def slugify(topic: str) -> str:
    lowered = topic.lower()
    no_punctuation = re.sub(r"[^a-z0-9\s-]", "", lowered)
    return re.sub(r"[\s-]+", "-", no_punctuation).strip("-")


@dataclass
class ProjectPaths:
    projects_root: Path
    slug: str

    @property
    def root(self) -> Path:
        return self.projects_root / self.slug

    @property
    def state_json(self) -> Path:
        return self.root / "state.json"

    @property
    def research_json(self) -> Path:
        return self.root / "research.json"

    @property
    def stance_json(self) -> Path:
        return self.root / "stance.json"

    @property
    def script_json(self) -> Path:
        return self.root / "script.json"

    @property
    def audio_dir(self) -> Path:
        return self.root / "audio"

    @property
    def images_dir(self) -> Path:
        return self.root / "images"

    @property
    def captions_srt(self) -> Path:
        return self.root / "captions.srt"

    @property
    def sections_dir(self) -> Path:
        return self.root / "sections"

    @property
    def final_mp4(self) -> Path:
        return self.root / "final.mp4"

    @property
    def metadata_json(self) -> Path:
        return self.root / "metadata.json"

    @property
    def thumbnail_jpg(self) -> Path:
        return self.root / "thumbnail.jpg"

    @property
    def video_id_txt(self) -> Path:
        return self.root / "video_id.txt"

    @property
    def tracking_dir(self) -> Path:
        return self.root / "tracking"

    @property
    def insight_json(self) -> Path:
        return self.root / "insight.json"

    def ensure_dirs(self) -> None:
        for directory in (
            self.root,
            self.audio_dir,
            self.images_dir,
            self.sections_dir,
            self.tracking_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)
