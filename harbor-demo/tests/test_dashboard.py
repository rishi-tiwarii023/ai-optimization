from __future__ import annotations

import json
from pathlib import Path

from src.arms.application.run_experiment import run_experiment
from src.arms.reporting.dashboard import generate_dashboard
from src.contracts.scoring import ScoreResult
from src.contracts.trials import FinalTrialResult, TrialRequest, TrialResult


def _write_metrics(path: Path, trials: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"trials": trials, "aggregate": {}, "by_model": {}}) + "\n", encoding="utf-8")


def test_generate_dashboard_from_all_metrics_json(tmp_path: Path) -> None:
    _write_metrics(
        tmp_path / "a" / "metrics.json",
        [
            {
                "model_name": "model1",
                "status": "success",
                "build_passed": True,
                "tests_passed": 3,
                "test_count": 3,
                "execution_time": 2.0,
                "token_usage": 40,
                "estimated_cost": 0.02,
                "score": 1.0,
            }
        ],
    )
    _write_metrics(
        tmp_path / "b" / "metrics.json",
        [
            {
                "model_name": "model2",
                "status": "error",
                "build_passed": False,
                "tests_passed": 0,
                "test_count": 3,
                "execution_time": 5.0,
                "token_usage": 10,
                "estimated_cost": 0.01,
                "score": 0.0,
            }
        ],
    )
    output = tmp_path / "reports" / "index.html"
    path = generate_dashboard(search_root=tmp_path, output_path=output)
    html = path.read_text(encoding="utf-8")
    assert path.name == "index.html"
    assert "Experiment Summary" in html
    assert "Total Trials" in html
    assert "Model Comparison Table" in html
    assert "Execution Time by Model" in html
    assert "Token Usage by Model" in html
    assert "Cost by Model" in html
    assert "Score by Model" in html
    assert "Highest Score" in html
    assert "Lowest Cost" in html
    assert "Fastest Model" in html
    assert "model1" in html
    assert "model2" in html
    assert ">2<" in html
    assert ">1<" in html


def test_run_experiment_writes_html_report(tmp_path: Path) -> None:
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

    metrics = tmp_path / "metrics.json"
    report = tmp_path / "reports" / "index.html"
    run_experiment(execute_trial=execute_trial, metrics_path=metrics, report_path=report)
    html = report.read_text(encoding="utf-8")
    assert "model1" in html
    assert "Experiment Ledger" in html
