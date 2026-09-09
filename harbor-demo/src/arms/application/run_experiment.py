from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from src.arms.application.run_trial import run_trial
from src.arms.reporting.dashboard import generate_dashboard
from src.arms.reporting.metrics import MetricsCollector
from src.contracts.config import ExperimentConfig
from src.contracts.scoring import ScoreResult
from src.contracts.trials import FinalTrialResult, TrialRequest, TrialResult
from src.experiments.compiler import ExperimentCompiler
from src.experiments.loader import REPO_ROOT


def run_experiment(
    source: ExperimentConfig | str | Path | None = None,
    *,
    compiler: ExperimentCompiler | None = None,
    execute_trial: Callable[[TrialRequest], FinalTrialResult] | None = None,
    metrics_path: Path | None = None,
    write_metrics: bool = True,
    report_path: Path | None = None,
    write_report: bool = True,
) -> list[FinalTrialResult]:
    """Load YAML, expand TrialRequests, run each trial independently, write metrics.json."""

    requests = (compiler or ExperimentCompiler()).compile(source)
    run_one = execute_trial or run_trial
    results: list[FinalTrialResult] = []
    for request in requests:
        results.append(_run_independently(run_one, request))
    if write_metrics:
        path = metrics_path or (REPO_ROOT / "artifacts" / "metrics.json")
        collector = MetricsCollector()
        collector.write(collector.collect(results), path)
        if write_report:
            generate_dashboard(
                search_root=_report_search_root(path),
                output_path=report_path or _default_report_path(path),
            )
    return results


def _default_report_path(metrics_path: Path) -> Path:
    try:
        metrics_path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return metrics_path.parent / "reports" / "index.html"
    return REPO_ROOT / "reports" / "index.html"


def _report_search_root(metrics_path: Path) -> Path:
    try:
        metrics_path.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return metrics_path.parent
    return REPO_ROOT


def _run_independently(
    run_one: Callable[[TrialRequest], FinalTrialResult],
    request: TrialRequest,
) -> FinalTrialResult:
    try:
        return run_one(request)
    except Exception as exc:  # noqa: BLE001
        return FinalTrialResult(
            trial_id=request.trial_id,
            experiment_id=request.experiment_id,
            task_id=request.task.id,
            model_id=request.model.id,
            attempt=request.attempt,
            execution=TrialResult(status="error", error_details=str(exc)),
            score=ScoreResult(
                passed=False,
                build_passed=False,
                tests_passed=0,
                tests_failed=0,
            ),
        )
