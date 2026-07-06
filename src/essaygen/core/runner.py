from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from essaygen.core.project import ProjectPaths
from essaygen.core.state import ProjectState, save_state


@dataclass
class RunContext:
    paths: ProjectPaths
    state: ProjectState


@dataclass
class StageDef:
    name: str
    run: Callable[[RunContext], None]
    artifact_path: Callable[[ProjectPaths], Path] | None = None


class Runner:
    def __init__(self, stages: list[StageDef]):
        self.stages = stages
        self._by_name = {s.name: s for s in stages}

    def _select(self, from_stage: str | None, to_stage: str | None) -> list[StageDef]:
        names = [s.name for s in self.stages]
        start = names.index(from_stage) if from_stage else 0
        end = names.index(to_stage) + 1 if to_stage else len(names)
        return self.stages[start:end]

    def _artifact_ok(self, stage: StageDef, paths: ProjectPaths) -> bool:
        if stage.artifact_path is None:
            return True
        path = stage.artifact_path(paths)
        if path is None:
            return True
        return path.exists() and path.stat().st_size > 0

    def execute(
        self,
        paths: ProjectPaths,
        state: ProjectState,
        from_stage: str | None = None,
        to_stage: str | None = None,
    ) -> None:
        for stage in self._select(from_stage, to_stage):
            if state.is_stage_done(stage.name) and self._artifact_ok(stage, paths):
                continue

            state.mark_stage_in_progress(stage.name)
            save_state(paths.state_json, state)

            ctx = RunContext(paths=paths, state=state)
            try:
                stage.run(ctx)
            except Exception as exc:
                state.mark_stage_failed(stage.name, str(exc))
                save_state(paths.state_json, state)
                raise

            state.mark_stage_done(stage.name, artifact=stage.name)
            save_state(paths.state_json, state)
