"""Hit every Hugging Face model in models.yaml to check the API key works."""

from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import InferenceClient
import os
import yaml

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

MODELS_YAML = ROOT / "src" / "experiments" / "models.yaml"


def main() -> None:
    api_key = os.getenv("HF_API_KEY")
    if not api_key:
        raise SystemExit("HF_API_KEY missing from .env")

    models = yaml.safe_load(MODELS_YAML.read_text())["models"]
    client = InferenceClient(token=api_key, timeout=120.0)
    failed: list[str] = []

    for key, spec in models.items():
        hf_id = spec["hf_id"]
        print(f"Calling {key} ({hf_id})...", flush=True)
        try:
            completion = client.chat.completions.create(
                model=hf_id,
                messages=[{"role": "user", "content": "Reply with the single word: pong"}],
                max_tokens=min(int(spec.get("max_new_tokens", 32)), 32),
                temperature=spec.get("temperature", 0.2),
            )
            text = (completion.choices[0].message.content if completion.choices else "") or ""
            if not text.strip():
                print("FAIL: empty response")
                failed.append(key)
                continue
            print("OK:", text.strip()[:200])
        except Exception as exc:
            print(f"FAIL: {exc}")
            failed.append(key)

    if failed:
        raise SystemExit("Failed: " + ", ".join(failed))
    print("All models responded.")


if __name__ == "__main__":
    main()
