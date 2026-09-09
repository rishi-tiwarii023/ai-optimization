from __future__ import annotations

from pathlib import Path

import yaml

from src.contracts.config import ExperimentConfig

DEFAULT_EXPERIMENT_PATH = Path(__file__).resolve().parent / "experiment.yaml"


def load_experiment(path: str | Path | None = None) -> ExperimentConfig:
    """Load experiment matrix and provider settings from YAML."""
    experiment_path = Path(path) if path is not None else DEFAULT_EXPERIMENT_PATH
    if not experiment_path.is_file():
        raise FileNotFoundError(f"Experiment config not found: {experiment_path}")
    payload = yaml.safe_load(experiment_path.read_text(encoding="utf-8")) or {}
    return ExperimentConfig.model_validate(payload)
