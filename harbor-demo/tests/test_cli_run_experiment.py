from __future__ import annotations

from pathlib import Path

from src.arms.adapters.storage.filesystem_store import FilesystemArtifactStore
from src.arms.cli.run_experiment import main
from src.contracts.scoring import ScoreResult
from src.contracts.trials import FinalTrialResult, TrialRequest, TrialResult


def test_cli_run_experiment_prints_expected_summary(tmp_path: Path, capsys) -> None:
    artifacts = tmp_path / "artifacts"
    store = FilesystemArtifactStore(artifacts)

    def execute_trial(request: TrialRequest) -> FinalTrialResult:
        result = FinalTrialResult(
            trial_id=request.trial_id,
            experiment_id=request.experiment_id,
            task_id=request.task.id,
            model_id=request.model.id,
            attempt=request.attempt,
            execution=TrialResult(status="success"),
            score=ScoreResult(passed=False, build_passed=False, tests_passed=0, tests_failed=0),
        )
        store.save_trial_artifacts(result)
        return result

    code = main(
        [
            "--metrics",
            str(tmp_path / "metrics.json"),
            "--report",
            str(tmp_path / "reports" / "index.html"),
            "--artifacts",
            str(artifacts),
        ],
        execute_trial=execute_trial,
    )
    captured = capsys.readouterr().out
    assert code == 0
    assert "5 TrialRequest(s)" in captured
    assert "TrialRequests:     5" in captured
    assert "TrialResults:      5" in captured
    assert "Artifact bundles:  5" in captured
    assert "HTML dashboard:    1" in captured
    assert (tmp_path / "reports" / "index.html").is_file()
    assert (tmp_path / "metrics.json").is_file()


def test_cli_prints_trial_error_details(tmp_path: Path, capsys) -> None:
    def execute_trial(request: TrialRequest) -> FinalTrialResult:
        return FinalTrialResult(
            trial_id=request.trial_id,
            experiment_id=request.experiment_id,
            task_id=request.task.id,
            model_id=request.model.id,
            attempt=request.attempt,
            execution=TrialResult(status="error", error_details="OpenHands binary not found"),
            score=ScoreResult(passed=False, build_passed=False, tests_passed=0, tests_failed=0),
        )

    main(
        [
            "--metrics",
            str(tmp_path / "metrics.json"),
            "--report",
            str(tmp_path / "reports" / "index.html"),
            "--artifacts",
            str(tmp_path / "artifacts"),
        ],
        execute_trial=execute_trial,
    )
    assert "error=OpenHands binary not found" in capsys.readouterr().out
