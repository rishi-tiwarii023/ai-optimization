from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from src.contracts.config import AgentSpec, ModelSpec, ProviderConfig, TaskSpec
from src.contracts.scoring import ScoreResult


class TrialRequest(BaseModel):
    """One unit of work from Task × Agent × Model × Attempt expansion."""

    trial_id: str
    experiment_id: str
    task: TaskSpec
    agent: AgentSpec
    model: ModelSpec
    attempt: int = Field(ge=1)
    provider: ProviderConfig

    @property
    def experiment_name(self) -> str:
        return self.experiment_id


class ResourceUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    latency_seconds: float | None = None


class TrajectoryEvent(BaseModel):
    kind: Literal["message", "tool_call", "command", "file_change"]
    payload: dict[str, Any] = Field(default_factory=dict)


class TrialResult(BaseModel):
    """Agent execution output. Scoring and persistence happen elsewhere."""

    status: Literal["success", "error", "timeout"]
    patch: str | None = None
    trajectory: list[TrajectoryEvent] = Field(default_factory=list)
    execution_logs: str = ""
    resource_usage: ResourceUsage | None = None
    error_details: str | None = None


class FinalTrialResult(BaseModel):
    """One completed trial: agent execution plus deterministic score."""

    trial_id: str
    experiment_id: str
    task_id: str
    model_id: str
    attempt: int = Field(ge=1)
    execution: TrialResult
    score: ScoreResult
