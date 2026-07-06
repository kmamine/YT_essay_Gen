from pydantic import BaseModel


class Metrics(BaseModel):
    views: int
    avg_view_duration_sec: float
    retention_curve: list[float]
    ctr: float
    likes: int
    comment_count: int


class CommentInsights(BaseModel):
    sentiment_summary: str
    recurring_themes: list[str]
    notable_pushback: list[str]
    follow_up_requests: list[str]


class Insight(BaseModel):
    video_id: str
    topic: str
    thesis: str
    thesis_style: str | None = None
    metrics: Metrics
    comment_insights: CommentInsights
    takeaways: list[str]
