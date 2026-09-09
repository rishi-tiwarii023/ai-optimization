from __future__ import annotations

from pydantic import BaseModel, Field

from src.contracts.config import AgentSpec, ModelSpec, ProviderConfig, TaskSpec


class TrialRequest(BaseModel):
    """One unit of work from Task × Agent × Model × Attempt expansion."""

    trial_id: str
    experiment_name: str
    task: TaskSpec
    agent: AgentSpec
    model: ModelSpec
    attempt: int = Field(ge=1)
    provider: ProviderConfig
