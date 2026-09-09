from __future__ import annotations

import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.contracts.trials import FinalTrialResult, ResourceUsage, TrajectoryEvent

_REQUIRED_FILES = (
    "manifest.json",
    "trajectory.json",
    "stdout.log",
    "stderr.log",
    "patch.diff",
    "agent-result.json",
    "resource-usage.json",
    "verifier-result.json",
)

# Placeholder USD per token when the provider does not report a price.
_USD_PER_TOKEN = 0.0


class ArtifactAlreadyExistsError(FileExistsError):
    """Trial artifact directory already exists and must not be overwritten."""


class FilesystemArtifactStore:
    """Write completed-trial artifacts once; never mutate them afterward."""

    def __init__(self, artifacts_root: Path) -> None:
        self._root = artifacts_root

    def trial_dir(self, trial_id: str) -> Path:
        return self._root / f"run_{_safe_id(trial_id)}"

    def save_trial_artifacts(
        self,
        result: FinalTrialResult,
        *,
        timestamp: datetime | None = None,
    ) -> Path:
        target = self.trial_dir(result.trial_id)
        if target.exists():
            raise ArtifactAlreadyExistsError(f"Artifacts already exist for trial {result.trial_id}: {target}")

        target.mkdir(parents=True, exist_ok=False)
        written = _payloads(result, timestamp=timestamp or datetime.now(timezone.utc))
        try:
            for name, content in written.items():
                path = target / name
                path.write_text(content, encoding="utf-8")
                _make_readonly(path)
        except Exception:
            for name in written:
                candidate = target / name
                if candidate.exists():
                    _make_writable(candidate)
                    candidate.unlink()
            if target.exists():
                target.rmdir()
            raise
        return target

    def load_trial_artifacts(self, trial_id: str) -> dict[str, Any]:
        target = self.trial_dir(trial_id)
        if not target.is_dir():
            raise FileNotFoundError(f"No artifacts for trial {trial_id}: {target}")
        return _read_trial_dir(target)


def save_trial_artifacts(
    result: FinalTrialResult,
    artifacts_root: Path,
    *,
    timestamp: datetime | None = None,
) -> Path:
    return FilesystemArtifactStore(artifacts_root).save_trial_artifacts(result, timestamp=timestamp)


def load_trial_artifacts(trial_id: str, artifacts_root: Path) -> dict[str, Any]:
    return FilesystemArtifactStore(artifacts_root).load_trial_artifacts(trial_id)


def _payloads(result: FinalTrialResult, *, timestamp: datetime) -> dict[str, str]:
    execution = result.execution
    messages, tool_calls, commands = _split_trajectory(execution.trajectory)
    usage = execution.resource_usage or ResourceUsage()
    tool_call_count = len(tool_calls)
    return {
        "manifest.json": _dumps(
            {
                "experiment_id": result.experiment_id,
                "task_id": result.task_id,
                "model_id": result.model_id,
                "attempt_id": result.attempt,
                "timestamp": timestamp.astimezone(timezone.utc).isoformat(),
            }
        ),
        "trajectory.json": _dumps(
            {
                "agent_messages": messages,
                "tool_calls": tool_calls,
                "command_history": commands,
            }
        ),
        "stdout.log": execution.execution_logs or "",
        "stderr.log": execution.error_details or "",
        "patch.diff": execution.patch or "",
        "agent-result.json": _dumps(execution.model_dump()),
        "resource-usage.json": _dumps(
            {
                "execution_time": usage.latency_seconds,
                "token_usage": {
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
                "tool_calls": tool_call_count,
                "estimated_cost": _estimated_cost(usage),
            }
        ),
        "verifier-result.json": _dumps(result.score.model_dump()),
    }


def _split_trajectory(
    events: list[TrajectoryEvent],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    messages: list[dict[str, Any]] = []
    tool_calls: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []
    for event in events:
        payload = dict(event.payload)
        if event.kind == "tool_call":
            tool_calls.append(payload)
        elif event.kind == "command":
            commands.append(payload)
        elif event.kind == "message":
            messages.append(payload)
    return messages, tool_calls, commands


def _estimated_cost(usage: ResourceUsage) -> float:
    tokens = usage.total_tokens
    if tokens is None:
        prompt = usage.prompt_tokens or 0
        completion = usage.completion_tokens or 0
        tokens = prompt + completion
    return round(float(tokens) * _USD_PER_TOKEN, 8)


def _read_trial_dir(target: Path) -> dict[str, Any]:
    missing = [name for name in _REQUIRED_FILES if not (target / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Incomplete artifacts in {target}: {missing}")
    return {
        "dir": target,
        "manifest": _load_json(target / "manifest.json"),
        "trajectory": _load_json(target / "trajectory.json"),
        "stdout": (target / "stdout.log").read_text(encoding="utf-8"),
        "stderr": (target / "stderr.log").read_text(encoding="utf-8"),
        "patch": (target / "patch.diff").read_text(encoding="utf-8"),
        "agent_result": _load_json(target / "agent-result.json"),
        "resource_usage": _load_json(target / "resource-usage.json"),
        "verifier_result": _load_json(target / "verifier-result.json"),
    }


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dumps(payload: Any) -> str:
    return json.dumps(payload, indent=2) + "\n"


def _safe_id(trial_id: str) -> str:
    cleaned = trial_id.replace("/", "_").replace(":", "_").replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9._-]", "_", cleaned)


def _make_readonly(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode & ~stat.S_IWRITE & ~stat.S_IWUSR & ~stat.S_IWGRP & ~stat.S_IWOTH)


def _make_writable(path: Path) -> None:
    os.chmod(path, path.stat().st_mode | stat.S_IWRITE | stat.S_IWUSR)
