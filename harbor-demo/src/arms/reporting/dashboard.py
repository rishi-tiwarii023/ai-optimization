from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.experiments.loader import REPO_ROOT

_TEMPLATE_DIR = REPO_ROOT / "templates"
_DEFAULT_OUTPUT = REPO_ROOT / "reports" / "index.html"


def generate_dashboard(
    *,
    search_root: Path | None = None,
    output_path: Path | None = None,
    metrics_files: list[Path] | None = None,
) -> Path:
    """Load every metrics.json under search_root and write reports/index.html."""

    root = Path(search_root) if search_root is not None else REPO_ROOT
    files = metrics_files if metrics_files is not None else _find_metrics_files(root)
    frame = _load_trials(files)
    context = _dashboard_context(frame, files)
    html = _render(context)
    dest = Path(output_path) if output_path is not None else _DEFAULT_OUTPUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    return dest


def _find_metrics_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return sorted(path for path in root.rglob("metrics.json") if path.is_file())


def _load_trials(files: list[Path]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for path in files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        trials = payload.get("trials") or []
        for trial in trials:
            rows.append(
                {
                    "source": str(path),
                    "model_name": trial.get("model_name", "unknown"),
                    "status": trial.get("status", "error"),
                    "build_passed": bool(trial.get("build_passed", False)),
                    "tests_passed": int(trial.get("tests_passed") or 0),
                    "test_count": int(trial.get("test_count") or 0),
                    "execution_time": trial.get("execution_time"),
                    "token_usage": int(trial.get("token_usage") or 0),
                    "estimated_cost": float(trial.get("estimated_cost") or 0.0),
                    "score": float(trial.get("score") or 0.0),
                }
            )
    if not rows:
        return pd.DataFrame(
            columns=[
                "source",
                "model_name",
                "status",
                "build_passed",
                "tests_passed",
                "test_count",
                "execution_time",
                "token_usage",
                "estimated_cost",
                "score",
            ]
        )
    return pd.DataFrame(rows)


def _dashboard_context(frame: pd.DataFrame, files: list[Path]) -> dict[str, Any]:
    total = int(len(frame))
    if total == 0:
        passed = 0
        failed = 0
    else:
        passed = int((frame["score"] >= 1.0).sum())
        failed = total - passed

    comparison = _comparison_rows(frame)
    charts = _charts(comparison)
    ranking = _ranking(comparison)
    return {
        "source_count": len(files),
        "summary": {
            "total_trials": total,
            "passed": passed,
            "failed": failed,
        },
        "comparison": comparison,
        "charts": charts,
        "ranking": ranking,
    }


def _comparison_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []

    grouped = frame.groupby("model_name", sort=True)
    rows: list[dict[str, Any]] = []
    for name, group in grouped:
        times = group["execution_time"].dropna()
        statuses = group["status"].tolist()
        status = statuses[-1] if statuses else "error"
        if any(item != statuses[0] for item in statuses[1:]):
            status = "mixed"
        test_count = int(group["test_count"].sum())
        tests_passed = int(group["tests_passed"].sum())
        rows.append(
            {
                "model": str(name),
                "status": status,
                "build": "Pass" if bool(group["build_passed"].all()) else "Fail",
                "build_passed": bool(group["build_passed"].all()),
                "tests": f"{tests_passed}/{test_count}",
                "tests_passed": tests_passed,
                "test_count": test_count,
                "execution_time": float(times.sum()) if not times.empty else None,
                "token_usage": int(group["token_usage"].sum()),
                "estimated_cost": float(group["estimated_cost"].sum()),
                "score": float(group["score"].mean()),
            }
        )
    rows.sort(key=lambda item: (-item["score"], item["model"]))
    return rows


def _charts(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "execution_time": _bar_series(rows, "execution_time"),
        "token_usage": _bar_series(rows, "token_usage"),
        "cost": _bar_series(rows, "estimated_cost"),
        "score": _bar_series(rows, "score", floor=1.0),
    }


def _bar_series(
    rows: list[dict[str, Any]],
    key: str,
    *,
    floor: float | None = None,
) -> list[dict[str, Any]]:
    values: list[float] = []
    for row in rows:
        raw = row.get(key)
        values.append(0.0 if raw is None else float(raw))
    peak = max(values) if values else 0.0
    if floor is not None:
        peak = max(peak, floor)
    series: list[dict[str, Any]] = []
    for row, value in zip(rows, values, strict=True):
        pct = 0.0 if peak <= 0 else round((value / peak) * 100.0, 2)
        series.append({"model": row["model"], "value": value, "pct": pct})
    return series


def _ranking(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any] | None]:
    if not rows:
        return {"highest_score": None, "lowest_cost": None, "fastest": None}

    highest = max(rows, key=lambda item: (item["score"], -_time_or_inf(item)))
    lowest_cost = min(rows, key=lambda item: (item["estimated_cost"], -item["score"], item["model"]))
    timed = [item for item in rows if item["execution_time"] is not None]
    fastest = min(timed, key=lambda item: (item["execution_time"], -item["score"])) if timed else None
    return {
        "highest_score": highest,
        "lowest_cost": lowest_cost,
        "fastest": fastest,
    }


def _time_or_inf(row: dict[str, Any]) -> float:
    value = row.get("execution_time")
    return float("inf") if value is None else float(value)


def _render(context: dict[str, Any]) -> str:
    env = Environment(
        loader=FileSystemLoader(_TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.filters["fmt_time"] = _fmt_time
    env.filters["fmt_cost"] = _fmt_cost
    env.filters["fmt_score"] = _fmt_score
    env.filters["fmt_int"] = _fmt_int
    template = env.get_template("report.html")
    return template.render(**context)


def _fmt_time(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}s"


def _fmt_cost(value: float | None) -> str:
    if value is None:
        return "—"
    return f"${value:.4f}"


def _fmt_score(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.3f}"


def _fmt_int(value: int | float | None) -> str:
    if value is None:
        return "—"
    return f"{int(value):,}"
