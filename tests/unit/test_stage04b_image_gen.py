import json

import pytest

from essaygen.core.errors import FatalError, QuotaExhaustedError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext
from essaygen.core.state import ProjectState, load_state
from essaygen.models.script import Script, Section, Subsection, YoutubeMetadata
from essaygen.stages.stage04b_image_gen import build_image_gen_stage


@pytest.fixture
def paths(tmp_path):
    p = ProjectPaths(projects_root=tmp_path, slug="rome")
    p.ensure_dirs()
    return p


@pytest.fixture
def script():
    return Script(
        title="t",
        thesis="t",
        youtube_metadata=YoutubeMetadata(title="t", description="d", tags=["t"]),
        sections=[
            Section(
                id="sec_01",
                title="Section One",
                subsections=[
                    Subsection(
                        id="sec_01_sub_01",
                        narration="n1",
                        claim="c1",
                        evidence="e1",
                        evidence_ref="fact_01",
                        image_prompt="a crumbling senate building",
                        stock_query="roman senate ruins",
                    ),
                    Subsection(
                        id="sec_01_sub_02",
                        narration="n2",
                        claim="c2",
                        evidence="e2",
                        evidence_ref="fact_02",
                        image_prompt="a roman legion marching",
                        stock_query="roman legion",
                    ),
                ],
            )
        ],
    )


class FakeImageProvider:
    def __init__(self, name, side_effect=None):
        self.name = name
        self.side_effect = side_effect or (lambda request: f"bytes-for-{request.image_prompt}".encode())
        self.calls = []

    def generate(self, request):
        self.calls.append(request)
        result = self.side_effect(request)
        if isinstance(result, Exception):
            raise result
        return result


def test_image_gen_stage_generates_image_and_meta_for_each_subsection(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    provider = FakeImageProvider("nano_banana")
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_image_gen_stage([provider])

    stage.run(ctx)

    image_path = paths.images_dir / "sec_01_sub_01.png"
    meta_path = paths.images_dir / "sec_01_sub_01.meta.json"
    assert image_path.read_bytes() == b"bytes-for-a crumbling senate building"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["tier"] == "nano_banana"
    assert state.get_unit_status("subsections", "sec_01_sub_01")["image"] == "done"
    assert state.get_unit_status("subsections", "sec_01_sub_01")["image_tier"] == "nano_banana"


def test_image_gen_stage_passes_both_image_prompt_and_stock_query(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    provider = FakeImageProvider("nano_banana")
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_image_gen_stage([provider])

    stage.run(ctx)

    first_request = provider.calls[0]
    assert first_request.image_prompt == "a crumbling senate building"
    assert first_request.stock_query == "roman senate ruins"


def test_image_gen_stage_skips_already_completed_units(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    provider = FakeImageProvider("nano_banana")
    state = ProjectState(topic="Fall of Rome")
    state.set_unit_status("subsections", "sec_01_sub_01", image="done", image_tier="nano_banana")
    ctx = RunContext(paths=paths, state=state)
    stage = build_image_gen_stage([provider])

    stage.run(ctx)

    assert [r.image_prompt for r in provider.calls] == ["a roman legion marching"]


def test_image_gen_stage_falls_back_to_second_tier_on_quota_exhausted(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    failing = FakeImageProvider("nano_banana", side_effect=lambda r: QuotaExhaustedError("quota"))
    fallback = FakeImageProvider("cloudflare_sdxl")
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_image_gen_stage([failing, fallback])

    stage.run(ctx)

    assert state.get_unit_status("subsections", "sec_01_sub_01")["image_tier"] == "cloudflare_sdxl"


def test_image_gen_stage_raises_fatal_error_when_script_missing(paths):
    stage = build_image_gen_stage([FakeImageProvider("nano_banana")])
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)

    with pytest.raises(FatalError):
        stage.run(ctx)


def test_image_gen_stage_persists_progress_after_each_subsection(paths, script):
    paths.script_json.write_text(script.model_dump_json(), encoding="utf-8")
    provider = FakeImageProvider("nano_banana")
    state = ProjectState(topic="Fall of Rome")
    ctx = RunContext(paths=paths, state=state)
    stage = build_image_gen_stage([provider])

    stage.run(ctx)

    restored = load_state(paths.state_json)
    assert restored.get_unit_status("subsections", "sec_01_sub_02")["image"] == "done"


def test_image_gen_stage_has_expected_name():
    stage = build_image_gen_stage([FakeImageProvider("nano_banana")])

    assert stage.name == "image_gen"
