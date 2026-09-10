"""Hit every model in models.yaml through local LiteLLM/Laguna via the HTTP proxy."""

from pathlib import Path

from dotenv import load_dotenv
import json
import os
import urllib.error
import urllib.request
import yaml

from src.adapters.http_proxy import build_forced_proxy_opener

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

MODELS_YAML = ROOT / "src" / "experiments" / "models.yaml"


def main() -> None:
    api_key = os.getenv("LAGUNA_API_KEY") or ""
    endpoint = (os.getenv("LAGUNA_API_ENDPOINT") or "").rstrip("/")
    proxy = (os.getenv("LAGUNA_PROXY_URL") or "").strip()
    if not endpoint:
        raise SystemExit("LAGUNA_API_ENDPOINT missing from .env")

    models = yaml.safe_load(MODELS_YAML.read_text())["models"]
    opener = build_forced_proxy_opener(proxy)
    failed: list[str] = []

    for key, spec in models.items():
        model_id = spec["hf_id"]
        print(f"Calling {key} ({model_id})...", flush=True)
        payload = {
            "model": model_id,
            "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
            "max_tokens": min(int(spec.get("max_new_tokens", 32)), 32),
            "temperature": spec.get("temperature", 0.2),
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        request = urllib.request.Request(
            f"{endpoint}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with opener.open(request, timeout=120.0) as response:
                body = json.loads(response.read().decode("utf-8"))
            choices = body.get("choices") or []
            message = choices[0].get("message") if choices else {}
            text = (message or {}).get("content") or ""
            if not text.strip():
                print("FAIL: empty response")
                failed.append(key)
                continue
            print("OK:", text.strip()[:200])
        except urllib.error.HTTPError as exc:
            print(f"FAIL: HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}")
            failed.append(key)
        except Exception as exc:
            print(f"FAIL: {exc}")
            failed.append(key)

    if failed:
        raise SystemExit("Failed: " + ", ".join(failed))
    print("All models responded.")


if __name__ == "__main__":
    main()
