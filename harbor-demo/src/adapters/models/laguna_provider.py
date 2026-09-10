from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any

from src.adapters.http_proxy import build_forced_proxy_opener
from src.adapters.models.provider import ModelProvider
from src.contracts.config import ModelSpec
from src.contracts.responses import ModelResponse, TokenUsage


class LagunaProvider(ModelProvider):
    """Stateless client for a local LiteLLM/Laguna OpenAI-compatible proxy.

    Credentials, endpoint, and proxy are injected; no client cache is kept.
    """

    def __init__(
        self,
        api_key: str,
        api_endpoint: str,
        proxy_url: str = "",
        timeout_seconds: float = 120.0,
    ) -> None:
        if not api_endpoint:
            raise ValueError("LAGUNA_API_ENDPOINT is required to construct LagunaProvider.")
        self._api_key = api_key
        self._api_endpoint = api_endpoint.rstrip("/")
        self._proxy_url = proxy_url.strip()
        self._timeout_seconds = timeout_seconds

    def generate(self, prompt: str, model: ModelSpec) -> ModelResponse:
        started = time.perf_counter()
        try:
            output, usage = self._complete(prompt=prompt, model=model)
            return ModelResponse(
                model_name=model.inference_id,
                output=output,
                token_usage=usage,
                latency=time.perf_counter() - started,
                error=None,
            )
        except Exception as exc:  # noqa: BLE001
            return ModelResponse(
                model_name=model.inference_id,
                output=None,
                token_usage=None,
                latency=time.perf_counter() - started,
                error=str(exc),
            )

    def _complete(self, prompt: str, model: ModelSpec) -> tuple[str, TokenUsage | None]:
        payload: dict[str, Any] = {
            "model": model.inference_id,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": model.max_new_tokens,
            "temperature": model.temperature,
        }
        if model.top_p is not None:
            payload["top_p"] = model.top_p

        url = f"{self._api_endpoint}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        opener = build_forced_proxy_opener(self._proxy_url)
        try:
            with opener.open(request, timeout=self._timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Laguna HTTP {exc.code}: {detail}") from exc

        choices = body.get("choices") or []
        message = choices[0].get("message") if choices else {}
        choice = (message or {}).get("content") or ""
        usage = None
        raw_usage = body.get("usage")
        if isinstance(raw_usage, dict):
            usage = TokenUsage(
                prompt_tokens=raw_usage.get("prompt_tokens"),
                completion_tokens=raw_usage.get("completion_tokens"),
                total_tokens=raw_usage.get("total_tokens"),
            )
        return choice or "", usage
