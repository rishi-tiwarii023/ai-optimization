"""Ping the configured model. Prints no credentials."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from main import build_call_kwargs, load_config, run_task, validate_config


def main():
    load_dotenv(ROOT / ".env")
    config = validate_config(load_config(ROOT / "config.json"))
    call_kwargs = build_call_kwargs(config)
    print(f'Provider: {config["provider"]} | Model: {config["model"]}')
    result = run_task(
        {"task_id": "connection", "prompt": "Reply with the single word OK."},
        config,
        call_kwargs,
    )
    if result["status"] == "failed":
        error = result["error"]
        print(f'FAILED | {error["type"]}: {error["message"]}', file=sys.stderr)
        sys.exit(1)
    print(f'SUCCESS | reply={result["response"].strip()!r}')


if __name__ == "__main__":
    main()
