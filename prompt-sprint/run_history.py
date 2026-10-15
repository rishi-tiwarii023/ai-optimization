import json
import os
import uuid
from datetime import datetime, timedelta, timezone

from stats import compute_score_stats

RUNS_DIRNAME = "runs"
INDEX_FILENAME = "index.json"


def _ist_timezone():
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo("Asia/Kolkata")
    except Exception:
        return timezone(timedelta(hours=5, minutes=30))


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def to_ist_display(utc_iso):
    if not utc_iso:
        return None
    normalized = utc_iso.replace("Z", "+00:00")
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(_ist_timezone()).strftime("%Y-%m-%d %H:%M:%S IST")


def now_ist_display():
    return to_ist_display(utc_now())


def runs_dir(responses_dir):
    return os.path.join(responses_dir, RUNS_DIRNAME)


def index_path(responses_dir):
    return os.path.join(runs_dir(responses_dir), INDEX_FILENAME)


def run_path(responses_dir, run_id):
    return os.path.join(runs_dir(responses_dir), f"{run_id}.json")


def task_stat_row(payload):
    if not isinstance(payload, dict):
        return None
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    return {
        "task_id": payload.get("task_id"),
        "status": payload.get("status"),
        "score": payload.get("score"),
        "model": payload.get("model"),
        "total_tokens": metrics.get("total_tokens"),
        "latency_ms": metrics.get("latency_ms"),
        "cost": metrics.get("cost"),
    }


def collect_task_stats(responses_dir):
    if not os.path.isdir(responses_dir):
        return []
    rows = []
    for name in sorted(os.listdir(responses_dir)):
        if name == "summary.json" or not name.endswith(".json") or name.startswith("."):
            continue
        path = os.path.join(responses_dir, name)
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        row = task_stat_row(payload)
        if row and row.get("task_id"):
            rows.append(row)
    return rows


def _load_index(responses_dir):
    path = index_path(responses_dir)
    if not os.path.exists(path):
        return {"runs": []}
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return {"runs": []}
    runs = data.get("runs")
    if not isinstance(runs, list):
        return {"runs": []}
    return data


def score_stats_from_tasks(tasks):
    scores = []
    for row in tasks or []:
        score = row.get("score") if isinstance(row, dict) else None
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            scores.append(float(score))
    return compute_score_stats(scores)


def score_stats_for_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        return None
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    stats = summary.get("score_stats")
    if stats is not None:
        return stats
    return score_stats_from_tasks(snapshot.get("tasks"))


def _index_entry(snapshot):
    summary = snapshot.get("summary") if isinstance(snapshot.get("summary"), dict) else {}
    captured_at = snapshot.get("captured_at")
    captured_at_ist = snapshot.get("captured_at_ist") or to_ist_display(captured_at)
    return {
        "run_id": snapshot.get("run_id"),
        "kind": snapshot.get("kind"),
        "captured_at": captured_at,
        "captured_at_ist": captured_at_ist,
        "started_at": summary.get("started_at"),
        "finished_at": summary.get("finished_at"),
        "provider": summary.get("provider"),
        "model": summary.get("model"),
        "total_tasks": summary.get("total_tasks"),
        "successful": summary.get("successful"),
        "failed": summary.get("failed"),
        "skipped": summary.get("skipped"),
        "score_stats": score_stats_for_snapshot(snapshot),
    }


def save_run_snapshot(snapshot, responses_dir, save_json):
    os.makedirs(runs_dir(responses_dir), exist_ok=True)
    run_id = snapshot["run_id"]
    index = _load_index(responses_dir)
    save_json(run_path(responses_dir, run_id), snapshot, responses_dir, prefix=f".run-{run_id}.")
    runs = [entry for entry in index.get("runs", []) if entry.get("run_id") != run_id]
    runs.insert(0, _index_entry(snapshot))
    index["runs"] = runs
    save_json(index_path(responses_dir), index, responses_dir, prefix=".runs-index.")


