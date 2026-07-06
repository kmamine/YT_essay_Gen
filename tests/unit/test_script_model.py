import pytest
from pydantic import ValidationError

from essaygen.models.script import Script, Section, Subsection, YoutubeMetadata


def make_subsection(**overrides):
    defaults = dict(
        id="sec_01_sub_01",
        narration="Rome did not fall to barbarians. It rotted from within.",
        claim="Institutional decay, not invasion, caused Rome's collapse.",
        evidence="Administrative corruption is documented across multiple 4th-century sources.",
        evidence_ref="fact_03",
        image_prompt="Crumbling Roman senate building, dramatic lighting",
        stock_query="roman senate ruins ancient",
    )
    defaults.update(overrides)
    return Subsection(**defaults)


def test_subsection_requires_all_spec_fields():
    sub = make_subsection()

    assert sub.id == "sec_01_sub_01"
    assert sub.evidence_ref == "fact_03"
    assert sub.stock_query == "roman senate ruins ancient"


def test_subsection_missing_claim_raises():
    with pytest.raises(ValidationError):
        Subsection(
            id="sec_01_sub_01",
            narration="text",
            evidence="text",
            evidence_ref="fact_01",
            image_prompt="prompt",
            stock_query="query",
        )


def test_subsection_missing_stock_query_raises():
    with pytest.raises(ValidationError):
        Subsection(
            id="sec_01_sub_01",
            narration="text",
            claim="claim",
            evidence="text",
            evidence_ref="fact_01",
            image_prompt="prompt",
        )


def test_script_round_trips_matching_spec_shape():
    script = Script(
        title="Rome Didn't Fall. It Quit.",
        thesis="Rome's fall was self-inflicted.",
        youtube_metadata=YoutubeMetadata(
            title="Why Rome ACTUALLY Fell (Not What You Think)",
            description="A video essay arguing institutional collapse over conquest.",
            tags=["rome", "history", "video essay"],
        ),
        sections=[
            Section(
                id="sec_01",
                title="The Myth of Barbarian Conquest",
                subsections=[make_subsection()],
            )
        ],
    )

    restored = Script.model_validate_json(script.model_dump_json())

    assert restored == script
    assert restored.sections[0].subsections[0].evidence_ref == "fact_03"
    assert restored.youtube_metadata.tags == ["rome", "history", "video essay"]
