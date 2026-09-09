from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TaskSpec(BaseModel):
    id: str
    name: str | None = None
    path: str | None = None
    enabled: bool = True

    @model_validator(mode="before")
    @classmethod
    def coerce_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {
                "id": value,
                "path": f"datasets/internal-core/{value}",
            }
        return value


class AgentSpec(BaseModel):
    id: str
    name: str | None = None
    enabled: bool = True

    @model_validator(mode="before")
    @classmethod
    def coerce_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"id": value}
        return value


class ModelSpec(BaseModel):
    """A model that can be enabled or tuned without code changes."""

    id: str
    hf_id: str | None = None
    enabled: bool = True
    max_new_tokens: int = Field(default=512, ge=1)
    temperature: float = Field(default=0.2, ge=0.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)

    @property
    def inference_id(self) -> str:
        return self.hf_id or self.id

    @model_validator(mode="before")
    @classmethod
    def coerce_id(cls, value: Any) -> Any:
        if isinstance(value, str):
            return {"id": value}
        return value


class ProviderConfig(BaseModel):
    type: Literal["huggingface"] = "huggingface"
    timeout_seconds: float = Field(default=120.0, gt=0)


class ExperimentConfig(BaseModel):
    experiment_id: str
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    tasks: list[TaskSpec] = Field(default_factory=list)
    agents: list[AgentSpec] = Field(default_factory=list)
    models: list[ModelSpec] = Field(default_factory=list)
    attempts: int = Field(default=1, ge=1)

    @model_validator(mode="before")
    @classmethod
    def normalize(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        if "experiment_id" not in data and "name" in data:
            data["experiment_id"] = data["name"]
        if "tasks" not in data and "task" in data:
            task = data["task"]
            data["tasks"] = task if isinstance(task, list) else [task]
        if "agents" not in data and "agent" in data:
            agent = data["agent"]
            data["agents"] = agent if isinstance(agent, list) else [agent]
        return data

    @property
    def name(self) -> str:
        return self.experiment_id

    def enabled_tasks(self) -> list[TaskSpec]:
        return [task for task in self.tasks if task.enabled]

    def enabled_agents(self) -> list[AgentSpec]:
        return [agent for agent in self.agents if agent.enabled]

    def enabled_models(self) -> list[ModelSpec]:
        return [model for model in self.models if model.enabled]


class AppSettings(BaseSettings):
    """Runtime secrets and environment. Loaded from `.env` and process env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    hf_api_key: str = Field(default="", alias="HF_API_KEY")
