from __future__ import annotations

import os

from src.adapters.models.provider import ModelProvider
from src.adapters.models.registry import get_provider
from src.contracts.config import ExperimentConfig, ProviderConfig


def _load_providers() -> None:
    """Import provider modules so their @register decorators fire."""
    from src.adapters.models import laguna_provider as _  # noqa: F401


_load_providers()


def create_model_provider(
    provider_config: ProviderConfig | ExperimentConfig,
    env: dict[str, str] | None = None,
) -> ModelProvider:
    """Look up provider in registry and instantiate via from_config()."""
    if env is None:
        env = dict(os.environ)
    config = (
        provider_config.provider
        if isinstance(provider_config, ExperimentConfig)
        else provider_config
    )
    provider_class = get_provider(config.type)
    return provider_class.from_config(config, env)
