"""Hit every model in models.yaml through the configured provider."""

from pathlib import Path

import yaml
from dotenv import load_dotenv

from src.adapters.models.factory import create_model_provider
from src.contracts.config import ExperimentConfig

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

EXPERIMENT_YAML = ROOT / "src" / "experiments" / "experiment.yaml"
MODELS_YAML = ROOT / "src" / "experiments" / "models.yaml"


def _load_experiment_config() -> ExperimentConfig:
    experiment_data = yaml.safe_load(EXPERIMENT_YAML.read_text())
    models_by_key = yaml.safe_load(MODELS_YAML.read_text())["models"]
    experiment_data["models"] = [
        {"id": key, **models_by_key[key]} for key in experiment_data["models"]
    ]
    return ExperimentConfig(**experiment_data)


def main() -> None:
    experiment_config = _load_experiment_config()
    provider = create_model_provider(experiment_config)
    failed: list[str] = []

    for model in experiment_config.enabled_models():
        print(f"Calling {model.id} ({model.inference_id})...", flush=True)
        response = provider.generate("Reply with the single word: pong", model)
        if response.error is not None:
            print(f"FAIL: {response.error}")
            failed.append(model.id)
            continue
        if not (response.output or "").strip():
            print("FAIL: empty response")
            failed.append(model.id)
            continue
        print("OK:", response.output.strip()[:200])

    if failed:
        raise SystemExit("Failed: " + ", ".join(failed))
    print("All models responded.")


if __name__ == "__main__":
    main()