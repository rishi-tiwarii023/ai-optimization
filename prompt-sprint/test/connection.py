"""Ping the configured Laguna model through LiteLLM. Prints no credentials."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import litellm
from dotenv import load_dotenv

from main import build_call_kwargs, extract_text, load_config, validate_config


def main():
    load_dotenv(ROOT / ".env")
    config = validate_config(load_config(ROOT / "config.json"))
    call_kwargs = build_call_kwargs(config)

    print(f'Provider: {config["provider"]} | Model: {config["model"]}')
    try:
        response = litellm.completion(
            model=config["model"],
            messages=[{"role": "user", "content": "Reply with the single word OK."}],
            temperature=0,
            max_tokens=16,
            timeout=config["timeout_seconds"],
            stream=False,
            **call_kwargs,
            **config["extra_params"],
        )
    except Exception as exc:
        print(f"FAILED | {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)

    text = extract_text(response).strip()
    print(f"SUCCESS | reply={text!r}")


if __name__ == "__main__":
    main()
