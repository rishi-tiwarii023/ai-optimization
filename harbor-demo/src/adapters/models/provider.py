from __future__ import annotations

from abc import ABC, abstractmethod

from src.contracts.config import ModelSpec
from src.contracts.responses import ModelResponse


class ModelProvider(ABC):
    """Port for generating completions. Implementations must stay stateless."""

    @abstractmethod
    def generate(self, prompt: str, model: ModelSpec) -> ModelResponse:
        """Return a common response schema for a single prompt/model pair."""
