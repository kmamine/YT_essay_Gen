from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext, StageDef
from essaygen.models.research import ResearchDoc
from essaygen.models.script import Script
from essaygen.models.stance import Stance
from essaygen.providers.llm.base import LLMProvider
from essaygen.providers.llm.parsing import extract_json_object

_SCRIPT_SHAPE_EXAMPLE = (
    '{"title": "...", "thesis": "...", '
    '"youtube_metadata": {"title": "...", "description": "...", "tags": ["..."]}, '
    '"sections": [{"id": "sec_01", "title": "...", "subsections": '
    '[{"id": "sec_01_sub_01", "narration": "...", "claim": "...", "evidence": "...", '
    '"evidence_ref": "fact_01", "image_prompt": "...", "stock_query": "..."}]}]}'
)


def build_script_prompt(research: ResearchDoc, stance: Stance) -> str:
    facts_block = "\n".join(f"- ({fact.id}) {fact.text}" for fact in research.facts)
    return (
        f"Topic: {research.topic}\n"
        f"Thesis: {stance.thesis}\n"
        f"Angle: {stance.angle}\n\n"
        "Available facts (reference by id in evidence_ref):\n"
        f"{facts_block}\n\n"
        "Write a full opinionated video essay script arguing the thesis directly: no "
        "hedging, direct judgments, rhetorical framing. Facts must stay accurate; "
        "interpretation should be opinionated. Structure the script into sections and "
        "subsections. Each subsection's evidence_ref MUST reference one of the fact ids above.\n\n"
        "Each subsection also needs two distinct image-related fields: image_prompt "
        "(descriptive, artistic phrasing for an AI image generator, e.g. 'a crumbling "
        "Roman senate building, dramatic lighting') and stock_query (a short, literal "
        "keyword phrase for searching real stock photo libraries, e.g. 'roman senate "
        "ruins ancient' — no mood/style language, just concrete searchable nouns).\n\n"
        "Respond ONLY with JSON matching this exact shape:\n"
        f"{_SCRIPT_SHAPE_EXAMPLE}"
    )


def parse_script_response(raw: str) -> Script:
    return Script.model_validate(extract_json_object(raw))


def build_script_stage(llm: LLMProvider) -> StageDef:
    def run(ctx: RunContext) -> None:
        if not ctx.paths.research_json.exists():
            raise FatalError("Cannot run script stage: research.json missing")
        if not ctx.paths.stance_json.exists():
            raise FatalError("Cannot run script stage: stance.json missing")

        research = ResearchDoc.model_validate_json(
            ctx.paths.research_json.read_text(encoding="utf-8")
        )
        stance = Stance.model_validate_json(ctx.paths.stance_json.read_text(encoding="utf-8"))
        prompt = build_script_prompt(research, stance)
        raw = llm.generate(prompt)
        script = parse_script_response(raw)
        ctx.paths.script_json.write_text(script.model_dump_json(indent=2), encoding="utf-8")

    def artifact_path(paths: ProjectPaths):
        return paths.script_json

    return StageDef(name="script", run=run, artifact_path=artifact_path)
