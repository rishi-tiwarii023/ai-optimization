from __future__ import annotations

from abc import ABC, abstractmethod

from src.contracts.config import ModelSpec, ProviderConfig
from src.contracts.responses import ModelResponse


class ModelProvider(ABC):
    """Port for generating completions. Implementations must stay stateless."""

    @abstractmethod
    def generate(self, prompt: str, model: ModelSpec) -> ModelResponse:
        """Return a common response schema for a single prompt/model pair."""

    @classmethod
    @abstractmethod
    def from_config(cls, provider_config: ProviderConfig, env: dict[str, str]) -> "ModelProvider":
        """Build an instance from provider config and an env-var dict (pass os.environ)."""

    @abstractmethod
    def get_agent_env(self, model: ModelSpec) -> dict[str, str]:
        """Return env vars that OpenHands needs to talk to this provider for the given model. Keys like LLM_BASE_URL, LLM_MODEL, LLM_API_KEY, proxy vars, etc."""
