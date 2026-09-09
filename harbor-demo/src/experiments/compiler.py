from __future__ import annotations

from pathlib import Path

from src.contracts.config import ExperimentConfig
from src.contracts.trials import TrialRequest
from src.experiments.loader import load_experiment


class ExperimentCompiler:
    """Stateless compiler: experiment.yaml (or config) to TrialRequest list."""

    def compile(
        self, source: ExperimentConfig | str | Path | None = None
    ) -> list[TrialRequest]:
        config = source if isinstance(source, ExperimentConfig) else load_experiment(source)
        return self._expand(config)

    def _expand(self, config: ExperimentConfig) -> list[TrialRequest]:
        trials: list[TrialRequest] = []
        for task in config.enabled_tasks():
            for agent in config.enabled_agents():
                for model in config.enabled_models():
                    for attempt in range(1, config.attempts + 1):
                        trials.append(
                            TrialRequest(
                                trial_id=_trial_id(
                                    experiment_id=config.experiment_id,
                                    task_id=task.id,
                                    agent_id=agent.id,
                                    model_id=model.id,
                                    attempt=attempt,
                                ),
                                experiment_id=config.experiment_id,
                                task=task,
                                agent=agent,
                                model=model,
                                attempt=attempt,
                                provider=config.provider,
                            )
                        )
        return trials


def _trial_id(
    *,
    experiment_id: str,
    task_id: str,
    agent_id: str,
    model_id: str,
    attempt: int,
) -> str:
    return f"{experiment_id}::{task_id}::{agent_id}::{model_id}::{attempt}"
