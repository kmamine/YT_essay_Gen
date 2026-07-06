import pytest
from pydantic import ValidationError

from essaygen.models.research import Fact, ResearchDoc


def test_fact_requires_id_and_text():
    fact = Fact(id="fact_01", text="Rome was founded in 753 BC.", source_url="https://en.wikipedia.org/wiki/Rome")

    assert fact.id == "fact_01"
    assert fact.text == "Rome was founded in 753 BC."
    assert fact.source_url == "https://en.wikipedia.org/wiki/Rome"


def test_fact_missing_required_field_raises():
    with pytest.raises(ValidationError):
        Fact(id="fact_01")


def test_research_doc_round_trips_through_json():
    doc = ResearchDoc(
        topic="Rome",
        facts=[
            Fact(id="fact_01", text="Rome was founded in 753 BC.", source_url="https://en.wikipedia.org/wiki/Rome"),
            Fact(id="fact_02", text="Rome became a republic in 509 BC.", source_url="https://en.wikipedia.org/wiki/Rome"),
        ],
    )

    restored = ResearchDoc.model_validate_json(doc.model_dump_json())

    assert restored == doc
    assert len(restored.facts) == 2
