from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from pathlib import Path

from src.arms.adapters.storage.filesystem_store import FilesystemArtifactStore
from src.arms.application.run_experiment import run_experiment
from src.contracts.trials import FinalTrialResult, TrialRequest
from src.experiments.compiler import ExperimentCompiler
from src.experiments.loader import REPO_ROOT


def main(
    argv: Sequence[str] | None = None,
    *,
    execute_trial: Callable[[TrialRequest], FinalTrialResult] | None = None,
) -> int:
    """Read experiment.yaml, run trials, aggregate metrics, write the HTML dashboard."""

    args = _parse_args(argv)
    compiler = ExperimentCompiler()
    requests = compiler.compile(args.experiment)
    print(f"Read experiment.yaml → {len(requests)} TrialRequest(s)")
    for request in requests:
        print(f"  {request.trial_id}")

    metrics_path = args.metrics or (REPO_ROOT / "artifacts" / "metrics.json")
    report_path = args.report or (REPO_ROOT / "reports" / "index.html")
    artifacts_root = args.artifacts or (REPO_ROOT / "artifacts")

    print("Running trials (sandbox → OpenHands → verifier → artifacts)...")
    results = run_experiment(
        args.experiment,
        compiler=compiler,
        execute_trial=execute_trial,
        metrics_path=metrics_path,
        report_path=report_path,
        write_metrics=True,
        write_report=True,
    )

    bundle_count = _artifact_bundle_count(artifacts_root, results)
    dashboard_count = 1 if report_path.is_file() else 0
    _print_summary(
        request_count=len(requests),
        result_count=len(results),
        bundle_count=bundle_count,
        dashboard_count=dashboard_count,
        report_path=report_path,
        results=results,
    )
    return 0


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m arms.cli.run_experiment",
        description="Compile the YAML matrix, run every trial, and write reports/index.html.",
    )
    parser.add_argument(
        "--experiment",
        type=Path,
        default=None,
        help="Path to experiment.yaml (default: src/experiments/experiment.yaml)",
    )
    parser.add_argument("--metrics", type=Path, default=None, help="metrics.json output path")
    parser.add_argument("--report", type=Path, default=None, help="HTML dashboard output path")
    parser.add_argument("--artifacts", type=Path, default=None, help="Artifact root (run_* dirs)")
    return parser.parse_args(list(argv) if argv is not None else None)


def _artifact_bundle_count(artifacts_root: Path, results: list[FinalTrialResult]) -> int:
    store = FilesystemArtifactStore(artifacts_root)
    return sum(1 for result in results if store.trial_dir(result.trial_id).is_dir())


def _print_summary(
    *,
    request_count: int,
    result_count: int,
    bundle_count: int,
    dashboard_count: int,
    report_path: Path,
    results: list[FinalTrialResult],
) -> None:
    print()
    print("=== Execution summary ===")
    print(f"TrialRequests:     {request_count}")
    print(f"TrialResults:      {result_count}")
    print(f"Artifact bundles:  {bundle_count}")
    print(f"HTML dashboard:    {dashboard_count}  ({report_path})")
    print()
    for result in results:
        score = result.score
        line = (
            f"  {result.model_id}: status={result.execution.status} "
            f"passed={score.passed} score_tests={score.tests_passed}/{score.tests_passed + score.tests_failed}"
        )
        if result.execution.error_details:
            line += f" error={result.execution.error_details}"
        print(line)


if __name__ == "__main__":
    raise SystemExit(main())
