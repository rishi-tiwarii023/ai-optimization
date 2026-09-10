from __future__ import annotations

from src.adapters.models.huggingface_provider import HuggingFaceProvider
from src.adapters.models.laguna_provider import LagunaProvider
from src.adapters.models.provider import ModelProvider
from src.contracts.config import AppSettings, ExperimentConfig, ProviderConfig


def create_model_provider(
    settings: AppSettings,
    provider_config: ProviderConfig | ExperimentConfig,
) -> ModelProvider:
    """Compose a ModelProvider from injected settings and experiment config."""
    config = (
        provider_config.provider
        if isinstance(provider_config, ExperimentConfig)
        else provider_config
    )
    if config.type == "laguna":
        return LagunaProvider(
            api_key=settings.laguna_api_key,
            api_endpoint=config.api_endpoint or settings.laguna_api_endpoint,
            proxy_url=config.proxy_url or settings.laguna_proxy_url,
            timeout_seconds=config.timeout_seconds,
        )
    if config.type == "huggingface":
        return HuggingFaceProvider(
            api_key=settings.hf_api_key,
            timeout_seconds=config.timeout_seconds,
        )
    raise ValueError(f"Unsupported provider type: {config.type}")
