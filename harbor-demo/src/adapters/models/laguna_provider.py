from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

from src.adapters.http_proxy import build_forced_proxy_opener
from src.adapters.models.provider import ModelProvider
from src.adapters.models.registry import register
from src.contracts.config import ModelSpec
from src.contracts.responses import ModelResponse, TokenUsage

if TYPE_CHECKING:
    from src.contracts.config import ProviderConfig


@register("laguna")
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
        prefix: str = "litellm_proxy",
    ) -> None:
        self._api_key = api_key
        self._api_endpoint = api_endpoint.rstrip("/")
        self._proxy_url = proxy_url.strip()
        self._timeout_seconds = timeout_seconds
        self._prefix = (prefix or "litellm_proxy").strip().rstrip("/") or "litellm_proxy"

    @classmethod
    def from_config(cls, provider_config: "ProviderConfig", env: dict[str, str]) -> "LagunaProvider":
        api_key = provider_config.extra.get("api_key") or env.get("LAGUNA_API_KEY", "")
        api_endpoint = (
            provider_config.api_endpoint
            or env.get("LAGUNA_API_ENDPOINT", "")
        )
        proxy_url = (
            provider_config.proxy_url
            or env.get("LAGUNA_PROXY_URL", "")
        )
        return cls(
            api_key=api_key,
            api_endpoint=api_endpoint,
            proxy_url=proxy_url,
            timeout_seconds=provider_config.timeout_seconds,
            prefix=provider_config.prefix,
        )

    def get_agent_env(self, model: ModelSpec) -> dict[str, str]:
        """Return env vars OpenHands needs to call this Laguna/LiteLLM endpoint."""
        from src.adapters.http_proxy import proxy_environment

        env: dict[str, str] = {}
        if self._api_endpoint:
            env["LLM_BASE_URL"] = self._api_endpoint
            env["LLM_API_BASE"] = self._api_endpoint
            env["OPENAI_API_BASE"] = self._api_endpoint
            env["OPENAI_BASE_URL"] = self._api_endpoint
        if self._api_key:
            env["LLM_API_KEY"] = self._api_key
        env.update(proxy_environment(self._proxy_url))
        return env

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
        if not self._api_endpoint:
            raise ValueError("LAGUNA_API_ENDPOINT is required to generate with LagunaProvider.")
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
