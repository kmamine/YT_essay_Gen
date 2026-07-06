from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext, StageDef
from essaygen.models.research import ResearchDoc
from essaygen.models.stance import Stance
from essaygen.providers.llm.base import LLMProvider
from essaygen.providers.llm.parsing import extract_json_object


def build_stance_prompt(research: ResearchDoc) -> str:
    facts_block = "\n".join(f"- {fact.text}" for fact in research.facts)
    return (
        f"You are writing an opinionated video essay about: {research.topic}\n\n"
        "Facts:\n"
        f"{facts_block}\n\n"
        "Commit to a single thesis: a contrarian or surprising argument the viewer "
        "should walk away believing. Respond ONLY with JSON matching this shape:\n"
        '{"thesis": "...", "angle": "..."}'
    )


def parse_stance_response(raw: str) -> Stance:
    return Stance.model_validate(extract_json_object(raw))


def build_stance_stage(llm: LLMProvider) -> StageDef:
    def run(ctx: RunContext) -> None:
        if not ctx.paths.research_json.exists():
            raise FatalError("Cannot run stance stage: research.json missing")

        research = ResearchDoc.model_validate_json(
            ctx.paths.research_json.read_text(encoding="utf-8")
        )
        prompt = build_stance_prompt(research)
        raw = llm.generate(prompt)
        stance = parse_stance_response(raw)
        ctx.paths.stance_json.write_text(stance.model_dump_json(indent=2), encoding="utf-8")

    def artifact_path(paths: ProjectPaths):
        return paths.stance_json

    return StageDef(name="stance", run=run, artifact_path=artifact_path)
