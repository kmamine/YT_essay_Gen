import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class StageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    FAILED = "failed"


class StageState(BaseModel):
    status: StageStatus = StageStatus.PENDING
    artifact: str | None = None
    last_error: str | None = None
    units: dict[str, dict[str, Any]] = Field(default_factory=dict)


class ProjectState(BaseModel):
    topic: str | None = None
    stages: dict[str, StageState] = Field(default_factory=dict)

    def _stage(self, name: str) -> StageState:
        return self.stages.setdefault(name, StageState())

    def is_stage_done(self, name: str) -> bool:
        stage = self.stages.get(name)
        return stage is not None and stage.status == StageStatus.DONE

    def mark_stage_in_progress(self, name: str) -> None:
        self._stage(name).status = StageStatus.IN_PROGRESS

    def mark_stage_done(self, name: str, artifact: str | None = None) -> None:
        stage = self._stage(name)
        stage.status = StageStatus.DONE
        stage.artifact = artifact

    def mark_stage_failed(self, name: str, last_error: str) -> None:
        stage = self._stage(name)
        stage.status = StageStatus.FAILED
        stage.last_error = last_error

    def set_unit_status(self, stage_name: str, unit_id: str, **fields: Any) -> None:
        self._stage(stage_name).units[unit_id] = fields

    def get_unit_status(self, stage_name: str, unit_id: str) -> dict[str, Any]:
        stage = self.stages.get(stage_name)
        if stage is None:
            return {}
        return stage.units.get(unit_id, {})


def load_state(path: Path) -> ProjectState:
    if not path.exists():
        return ProjectState()
    return ProjectState.model_validate_json(path.read_text(encoding="utf-8"))


def save_state(path: Path, state: ProjectState) -> None:
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
    os.replace(tmp_path, path)
