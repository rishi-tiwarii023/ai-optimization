from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

import pytest

from src.arms.reporting.metrics import MetricsCollector
from src.contracts.scoring import ScoreResult
from src.contracts.trials import FinalTrialResult, ResourceUsage, TrajectoryEvent, TrialResult


def _trial(
    *,
    model_id: str,
    status: Literal["success", "error", "timeout"] = "success",
    build_passed: bool = True,
    tests_passed: int = 2,
    tests_failed: int = 1,
    passed: bool = False,
    latency: float = 1.25,
    tokens: int = 40,
    tool_calls: int = 1,
) -> FinalTrialResult:
    trajectory = [
        TrajectoryEvent(kind="tool_call", payload={"name": "edit"})
        for _ in range(tool_calls)
    ]
    return FinalTrialResult(
        trial_id=f"exp::health-api::openhands::{model_id}::1",
        experiment_id="exp",
        task_id="health-api",
        model_id=model_id,
        attempt=1,
        execution=TrialResult(
            status=status,
            trajectory=trajectory,
            resource_usage=ResourceUsage(total_tokens=tokens, latency_seconds=latency),
        ),
        score=ScoreResult(
            passed=passed,
            build_passed=build_passed,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
        ),
    )


def test_collect_returns_one_metrics_object_per_trial() -> None:
    results = [
        _trial(model_id="model1", passed=True, tests_passed=3, tests_failed=0),
        _trial(model_id="model2", status="error", build_passed=False, tests_passed=0, tests_failed=3, tokens=10, tool_calls=0),
    ]
    metrics = MetricsCollector().collect(results)
    assert len(metrics) == 2
    first = metrics[0]
    assert first.model_name == "model1"
    assert first.status == "success"
    assert first.build_passed is True
    assert first.tests_passed == 3
    assert first.test_count == 3
    assert first.execution_time == 1.25
    assert first.token_usage == 40
    assert first.estimated_cost == 0.0
    assert first.tool_calls == 1
    assert first.score == 1.0
    assert metrics[1].score == 0.0
    assert metrics[1].test_count == 3


def test_aggregate_across_all_trials() -> None:
    results = [
        _trial(model_id="model1", passed=True, tests_passed=3, tests_failed=0, latency=2.0, tokens=10, tool_calls=2),
        _trial(model_id="model2", tests_passed=1, tests_failed=2, latency=3.0, tokens=30, tool_calls=1),
    ]
    collector = MetricsCollector()
    metrics = collector.collect(results)
    summary = collector.aggregate(metrics)
    assert summary["trial_count"] == 2
    assert summary["build_passed"] == 2
    assert summary["tests_passed"] == 4
    assert summary["test_count"] == 6
    assert summary["execution_time"] == 5.0
    assert summary["token_usage"] == 40
    assert summary["tool_calls"] == 3
    assert summary["score"] == pytest.approx((1.0 + (1 / 3)) / 2, abs=1e-4)


def test_write_metrics_json(tmp_path: Path) -> None:
    collector = MetricsCollector()
    metrics = collector.collect([_trial(model_id="model1", passed=True, tests_passed=3, tests_failed=0)])
    path = collector.write(metrics, tmp_path / "metrics.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert path.name == "metrics.json"
    assert len(payload["trials"]) == 1
    assert payload["trials"][0]["model_name"] == "model1"
    assert payload["aggregate"]["trial_count"] == 1
    assert payload["by_model"]["model1"]["trial_count"] == 1
