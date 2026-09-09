from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.adapters.sandbox.docker_sandbox import DockerSandboxFactory
from src.adapters.verifiers.factory import create_verifier
from src.adapters.verifiers.verifier import Verifier
from src.arms.adapters.agents.openhands_adapter import OpenHandsAdapter
from src.contracts.sandbox import SandboxSession
from src.contracts.scoring import ScoreResult, VerificationRequest
from src.contracts.trials import FinalTrialResult, TrialRequest, TrialResult
from src.experiments.loader import REPO_ROOT


class SandboxFactory(Protocol):
    def create(self, request: TrialRequest) -> SandboxSession:
        ...


def run_trial(
    request: TrialRequest,
    *,
    sandbox_factory: SandboxFactory | None = None,
    agent: OpenHandsAdapter | None = None,
    verifier: Verifier | None = None,
    artefact_dir: Path | None = None,
    repo_root: Path | None = None,
) -> FinalTrialResult:
    """Sandbox -> OpenHands -> verifier -> FinalTrialResult. Always destroy the sandbox."""

    root = repo_root or REPO_ROOT
    factory = sandbox_factory or DockerSandboxFactory(repo_root=root)
    agent_runtime = agent or OpenHandsAdapter(repo_root=root)
    scorer = verifier or create_verifier()
    artefacts = artefact_dir or (root / "artefacts")

    sandbox = factory.create(request)
    execution: TrialResult | None = None
    score: ScoreResult | None = None
    try:
        execution = agent_runtime.execute(request, sandbox)
        workspace = sandbox.mount()
        task_path = _task_path(request, root)
        score = scorer.verify(
            VerificationRequest(
                trial_id=request.trial_id,
                workspace=workspace,
                task_path=task_path,
                artefact_dir=artefacts,
            )
        )
    except Exception as exc:  # noqa: BLE001
        execution = execution or TrialResult(status="error", error_details=str(exc))
        score = score or ScoreResult(
            passed=False,
            build_passed=False,
            tests_passed=0,
            tests_failed=0,
        )
        if execution.error_details is None:
            execution = execution.model_copy(update={"error_details": str(exc)})
    finally:
        sandbox.destroy()

    assert execution is not None
    assert score is not None
    return FinalTrialResult(
        trial_id=request.trial_id,
        experiment_id=request.experiment_id,
        task_id=request.task.id,
        model_id=request.model.id,
        attempt=request.attempt,
        execution=execution,
        score=score,
    )


def _task_path(request: TrialRequest, repo_root: Path) -> Path:
    raw = request.task.path
    if raw:
        path = Path(raw)
        return path if path.is_absolute() else repo_root / path
    return repo_root / "datasets" / "internal-core" / request.task.id
