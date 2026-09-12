import argparse
import os

from dotenv import load_dotenv

from main import (
    RESPONSES_DIR,
    build_call_kwargs,
    fail,
    load_config,
    load_json,
    save_json,
    save_result,
    validate_config,
)
from scorer import score_response
from stats import compute_score_stats


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Score PromptSprint responses")
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--output", default=RESPONSES_DIR)
    parser.add_argument("--task-id")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--provider")
    parser.add_argument("--model")
    return parser.parse_args(argv)


def list_result_paths(responses_dir, task_id=None):
    if not os.path.isdir(responses_dir):
        fail(f"Missing directory: {responses_dir}")
    if task_id:
        path = os.path.join(responses_dir, f"{task_id}.json")
        if not os.path.exists(path):
            fail(f"Missing file: {path}")
        return [path]
    paths = []
    for name in sorted(os.listdir(responses_dir)):
        if name == "summary.json" or not name.endswith(".json") or name.startswith("."):
            continue
        paths.append(os.path.join(responses_dir, name))
    return paths


def collect_scores(paths):
    scores = []
    for path in paths:
        payload = load_json(path)
        if not isinstance(payload, dict):
            continue
        score = payload.get("score")
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            scores.append(float(score))
    return scores


def update_summary(responses_dir, scores):
    path = os.path.join(responses_dir, "summary.json")
    if os.path.exists(path):
        summary = load_json(path)
        if not isinstance(summary, dict):
            fail(f"Invalid JSON in {path}: expected a JSON object.")
    else:
        summary = {}
    summary["score_stats"] = compute_score_stats(scores)
    save_json(path, summary, responses_dir, prefix=".summary.")


def main(argv=None):
    args = parse_args(argv)
    load_dotenv()
    config = load_config(args.config)
    if args.provider:
        config["provider"] = args.provider
    if args.model:
        config["model"] = args.model
        config["judge_model"] = args.model
    config = validate_config(
        config,
        enforce_available_models=not (args.provider or args.model),
    )
    call_kwargs = build_call_kwargs(config)
    paths = list_result_paths(args.output, args.task_id)
    if not paths:
        fail(f"No task result files found in {args.output}.")

    total = len(paths)
    scored = 0
    skipped = 0
    failed = 0
    for index, path in enumerate(paths, start=1):
        payload = load_json(path)
        task_id = os.path.splitext(os.path.basename(path))[0]
        prefix = f"[{index}/{total}] {task_id}"
        if not isinstance(payload, dict):
            skipped += 1
            print(f"{prefix} SKIPPED | invalid result file")
            continue
        if payload.get("status") != "success":
            skipped += 1
            print(f"{prefix} SKIPPED | status={payload.get('status')}")
            continue
        existing = payload.get("score")
        has_score = isinstance(existing, (int, float)) and not isinstance(existing, bool)
        if has_score and not args.overwrite:
            skipped += 1
            print(f"{prefix} SKIPPED | score={existing}")
            continue

        print(f"{prefix} SCORING")
        score = score_response(
            payload.get("prompt", ""),
            payload.get("response") or "",
            config,
            call_kwargs,
        )
        payload["score"] = score
        save_result(payload, args.output)
        if score is None:
            failed += 1
            print(f"{prefix} FAILED | could not parse score")
        else:
            scored += 1
            print(f"{prefix} SUCCESS | score={score}")

    all_paths = list_result_paths(args.output)
    scores = collect_scores(all_paths)
    update_summary(args.output, scores)
    print()
    print(f"Scored: {scored}")
    print(f"Skipped: {skipped}")
    print(f"Failed: {failed}")
    stats = compute_score_stats(scores)
    if not stats:
        print("Score stats: unavailable")
    else:
        print(
            "Score stats: "
            f'mean={stats["mean"]} median={stats["median"]} '
            f'mode={stats["mode"]} max={stats["max"]} '
            f'median_range={stats["median_range"]} p95={stats["p95"]} '
            f'std_dev={stats["std_dev"]}'
        )


if __name__ == "__main__":
    main()
