import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime, timezone

import litellm
from dotenv import load_dotenv

PROVIDERS = {
    "openrouter": {"key_env": "OPENROUTER_API_KEY", "prefix": "openrouter/", "base_env": None},
    "openai":     {"key_env": "OPENAI_API_KEY",     "prefix": "openai/",     "base_env": None},
    "anthropic":  {"key_env": "ANTHROPIC_API_KEY",  "prefix": "anthropic/",  "base_env": None},
    "gemini":     {"key_env": "GEMINI_API_KEY",     "prefix": "gemini/",     "base_env": None},
    "laguna":     {"key_env": "LAGUNA_API_KEY",     "prefix": "openai/",     "base_env": "LAGUNA_API_BASE"},
}


def fail(message):
    print(message, file=sys.stderr)
    sys.exit(1)


def load_config(path="config.json"):
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
    except FileNotFoundError:
        fail(f"Missing configuration file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path}: {exc}")

    if not isinstance(config, dict):
        fail(f"{path} must contain a JSON object.")
    return config


def require_string(config, key):
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        fail(f'Invalid or missing "{key}": expected a non-empty string.')
    return value.strip()


def require_number(config, key, integer=False):
    value = config.get(key)
    if integer:
        if isinstance(value, bool) or not isinstance(value, int):
            fail(f'Invalid or missing "{key}": expected an integer.')
    else:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            fail(f'Invalid or missing "{key}": expected a number.')
    return value


def require_bool(config, key):
    value = config.get(key)
    if not isinstance(value, bool):
        fail(f'Invalid or missing "{key}": expected a boolean.')
    return value


def validate_config(config):
    provider_name = require_string(config, "provider")
    if provider_name not in PROVIDERS:
        supported = ", ".join(PROVIDERS)
        fail(f'Unknown provider {provider_name!r}. Supported providers: {supported}.')

    model = require_string(config, "model")
    prefix = PROVIDERS[provider_name]["prefix"]
    if not model.startswith(prefix):
        fail(
            f'Model {model!r} does not start with expected prefix {prefix!r} '
            f'for provider "{provider_name}".'
        )

    require_number(config, "temperature")
    require_number(config, "max_tokens", integer=True)
    require_number(config, "timeout_seconds", integer=True)
    require_bool(config, "continue_on_error")
    require_bool(config, "overwrite_existing")

    extra_params = config.get("extra_params", {})
    if extra_params is None:
        extra_params = {}
    if not isinstance(extra_params, dict):
        fail('Invalid "extra_params": expected a JSON object.')
    config["extra_params"] = extra_params
    return config


def build_call_kwargs(config):
    provider_name = config["provider"]
    spec = PROVIDERS[provider_name]
    key_env = spec["key_env"]
    api_key = os.getenv(key_env)
    if not api_key:
        fail(f'Missing {key_env}. Set it in .env for provider "{provider_name}".')

    call_kwargs = {"api_key": api_key}
    base_env = spec["base_env"]
    if base_env:
        api_base = os.getenv(base_env)
        if not api_base:
            fail(f'Missing {base_env}. Set it in .env for provider "{provider_name}".')
        call_kwargs["api_base"] = api_base
    return call_kwargs


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def extract_text(response):
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        return ""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and item.get("text"):
                parts.append(str(item["text"]))
        return "".join(parts)
    return str(content)


def extract_usage(response):
    usage = getattr(response, "usage", None)
    prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0) if usage is not None else 0
    completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0) if usage is not None else 0
    total_tokens = int(getattr(usage, "total_tokens", 0) or 0) if usage is not None else 0
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens
    return prompt_tokens, completion_tokens, total_tokens


def extract_cost(response):
    hidden = getattr(response, "_hidden_params", None)
    if not isinstance(hidden, dict):
        return None
    cost = hidden.get("response_cost")
    if cost is None:
        return None
    try:
        return float(cost)
    except (TypeError, ValueError):
        return None


def sanitise_error_message(message, call_kwargs):
    text = str(message)
    for value in call_kwargs.values():
        if value:
            text = text.replace(str(value), "[redacted]")
    return text


def empty_metrics(latency_ms):
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "latency_ms": latency_ms,
        "cost": None,
    }


