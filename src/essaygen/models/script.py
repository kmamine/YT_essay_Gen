from pydantic import BaseModel


class Subsection(BaseModel):
    id: str
    narration: str
    claim: str
    evidence: str
    evidence_ref: str
    image_prompt: str
    stock_query: str


class Section(BaseModel):
    id: str
    title: str
    subsections: list[Subsection]


class YoutubeMetadata(BaseModel):
    title: str
    description: str
    tags: list[str]


class Script(BaseModel):
    title: str
    thesis: str
    youtube_metadata: YoutubeMetadata
    sections: list[Section]
