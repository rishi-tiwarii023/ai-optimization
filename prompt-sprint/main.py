import argparse
import json
import os
import re
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone

import litellm
from dotenv import load_dotenv

PROVIDERS = {
    "openrouter": {"key_env": "OPENROUTER_API_KEY", "prefix": "openrouter/", "base_env": "OPENROUTER_API_BASE"},
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


def validate_config(config, enforce_available_models=True):
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

    available_models = config.get("available_models")
    if available_models is not None and enforce_available_models:
        if not isinstance(available_models, list) or not available_models:
            fail('Invalid "available_models": expected a non-empty JSON array of model ids.')
        for index, candidate in enumerate(available_models, start=1):
            if not isinstance(candidate, str) or not candidate.strip():
                fail(f'Invalid "available_models" item at index {index}: expected a non-empty string.')
            candidate = candidate.strip()
            if not candidate.startswith(prefix):
                fail(
                    f'Model {candidate!r} in available_models does not start with expected '
                    f'prefix {prefix!r} for provider "{provider_name}".'
                )
            available_models[index - 1] = candidate
        if model not in available_models:
            fail(
                f'Model {model!r} is not in available_models. '
                "Set \"model\" to one of the listed OpenRouter ids."
            )
        config["available_models"] = available_models

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


def save_json(path, payload, responses_dir=RESPONSES_DIR, prefix=".tmp."):
    fd, tmp_path = tempfile.mkstemp(dir=responses_dir, prefix=prefix, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def save_result(result, responses_dir=RESPONSES_DIR):
    path = result_path(result["task_id"], responses_dir)
    save_json(path, result, responses_dir, prefix=f'.{result["task_id"]}.')


def save_summary(summary, responses_dir=RESPONSES_DIR):
    path = os.path.join(responses_dir, "summary.json")
    save_json(path, summary, responses_dir, prefix=".summary.")


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


def format_elapsed(elapsed_ms):
    seconds = elapsed_ms / 1000
    if seconds < 60:
        return f"{seconds:.2f} s"
    minutes, seconds = divmod(seconds, 60)
    return f"{int(minutes)} m {seconds:.2f} s"


def average_latency_ms(stats):
    api_calls = stats["successful"] + stats["failed"]
    if not api_calls:
        return 0
    return round(stats["latency_sum_ms"] / api_calls)


def reported_cost_value(stats):
    if stats["cost_available_for_calls"] == 0:
        return None
    return stats["reported_cost"]


def build_summary(config, stats, run_id, started_at, finished_at):
    return {
        "run_id": run_id,
        "provider": config["provider"],
        "model": config["model"],
        "started_at": started_at,
        "finished_at": finished_at,
        "total_tasks": stats["total_tasks"],
        "successful": stats["successful"],
        "failed": stats["failed"],
        "skipped": stats["skipped"],
        "prompt_tokens": stats["prompt_tokens"],
        "completion_tokens": stats["completion_tokens"],
        "total_tokens": stats["total_tokens"],
        "reported_cost": reported_cost_value(stats),
        "cost_available_for_calls": stats["cost_available_for_calls"],
        "cost_unavailable_for_calls": stats["cost_unavailable_for_calls"],
        "total_elapsed_ms": stats["total_elapsed_ms"],
        "average_latency_ms": average_latency_ms(stats),
    }


def print_summary(config, stats):
    average_latency = average_latency_ms(stats)

    cost_available = stats["cost_available_for_calls"]
    cost_unavailable = stats["cost_unavailable_for_calls"]
    if cost_available == 0:
        reported_cost = "unavailable"
        if cost_unavailable:
            reported_cost = f"unavailable for {cost_unavailable} calls"
    elif cost_unavailable:
        reported_cost = (
            f'{stats["reported_cost"]} across {cost_available} calls; '
            f"unavailable for {cost_unavailable} calls"
        )
    else:
        reported_cost = str(stats["reported_cost"])

    print()
    print("PromptRun Summary")
    print("-----------------")
    print(f'Provider: {config["provider"]}')
    print(f'Model: {config["model"]}')
    print(f'Total tasks: {stats["total_tasks"]}')
    print(f'Successful: {stats["successful"]}')
    print(f'Failed: {stats["failed"]}')
    print(f'Skipped: {stats["skipped"]}')
    print(f'Prompt tokens: {stats["prompt_tokens"]}')
    print(f'Completion tokens: {stats["completion_tokens"]}')
    print(f'Total tokens: {stats["total_tokens"]}')
    print(f"Reported cost: {reported_cost}")
    print(f'Total elapsed: {format_elapsed(stats["total_elapsed_ms"])}')
    print(f"Average latency: {average_latency} ms")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="PromptSprint")
    parser.add_argument("--tasks", default="tasks.json")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output", default="responses")
    parser.add_argument("--task-id")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    load_dotenv()
    config = load_config(args.config)
    if args.provider:
        config["provider"] = args.provider
    if args.model:
        config["model"] = args.model
    config = validate_config(
        config,
        enforce_available_models=not (args.provider or args.model),
    )
    if args.overwrite:
        config["overwrite_existing"] = True

    call_kwargs = build_call_kwargs(config)
    tasks = load_tasks(args.tasks)
    if args.task_id:
        match = [task for task in tasks if task["task_id"] == args.task_id]
        if not match:
            fail(f'task_id {args.task_id!r} was not found in {args.tasks}.')
        tasks = match

    responses_dir = ensure_responses_dir(args.output)
    print(f'Provider: {config["provider"]} | Model: {config["model"]}')

    run_id = str(uuid.uuid4())
    started_at = utc_now()
    total = len(tasks)
    stats = {
        "total_tasks": total,
        "successful": 0,
        "failed": 0,
        "skipped": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reported_cost": 0.0,
        "cost_available_for_calls": 0,
        "cost_unavailable_for_calls": 0,
        "latency_sum_ms": 0,
        "total_elapsed_ms": 0,
    }
    run_started = time.perf_counter()
    for index, task in enumerate(tasks, start=1):
        prefix = f'[{index}/{total}] {task["task_id"]}'
        if not config["overwrite_existing"] and result_exists(task["task_id"], responses_dir):
            stats["skipped"] += 1
            print(f"{prefix} SKIPPED")
            continue

        print(f"{prefix} RUNNING")
        result = run_task(task, config, call_kwargs)
        save_result(result, responses_dir)
        metrics = result["metrics"]
        stats["latency_sum_ms"] += metrics["latency_ms"]
        stats["prompt_tokens"] += metrics["prompt_tokens"]
        stats["completion_tokens"] += metrics["completion_tokens"]
        stats["total_tokens"] += metrics["total_tokens"]
        if metrics["cost"] is None:
            stats["cost_unavailable_for_calls"] += 1
        else:
            stats["cost_available_for_calls"] += 1
            stats["reported_cost"] += metrics["cost"]

        if result["status"] == "failed":
            stats["failed"] += 1
            print(f'{prefix} FAILED | error={result["error"]["type"]}')
            if not config["continue_on_error"]:
                break
        else:
            stats["successful"] += 1
            print(
                f'{prefix} SUCCESS | tokens={metrics["total_tokens"]} | '
                f'latency={metrics["latency_ms"]} ms'
            )

    stats["total_elapsed_ms"] = round((time.perf_counter() - run_started) * 1000)
    save_summary(build_summary(config, stats, run_id, started_at, utc_now()), responses_dir)
    print_summary(config, stats)
    if stats["failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
