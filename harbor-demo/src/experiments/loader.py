from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

import yaml

from src.contracts.config import ExperimentConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EXPERIMENT_PATH = Path(__file__).resolve().parent / "experiment.yaml"
DEFAULT_MODELS_PATH = Path(__file__).resolve().parent / "models.yaml"
DEFAULT_TASKS_ROOT = REPO_ROOT / "datasets" / "internal-core"


def load_experiment(path: str | Path | None = None) -> ExperimentConfig:
    """Load the experiment matrix and resolve task/model IDs to runnable specs."""
    experiment_path = Path(path) if path is not None else DEFAULT_EXPERIMENT_PATH
    if not experiment_path.is_file():
        raise FileNotFoundError(f"Experiment config not found: {experiment_path}")
    payload = yaml.safe_load(experiment_path.read_text(encoding="utf-8")) or {}
    catalog = _load_model_catalog()
    raw_models = payload.get("models") if payload.get("models") is not None else []
    raw_tasks = payload["tasks"] if "tasks" in payload else payload.get("task") or []
    if not isinstance(raw_tasks, list):
        raw_tasks = [raw_tasks]
    payload["models"] = [_resolve_model(item, catalog) for item in raw_models]
    payload["tasks"] = [_resolve_task(item) for item in raw_tasks]
    return ExperimentConfig.model_validate(payload)


def _load_model_catalog(path: Path | None = None) -> dict[str, dict[str, Any]]:
    catalog_path = path or DEFAULT_MODELS_PATH
    if not catalog_path.is_file():
        raise FileNotFoundError(f"Model catalog not found: {catalog_path}")
    payload = yaml.safe_load(catalog_path.read_text(encoding="utf-8")) or {}
    models = payload.get("models") or {}
    if not isinstance(models, dict):
        raise ValueError("models.yaml must define a mapping under 'models'.")
    return models


def _resolve_model(item: Any, catalog: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if isinstance(item, str):
        if item not in catalog:
            raise KeyError(f"Unknown model alias '{item}'. Add it to models.yaml.")
        return {"id": item, **catalog[item]}
    if isinstance(item, dict):
        alias = item.get("id")
        extras = catalog.get(alias, {}) if alias else {}
        return {**extras, **item}
    raise TypeError(f"Unsupported model entry: {item!r}")


def _resolve_task(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        return _task_from_id(item)
    if isinstance(item, dict):
        task_id = item.get("id")
        if not task_id:
            raise ValueError("Task objects must include an 'id'.")
        resolved = _task_from_id(str(task_id))
        return {**resolved, **item}
    raise TypeError(f"Unsupported task entry: {item!r}")


def _task_from_id(task_id: str) -> dict[str, Any]:
    task_dir = DEFAULT_TASKS_ROOT / task_id
    spec: dict[str, Any] = {
        "id": task_id,
        "path": str(task_dir.relative_to(REPO_ROOT).as_posix()),
    }
    toml_path = task_dir / "task.toml"
    if not toml_path.is_file():
        raise FileNotFoundError(f"Task '{task_id}' not found at {task_dir}")
    meta = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    if meta.get("name"):
        spec["name"] = meta["name"]
    return spec
