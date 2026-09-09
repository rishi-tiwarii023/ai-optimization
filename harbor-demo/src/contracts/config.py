from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TaskSpec(BaseModel):
    id: str
    name: str | None = None
    path: str | None = None
    enabled: bool = True


class AgentSpec(BaseModel):
    id: str
    name: str | None = None
    enabled: bool = True


class ModelSpec(BaseModel):
    """A model that can be enabled or tuned without code changes."""

    id: str
    enabled: bool = True
    max_new_tokens: int = Field(default=512, ge=1)
    temperature: float = Field(default=0.2, ge=0.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)


class ProviderConfig(BaseModel):
    type: Literal["huggingface"] = "huggingface"
    timeout_seconds: float = Field(default=120.0, gt=0)


class ExperimentConfig(BaseModel):
    name: str
    provider: ProviderConfig = Field(default_factory=ProviderConfig)
    tasks: list[TaskSpec] = Field(default_factory=list)
    agents: list[AgentSpec] = Field(default_factory=list)
    models: list[ModelSpec] = Field(default_factory=list)
    attempts: int = Field(default=1, ge=1)

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