def run_task(task, config, call_kwargs):
    started_at = utc_now()
    started = time.perf_counter()
    try:
        response = litellm.completion(
            model=config["model"],
            messages=[{"role": "user", "content": task["prompt"]}],
            temperature=config["temperature"],
            max_tokens=config["max_tokens"],
            timeout=config["timeout_seconds"],
            stream=False,
            **call_kwargs,
            **config["extra_params"],
        )
        latency_ms = round((time.perf_counter() - started) * 1000)
        prompt_tokens, completion_tokens, total_tokens = extract_usage(response)
        return {
            "task_id": task["task_id"],
            "model": config["model"],
            "status": "success",
            "prompt": task["prompt"],
            "response": extract_text(response),
            "metrics": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": total_tokens,
                "latency_ms": latency_ms,
                "cost": extract_cost(response),
            },
            "error": None,
            "started_at": started_at,
            "finished_at": utc_now(),
        }
    except Exception as exc:
        latency_ms = round((time.perf_counter() - started) * 1000)
        return {
            "task_id": task["task_id"],
            "model": config["model"],
            "status": "failed",
            "prompt": task["prompt"],
            "response": None,
            "metrics": empty_metrics(latency_ms),
            "error": {
                "type": type(exc).__name__,
                "message": sanitise_error_message(exc, call_kwargs),
            },
            "started_at": started_at,
            "finished_at": utc_now(),
        }


RESPONSES_DIR = "responses"


def ensure_responses_dir(path=RESPONSES_DIR):
    os.makedirs(path, exist_ok=True)
    return path


def result_path(task_id, responses_dir=RESPONSES_DIR):
    return os.path.join(responses_dir, f"{task_id}.json")


def result_exists(task_id, responses_dir=RESPONSES_DIR):
    return os.path.exists(result_path(task_id, responses_dir))


def save_result(result, responses_dir=RESPONSES_DIR):
    path = result_path(result["task_id"], responses_dir)
    fd, tmp_path = tempfile.mkstemp(
        dir=responses_dir, prefix=f'.{result["task_id"]}.', suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


TASK_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def load_tasks(path="tasks.json"):
    try:
        with open(path, encoding="utf-8") as f:
            tasks = json.load(f)
    except FileNotFoundError:
        fail(f"Missing tasks file: {path}")
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {path}: {exc}")

    if not isinstance(tasks, list):
        fail(f"{path} must contain a JSON array of tasks.")
    if not tasks:
        fail(f"{path} must contain at least one task.")

    seen_ids = set()
    validated = []
    for index, task in enumerate(tasks, start=1):
        location = f"task at index {index}"
        if not isinstance(task, dict):
            fail(f"Invalid {location}: expected a JSON object.")

        task_id = task.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            fail(f'Invalid {location}: "task_id" must be a non-empty string.')
        task_id = task_id.strip()
        location = f'task "{task_id}" (index {index})'

        if not TASK_ID_PATTERN.fullmatch(task_id):
            fail(
                f'Invalid {location}: "task_id" may contain only letters, '
                "numbers, underscores and hyphens."
            )
        if task_id in seen_ids:
            fail(f"Invalid {location}: duplicate task_id.")
        seen_ids.add(task_id)

        prompt = task.get("prompt")
        if not isinstance(prompt, str) or not prompt.strip():
            fail(f'Invalid {location}: "prompt" must be a non-empty string.')

        validated.append({"task_id": task_id, "prompt": prompt.strip()})

    return validated


def main():
    load_dotenv()
    config = validate_config(load_config())
    call_kwargs = build_call_kwargs(config)
    tasks = load_tasks()
    responses_dir = ensure_responses_dir()
    print(f'Provider: {config["provider"]} | Model: {config["model"]}')

    total = len(tasks)
    any_failed = False
    for index, task in enumerate(tasks, start=1):
        prefix = f'[{index}/{total}] {task["task_id"]}'
        if not config["overwrite_existing"] and result_exists(task["task_id"], responses_dir):
            print(f"{prefix} SKIPPED")
            continue

        print(f"{prefix} RUNNING")
        result = run_task(task, config, call_kwargs)
        save_result(result, responses_dir)
        if result["status"] == "failed":
            any_failed = True
            print(f'{prefix} FAILED | error={result["error"]["type"]}')
            if not config["continue_on_error"]:
                break
        else:
            metrics = result["metrics"]
            print(
                f'{prefix} SUCCESS | tokens={metrics["total_tokens"]} | '
                f'latency={metrics["latency_ms"]} ms'
            )

    if any_failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
