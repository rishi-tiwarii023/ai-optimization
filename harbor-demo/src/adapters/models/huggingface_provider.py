from __future__ import annotations

import time
from typing import Any

from huggingface_hub import InferenceClient

from src.adapters.models.provider import ModelProvider
from src.contracts.config import ModelSpec
from src.contracts.responses import ModelResponse, TokenUsage


class HuggingFaceProvider(ModelProvider):
    """Stateless Hugging Face Inference adapter.

    Credentials and timeout are injected; no conversation or client cache is kept.
    """

    def __init__(self, api_key: str, timeout_seconds: float = 120.0) -> None:
        if not api_key:
            raise ValueError("HF_API_KEY is required to construct HuggingFaceProvider.")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def generate(self, prompt: str, model: ModelSpec) -> ModelResponse:
        started = time.perf_counter()
        try:
            output, usage = self._complete(prompt=prompt, model=model)
            return ModelResponse(
                model_name=model.id,
                output=output,
                token_usage=usage,
                latency=time.perf_counter() - started,
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            return ModelResponse(
                model_name=model.id,
                output=None,
                token_usage=None,
                latency=time.perf_counter() - started,
                error=str(exc),
            )

    def _complete(self, prompt: str, model: ModelSpec) -> tuple[str, TokenUsage | None]:
        client = InferenceClient(token=self._api_key, timeout=self._timeout_seconds)
        kwargs: dict[str, Any] = {
            "model": model.id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": model.max_new_tokens,
            "temperature": model.temperature,
        }
        if model.top_p is not None:
            kwargs["top_p"] = model.top_p

        completion = client.chat.completions.create(**kwargs)
        choice = completion.choices[0].message.content if completion.choices else ""
        usage = None
        raw_usage = getattr(completion, "usage", None)
        if raw_usage is not None:
            usage = TokenUsage(
                prompt_tokens=getattr(raw_usage, "prompt_tokens", None),
                completion_tokens=getattr(raw_usage, "completion_tokens", None),
                total_tokens=getattr(raw_usage, "total_tokens", None),
            )
        return choice or "", usage
