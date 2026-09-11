from __future__ import annotations

import json
from pathlib import Path

from src.arms.application.run_experiment import run_experiment
from src.arms.application.run_trial import run_trial
from src.contracts.config import AgentSpec, ModelSpec, ProviderConfig, TaskSpec
from src.contracts.scoring import ScoreResult, VerificationRequest
from src.contracts.trials import FinalTrialResult, TrialRequest, TrialResult
from src.experiments.compiler import ExperimentCompiler


class FakeSandbox:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        self.destroyed = False

    def mount(self) -> Path:
        self.workspace.mkdir(parents=True, exist_ok=True)
        return self.workspace

    def destroy(self) -> None:
        self.destroyed = True


class FakeSandboxFactory:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.created: list[str] = []
        self.sandboxes: list[FakeSandbox] = []

    def create(self, request: TrialRequest) -> FakeSandbox:
        self.created.append(request.trial_id)
        sandbox = FakeSandbox(self.root / request.model.id)
        self.sandboxes.append(sandbox)
        return sandbox


class FakeAgent:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def execute(self, request: TrialRequest, sandbox: FakeSandbox) -> TrialResult:
        self.calls.append(request.trial_id)
        sandbox.mount()
        return TrialResult(status="success", execution_logs=request.model.id)


class FakeVerifier:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def verify(self, request: VerificationRequest) -> ScoreResult:
        self.calls.append(request.trial_id)
        return ScoreResult(passed=False, build_passed=False, tests_passed=0, tests_failed=3)


def _request(model_id: str = "model1") -> TrialRequest:
    return TrialRequest(
        trial_id=f"exp::health-api::openhands::{model_id}::1",
        experiment_id="exp",
        task=TaskSpec(id="health-api", path="datasets/internal-core/health-api"),
        agent=AgentSpec(id="openhands"),
        model=ModelSpec(id=model_id, model_id=model_id),
        attempt=1,
        provider=ProviderConfig(),
    )


def test_run_trial_pipeline_and_destroys_sandbox(tmp_path: Path) -> None:
    factory = FakeSandboxFactory(tmp_path / "ws")
    agent = FakeAgent()
    verifier = FakeVerifier()
    request = _request()
    result = run_trial(
        request,
        sandbox_factory=factory,
        agent=agent,
        verifier=verifier,
        artefact_dir=tmp_path / "artefacts",
        repo_root=tmp_path,
    )
    assert result.trial_id == request.trial_id
    assert result.execution.status == "success"
    assert result.score.tests_failed == 3
    assert factory.sandboxes[0].destroyed is True
    assert agent.calls == [request.trial_id]
    assert verifier.calls == [request.trial_id]
    artifacts = tmp_path / "artifacts" / "run_exp__health-api__openhands__model1__1"
    assert (artifacts / "manifest.json").is_file()
    assert (artifacts / "verifier-result.json").is_file()


def test_run_trial_destroys_sandbox_when_agent_fails(tmp_path: Path) -> None:
    class BoomAgent:
        def execute(self, request: TrialRequest, sandbox: FakeSandbox) -> TrialResult:
            raise RuntimeError("agent crashed")

    factory = FakeSandboxFactory(tmp_path / "ws")
    result = run_trial(
        _request(),
        sandbox_factory=factory,
        agent=BoomAgent(),
        verifier=FakeVerifier(),
        artefact_dir=tmp_path / "artefacts",
        repo_root=tmp_path,
    )
    assert result.execution.status == "error"
    assert "agent crashed" in (result.execution.error_details or "")
    assert factory.sandboxes[0].destroyed is True


def test_run_experiment_executes_five_independent_trials() -> None:
    seen: list[str] = []

    def execute_trial(request: TrialRequest) -> FinalTrialResult:
        seen.append(request.trial_id)
        return FinalTrialResult(
            trial_id=request.trial_id,
            experiment_id=request.experiment_id,
            task_id=request.task.id,
            model_id=request.model.id,
            attempt=request.attempt,
            execution=TrialResult(status="success"),
            score=ScoreResult(passed=False, build_passed=False, tests_passed=0, tests_failed=0),
        )

    results = run_experiment(execute_trial=execute_trial, write_metrics=False)
    assert len(ExperimentCompiler().compile()) == 5
    assert len(results) == 5
    assert len(set(seen)) == 5
    assert [item.model_id for item in results] == [
        "model1",
        "model2",
        "model3",
        "model4",
        "model5",
    ]
    assert all(item.task_id == "health-api" for item in results)
    assert all(item.attempt == 1 for item in results)


def test_run_experiment_continues_after_one_trial_failure() -> None:
    def execute_trial(request: TrialRequest) -> FinalTrialResult:
        if request.model.id == "model2":
            raise RuntimeError("isolated failure")
        return FinalTrialResult(
            trial_id=request.trial_id,
            experiment_id=request.experiment_id,
            task_id=request.task.id,
            model_id=request.model.id,
            attempt=request.attempt,
            execution=TrialResult(status="success"),
            score=ScoreResult(passed=False, build_passed=False, tests_passed=0, tests_failed=0),
        )

    results = run_experiment(execute_trial=execute_trial, write_metrics=False)
    assert len(results) == 5
    failed = next(item for item in results if item.model_id == "model2")
    assert failed.execution.status == "error"
    assert "isolated failure" in (failed.execution.error_details or "")
    assert sum(1 for item in results if item.execution.status == "success") == 4


def test_run_experiment_writes_metrics_json(tmp_path: Path) -> None:
    def execute_trial(request: TrialRequest) -> FinalTrialResult:
        return FinalTrialResult(
            trial_id=request.trial_id,
            experiment_id=request.experiment_id,
            task_id=request.task.id,
            model_id=request.model.id,
            attempt=request.attempt,
            execution=TrialResult(status="success"),
            score=ScoreResult(passed=False, build_passed=False, tests_passed=0, tests_failed=0),
        )

    path = tmp_path / "metrics.json"
    results = run_experiment(execute_trial=execute_trial, metrics_path=path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert len(results) == 5
    assert len(payload["trials"]) == 5
    assert payload["aggregate"]["trial_count"] == 5
    assert set(payload["by_model"]) == {"model1", "model2", "model3", "model4", "model5"}
    assert (tmp_path / "reports" / "index.html").is_file()

