from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.arms.adapters.storage.filesystem_store import (
    ArtifactAlreadyExistsError,
    FilesystemArtifactStore,
    load_trial_artifacts,
    save_trial_artifacts,
)
from src.contracts.scoring import ScoreResult
from src.contracts.trials import FinalTrialResult, ResourceUsage, TrajectoryEvent, TrialResult


def _result() -> FinalTrialResult:
    return FinalTrialResult(
        trial_id="exp::health-api::openhands::model1::1",
        experiment_id="exp",
        task_id="health-api",
        model_id="model1",
        attempt=1,
        execution=TrialResult(
            status="success",
            patch="--- a/app/main.py\n+++ b/app/main.py\n",
            trajectory=[
                TrajectoryEvent(kind="message", payload={"role": "assistant", "content": "hi"}),
                TrajectoryEvent(kind="tool_call", payload={"name": "edit"}),
                TrajectoryEvent(kind="command", payload={"cmd": "pytest"}),
            ],
            execution_logs="container started",
            resource_usage=ResourceUsage(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                latency_seconds=1.5,
            ),
            error_details=None,
        ),
        score=ScoreResult(passed=True, build_passed=True, tests_passed=3, tests_failed=0),
    )


def test_save_and_load_trial_artifacts(tmp_path: Path) -> None:
    stamp = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    result = _result()
    saved = save_trial_artifacts(result, tmp_path, timestamp=stamp)
    assert saved.name == "run_exp__health-api__openhands__model1__1"
    names = {path.name for path in saved.iterdir()}
    assert names == {
        "manifest.json",
        "trajectory.json",
        "stdout.log",
        "stderr.log",
        "patch.diff",
        "agent-result.json",
        "resource-usage.json",
        "verifier-result.json",
    }

    loaded = load_trial_artifacts(result.trial_id, tmp_path)
    assert loaded["manifest"] == {
        "experiment_id": "exp",
        "task_id": "health-api",
        "model_id": "model1",
        "attempt_id": 1,
        "timestamp": "2026-09-09T12:00:00+00:00",
    }
    assert loaded["trajectory"]["agent_messages"] == [{"role": "assistant", "content": "hi"}]
    assert loaded["trajectory"]["tool_calls"] == [{"name": "edit"}]
    assert loaded["trajectory"]["command_history"] == [{"cmd": "pytest"}]
    assert loaded["stdout"] == "container started"
    assert loaded["stderr"] == ""
    assert loaded["patch"] == "--- a/app/main.py\n+++ b/app/main.py\n"
    assert loaded["agent_result"]["status"] == "success"
    assert loaded["resource_usage"]["execution_time"] == 1.5
    assert loaded["resource_usage"]["token_usage"]["total_tokens"] == 30
    assert loaded["resource_usage"]["tool_calls"] == 1
    assert loaded["resource_usage"]["estimated_cost"] == 0.0
    assert loaded["verifier_result"]["passed"] is True


def test_artifacts_are_immutable_after_creation(tmp_path: Path) -> None:
    result = _result()
    store = FilesystemArtifactStore(tmp_path)
    saved = store.save_trial_artifacts(result)
    with pytest.raises(ArtifactAlreadyExistsError):
        store.save_trial_artifacts(result)
    patch = saved / "patch.diff"
    with pytest.raises(PermissionError):
        patch.write_text("mutated", encoding="utf-8")
    assert patch.read_text(encoding="utf-8") == "--- a/app/main.py\n+++ b/app/main.py\n"
