from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.contracts.scoring import ScoreResult
from src.contracts.trials import FinalTrialResult, ResourceUsage, TrialResult

_USD_PER_TOKEN = 0.0


class ModelMetrics(BaseModel):
    """Per-trial metrics derived from verifier, resource usage, and trial result."""

    model_name: str
    status: Literal["success", "error", "timeout"]
    build_passed: bool
    tests_passed: int = Field(ge=0)
    test_count: int = Field(ge=0)
    execution_time: float | None = None
    token_usage: int = Field(ge=0)
    estimated_cost: float = Field(ge=0.0)
    tool_calls: int = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)


class MetricsCollector:
    """Build one ModelMetrics row per trial and aggregate across a run."""

    def collect(self, results: Sequence[FinalTrialResult]) -> list[ModelMetrics]:
        return [_from_trial(item) for item in results]

    def aggregate(self, metrics: Sequence[ModelMetrics]) -> dict[str, Any]:
        return _aggregate(metrics)

    def to_payload(self, metrics: Sequence[ModelMetrics]) -> dict[str, Any]:
        return {
            "trials": [item.model_dump() for item in metrics],
            "aggregate": self.aggregate(metrics),
            "by_model": _by_model(metrics),
        }

    def write(self, metrics: Sequence[ModelMetrics], path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_payload(metrics), indent=2) + "\n", encoding="utf-8")
        return path


def _from_trial(result: FinalTrialResult) -> ModelMetrics:
    execution = result.execution
    verifier = result.score
    usage = execution.resource_usage or ResourceUsage()
    test_count = verifier.tests_passed + verifier.tests_failed
    return ModelMetrics(
        model_name=result.model_id,
        status=execution.status,
        build_passed=verifier.build_passed,
        tests_passed=verifier.tests_passed,
        test_count=test_count,
        execution_time=usage.latency_seconds,
        token_usage=_token_total(usage),
        estimated_cost=_estimated_cost(usage),
        tool_calls=_tool_call_count(execution),
        score=_score(verifier, test_count),
    )


def _token_total(usage: ResourceUsage) -> int:
    if usage.total_tokens is not None:
        return usage.total_tokens
    return (usage.prompt_tokens or 0) + (usage.completion_tokens or 0)


def _estimated_cost(usage: ResourceUsage) -> float:
    return round(float(_token_total(usage)) * _USD_PER_TOKEN, 8)


def _tool_call_count(execution: TrialResult) -> int:
    return sum(1 for event in execution.trajectory if event.kind == "tool_call")


def _score(verifier: ScoreResult, test_count: int) -> float:
    if verifier.passed:
        return 1.0
    if test_count <= 0:
        return 0.0
    return round(verifier.tests_passed / test_count, 4)


def _aggregate(metrics: Sequence[ModelMetrics]) -> dict[str, Any]:
    count = len(metrics)
    times = [item.execution_time for item in metrics if item.execution_time is not None]
    tests_passed = sum(item.tests_passed for item in metrics)
    test_count = sum(item.test_count for item in metrics)
    return {
        "trial_count": count,
        "build_passed": sum(1 for item in metrics if item.build_passed),
        "tests_passed": tests_passed,
        "test_count": test_count,
        "execution_time": round(sum(times), 6) if times else None,
        "token_usage": sum(item.token_usage for item in metrics),
        "estimated_cost": round(sum(item.estimated_cost for item in metrics), 8),
        "tool_calls": sum(item.tool_calls for item in metrics),
        "score": round(sum(item.score for item in metrics) / count, 4) if count else 0.0,
    }


def _by_model(metrics: Sequence[ModelMetrics]) -> dict[str, Any]:
    grouped: dict[str, list[ModelMetrics]] = {}
    for item in metrics:
        grouped.setdefault(item.model_name, []).append(item)
    return {name: _aggregate(rows) for name, rows in grouped.items()}