def build_snapshot(summary, tasks, kind, run_id=None, captured_at=None):
    run_id = run_id or str(uuid.uuid4())
    captured_at = captured_at or utc_now()
    summary_copy = dict(summary) if isinstance(summary, dict) else {}
    summary_copy["score_stats"] = score_stats_from_tasks(tasks)
    summary_copy.setdefault("run_id", run_id)
    if not summary_copy.get("model") and tasks:
        first = tasks[0] if isinstance(tasks[0], dict) else {}
        task_model = first.get("model")
        if task_model:
            summary_copy["model"] = task_model
    return {
        "run_id": run_id,
        "kind": kind,
        "captured_at": captured_at,
        "captured_at_ist": to_ist_display(captured_at),
        "summary": summary_copy,
        "tasks": tasks,
    }


def record_run_snapshot(responses_dir, kind, summary, save_json, run_id=None):
    tasks = collect_task_stats(responses_dir)
    snapshot = build_snapshot(summary, tasks, kind, run_id=run_id)
    save_run_snapshot(snapshot, responses_dir, save_json)
    return snapshot


def _count_scored_tasks(tasks):
    scored = 0
    for row in tasks or []:
        score = row.get("score") if isinstance(row, dict) else None
        if isinstance(score, (int, float)) and not isinstance(score, bool):
            scored += 1
    return scored


def stats_refresh_message(score_stats, tasks):
    total = len(tasks or [])
    scored = _count_scored_tasks(tasks)
    if score_stats:
        return f"Score stats updated from {scored} of {total} task(s)."
    if total == 0:
        return "No task results found. Run tasks first."
    return (
        "No scores in task results. Run with scoring enabled, or click Score "
        "after you have successful responses."
    )


def refresh_stats_snapshot(responses_dir, load_json, save_json):
    tasks = collect_task_stats(responses_dir)
    score_stats = score_stats_from_tasks(tasks)
    summary_path = os.path.join(responses_dir, "summary.json")
    if os.path.exists(summary_path):
        summary = load_json(summary_path)
        if not isinstance(summary, dict):
            summary = {}
    else:
        summary = {}
    summary["score_stats"] = score_stats
    save_json(summary_path, summary, responses_dir, prefix=".summary.")
    snapshot = build_snapshot(summary, tasks, "stats")
    save_run_snapshot(snapshot, responses_dir, save_json)
    message = stats_refresh_message(score_stats, tasks)
    return {
        "run_id": snapshot["run_id"],
        "kind": snapshot["kind"],
        "captured_at": snapshot["captured_at"],
        "captured_at_ist": snapshot["captured_at_ist"],
        "model": snapshot["summary"].get("model"),
        "score_stats": score_stats,
        "scored_tasks": _count_scored_tasks(tasks),
        "total_tasks": len(tasks),
        "message": message,
    }


def capture_stats_snapshot(responses_dir, load_json, save_json):
    return refresh_stats_snapshot(responses_dir, load_json, save_json)


def _enrich_index_entry(entry, responses_dir, load_json):
    if not isinstance(entry, dict):
        return None
    enriched = dict(entry)
    if not enriched.get("captured_at_ist"):
        enriched["captured_at_ist"] = to_ist_display(enriched.get("captured_at"))
    if "score_stats" not in enriched:
        run_id = enriched.get("run_id")
        if run_id and load_json is not None:
            snapshot = load_run_snapshot(responses_dir, run_id, load_json)
            enriched["score_stats"] = score_stats_for_snapshot(snapshot)
            if not enriched.get("model") and isinstance(snapshot, dict):
                summary = snapshot.get("summary") or {}
                enriched["model"] = summary.get("model")
        else:
            enriched["score_stats"] = None
    return enriched


def list_run_index(responses_dir, load_json=None):
    runs = _load_index(responses_dir).get("runs", [])
    enriched = []
    for entry in runs:
        row = _enrich_index_entry(entry, responses_dir, load_json)
        if row:
            enriched.append(row)
    return enriched


def load_run_snapshot(responses_dir, run_id, load_json):
    path = run_path(responses_dir, run_id)
    if not os.path.exists(path):
        return None
    payload = load_json(path)
    if not isinstance(payload, dict):
        return None
    payload["score_stats"] = score_stats_for_snapshot(payload)
    return payload
