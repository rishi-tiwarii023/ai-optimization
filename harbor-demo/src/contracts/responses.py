from __future__ import annotations

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ModelResponse(BaseModel):
    model_name: str
    output: str | None = None
    token_usage: TokenUsage | None = None
    latency: float = Field(description="Wall-clock latency in seconds.")
    error: str | None = None
