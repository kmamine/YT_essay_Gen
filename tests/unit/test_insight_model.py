import pytest
from pydantic import ValidationError

from essaygen.models.insight import CommentInsights, Insight, Metrics


def make_insight(**overrides):
    defaults = dict(
        video_id="abc123",
        topic="Fall of Rome",
        thesis="Rome's fall was self-inflicted.",
        thesis_style="contrarian",
        metrics=Metrics(
            views=1000,
            avg_view_duration_sec=180.5,
            retention_curve=[1.0, 0.8, 0.5],
            ctr=0.06,
            likes=50,
            comment_count=12,
        ),
        comment_insights=CommentInsights(
            sentiment_summary="Mostly positive, some pushback on framing.",
            recurring_themes=["praise for pacing"],
            notable_pushback=["disputes causal claim"],
            follow_up_requests=["cover Byzantine continuation"],
        ),
        takeaways=["Lead with the contrarian hook earlier next time."],
    )
    defaults.update(overrides)
    return Insight(**defaults)


def test_insight_holds_metrics_and_comment_insights():
    insight = make_insight()

    assert insight.video_id == "abc123"
    assert insight.thesis_style == "contrarian"
    assert insight.metrics.views == 1000
    assert insight.comment_insights.recurring_themes == ["praise for pacing"]


def test_insight_missing_takeaways_raises():
    with pytest.raises(ValidationError):
        Insight(
            video_id="abc123",
            topic="Fall of Rome",
            thesis="thesis",
            metrics=Metrics(
                views=1000,
                avg_view_duration_sec=180.5,
                retention_curve=[],
                ctr=0.06,
                likes=50,
                comment_count=12,
            ),
            comment_insights=CommentInsights(
                sentiment_summary="ok",
                recurring_themes=[],
                notable_pushback=[],
                follow_up_requests=[],
            ),
        )


def test_insight_round_trips_through_json():
    insight = make_insight()

    restored = Insight.model_validate_json(insight.model_dump_json())

    assert restored == insight
