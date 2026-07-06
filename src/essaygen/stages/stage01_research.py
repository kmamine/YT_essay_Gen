from typing import Callable

from essaygen.core.errors import FatalError
from essaygen.core.project import ProjectPaths
from essaygen.core.runner import RunContext, StageDef
from essaygen.models.research import ResearchDoc
from essaygen.providers.wikipedia.client import extract_facts, fetch_article_extract

FetchFn = Callable[..., tuple[str, str]]


def build_research_stage(user_agent: str, fetch: FetchFn = fetch_article_extract) -> StageDef:
    def run(ctx: RunContext) -> None:
        topic = ctx.state.topic
        if not topic:
            raise FatalError("Cannot run research stage: project has no topic set")

        text, source_url = fetch(topic, user_agent=user_agent)
        facts = extract_facts(text, source_url)
        doc = ResearchDoc(topic=topic, facts=facts)
        ctx.paths.research_json.write_text(doc.model_dump_json(indent=2), encoding="utf-8")

    def artifact_path(paths: ProjectPaths):
        return paths.research_json

    return StageDef(name="research", run=run, artifact_path=artifact_path)
