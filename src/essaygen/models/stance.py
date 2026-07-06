from pydantic import BaseModel


class Stance(BaseModel):
    thesis: str
    angle: str
