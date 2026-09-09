from __future__ import annotations

from src.experiments.compiler import ExperimentCompiler
from src.experiments.loader import load_experiment


def test_load_experiment_from_yaml() -> None:
    config = load_experiment()
    assert config.experiment_id == "harbor-openhands-hf"
    assert [task.id for task in config.enabled_tasks()] == ["health-api"]
    assert [agent.id for agent in config.enabled_agents()] == ["openhands"]
    assert [model.id for model in config.enabled_models()] == [
        "model1",
        "model2",
        "model3",
        "model4",
        "model5",
    ]
    assert config.attempts == 1
    task = config.enabled_tasks()[0]
    assert task.path == "datasets/internal-core/health-api"
    assert task.name == "Health API"
    assert [model.hf_id for model in config.enabled_models()] == [
        "google/gemma-7b-it",
        "deepseek-ai/DeepSeek-V3",
        "meta-llama/Llama-3.3-70B-Instruct",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
    ]


def test_compiler_expands_task_agent_model_attempt() -> None:
    trials = ExperimentCompiler().compile()
    assert len(trials) == 5
    assert [trial.model.id for trial in trials] == [
        "model1",
        "model2",
        "model3",
        "model4",
        "model5",
    ]
    assert all(trial.experiment_id == "harbor-openhands-hf" for trial in trials)
    assert all(trial.task.id == "health-api" for trial in trials)
    assert all(trial.agent.id == "openhands" for trial in trials)
    assert all(trial.attempt == 1 for trial in trials)
    assert all(trial.model.hf_id for trial in trials)
    assert all(trial.task.path == "datasets/internal-core/health-api" for trial in trials)
    assert {trial.trial_id for trial in trials} == {
        "harbor-openhands-hf::health-api::openhands::model1::1",
        "harbor-openhands-hf::health-api::openhands::model2::1",
        "harbor-openhands-hf::health-api::openhands::model3::1",
        "harbor-openhands-hf::health-api::openhands::model4::1",
        "harbor-openhands-hf::health-api::openhands::model5::1",
    }
