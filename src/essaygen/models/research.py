from pydantic import BaseModel


class Fact(BaseModel):
    id: str
    text: str
    source_url: str


class ResearchDoc(BaseModel):
    topic: str
    facts: list[Fact]
