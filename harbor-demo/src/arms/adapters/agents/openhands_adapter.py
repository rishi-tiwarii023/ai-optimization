from __future__ import annotations

import difflib
import json
import os
import shutil
import subprocess
import sys
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from src.adapters.models.factory import create_model_provider
from src.contracts.config import ModelSpec
from src.contracts.sandbox import SandboxSession
from src.contracts.trials import ResourceUsage, TrajectoryEvent, TrialRequest, TrialResult

_SKIP_DIR_NAMES = {".git", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
_TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
    ".json",
    ".ini",
    ".cfg",
    ".sh",
}


@dataclass(frozen=True)
class OpenHandsOutcome:
    """Raw OpenHands session output. Mapped into TrialResult by the adapter."""

    events: list[dict[str, Any]] = field(default_factory=list)
    logs: str = ""
    error: str | None = None
    timed_out: bool = False
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class OpenHandsRunner(Protocol):
    def run(
        self,
        *,
        model: ModelSpec,
        workspace: Path,
        instruction: str,
        timeout_seconds: float,
        api_key: str,
        extra_env: dict[str, str] | None = None,
        model_prefix: str = "litellm_proxy",
    ) -> OpenHandsOutcome:
        """Start OpenHands against a mounted workspace and return captured events."""


class SubprocessOpenHandsRunner:
    """Invoke the OpenHands CLI in headless mode. No session cache."""

    def __init__(self, binary: str = "openhands") -> None:
        self._binary = binary

    def run(
        self,
        *,
        model: ModelSpec,
        workspace: Path,
        instruction: str,
        timeout_seconds: float,
        api_key: str,
        extra_env: dict[str, str] | None = None,
        model_prefix: str = "litellm_proxy",
    ) -> OpenHandsOutcome:
        env = dict(os.environ)
        env.update(extra_env or {})
        env["LLM_MODEL"] = _litellm_model(model.inference_id, prefix=model_prefix)
        env["LLM_API_KEY"] = api_key
        command = _resolve_openhands_command(self._binary)
        if command is None:
            return OpenHandsOutcome(error=_missing_openhands_message(self._binary))
        args = [
            *command,
            "--headless",
            "--json",
            "--override-with-envs",
            "--task",
            instruction,
        ]
        try:
            completed = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=timeout_seconds,
                check=False,
                cwd=str(workspace),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if isinstance(stdout, bytes):
                stdout = stdout.decode("utf-8", errors="replace")
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return OpenHandsOutcome(
                logs=_join_logs(stdout, stderr),
                error=f"OpenHands timed out after {timeout_seconds}s",
                timed_out=True,
            )
        except FileNotFoundError:
            return OpenHandsOutcome(error=_missing_openhands_message(self._binary))
        logs = _join_logs(completed.stdout, completed.stderr)
        events = _parse_event_lines(completed.stdout)
        error = None
        if completed.returncode != 0:
            hint = _cli_error_hint(completed.stderr, completed.stdout)
            error = f"OpenHands exited with code {completed.returncode}"
            if hint:
                error = f"{error}: {hint}"
        return OpenHandsOutcome(events=events, logs=logs, error=error)


class OpenHandsAdapter:
    """Stateless OpenHands execution. Does not score, store, or report results."""

    def __init__(
        self,
        *,
        runner: OpenHandsRunner | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._runner = runner or SubprocessOpenHandsRunner()
        self._repo_root = repo_root or Path(__file__).resolve().parents[4]

    def execute(self, request: TrialRequest, sandbox: SandboxSession) -> TrialResult:
        task_id = request.task.id
        model_id = request.model.inference_id
        attempt_id = request.attempt
        started = time.perf_counter()

        try:
            workspace = sandbox.mount()
            instruction, timeout_seconds = self._load_task(request)
            before = _snapshot(workspace)
            api_key, model_prefix, extra_env = self._llm_runtime(request)
            outcome = self._runner.run(
                model=request.model,
                workspace=workspace,
                instruction=instruction,
                timeout_seconds=timeout_seconds,
                api_key=api_key,
                extra_env=extra_env,
                model_prefix=model_prefix,
            )
            after = _snapshot(workspace)
        except Exception as exc:  # noqa: BLE001
            return TrialResult(
                status="error",
                patch=None,
                trajectory=[],
                execution_logs="",
                resource_usage=ResourceUsage(latency_seconds=time.perf_counter() - started),
                error_details=str(exc),
            )

        file_changes = _file_changes(before, after)
        patch = _unified_patch(before, after)
        trajectory = _trajectory(outcome.events, file_changes)
        logs = _execution_logs(
            task_id=task_id,
            model_id=model_id,
            attempt_id=attempt_id,
            workspace=workspace,
            outcome=outcome,
        )
        usage = ResourceUsage(
            prompt_tokens=outcome.prompt_tokens,
            completion_tokens=outcome.completion_tokens,
            total_tokens=outcome.total_tokens,
            latency_seconds=time.perf_counter() - started,
        )
        if outcome.timed_out:
            return TrialResult(
                status="timeout",
                patch=patch or None,
                trajectory=trajectory,
                execution_logs=logs,
                resource_usage=usage,
                error_details=outcome.error,
            )
        if outcome.error:
            return TrialResult(
                status="error",
                patch=patch or None,
                trajectory=trajectory,
                execution_logs=logs,
                resource_usage=usage,
                error_details=outcome.error,
            )
        return TrialResult(
            status="success",
            patch=patch or None,
            trajectory=trajectory,
            execution_logs=logs,
            resource_usage=usage,
            error_details=None,
        )

    def _llm_runtime(self, request: TrialRequest) -> tuple[str, str, dict[str, str]]:
        model_provider = create_model_provider(request.provider)
        prefix = (request.provider.prefix or "litellm_proxy").strip()
        extra = model_provider.get_agent_env(request.model)
        api_key = extra.get("LLM_API_KEY", "")
        return api_key, prefix, extra

    def _load_task(self, request: TrialRequest) -> tuple[str, float]:
        task_dir = self._task_dir(request)
        toml_path = task_dir / "task.toml"
        if not toml_path.is_file():
            raise FileNotFoundError(f"task.toml not found for task {request.task.id}: {toml_path}")
        meta = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        parts: list[str] = []
        description = meta.get("description")
        if isinstance(description, str) and description.strip():
            parts.append(description.strip())
        instruction_md = task_dir / "instruction.md"
        if instruction_md.is_file():
            parts.append(instruction_md.read_text(encoding="utf-8").strip())
        if not parts:
            raise ValueError(f"No instructions found for task {request.task.id}")
        timeout = meta.get("timeout", request.provider.timeout_seconds)
        return "\n\n".join(parts), float(timeout)

    def _task_dir(self, request: TrialRequest) -> Path:
        raw = request.task.path
        if raw:
            path = Path(raw)
            if not path.is_absolute():
                path = self._repo_root / path
            return path
        return self._repo_root / "datasets" / "internal-core" / request.task.id


def _snapshot(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    if not root.exists():
        return files
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _SKIP_DIR_NAMES for part in path.parts):
            continue
        if path.suffix.lower() not in _TEXT_SUFFIXES and path.suffix:
            continue
        relative = path.relative_to(root).as_posix()
        try:
            files[relative] = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
    return files


def _file_changes(before: dict[str, str], after: dict[str, str]) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for name in sorted(set(before) | set(after)):
        if name not in after:
            changes.append({"path": name, "action": "deleted"})
        elif name not in before:
            changes.append({"path": name, "action": "created"})
        elif before[name] != after[name]:
            changes.append({"path": name, "action": "modified"})
    return changes


def _unified_patch(before: dict[str, str], after: dict[str, str]) -> str:
    chunks: list[str] = []
    for name in sorted(set(before) | set(after)):
        old = before.get(name, "").splitlines(keepends=True)
        new = after.get(name, "").splitlines(keepends=True)
        if old == new:
            continue
        diff = difflib.unified_diff(old, new, fromfile=f"a/{name}", tofile=f"b/{name}")
        chunks.append("".join(diff))
    return "\n".join(chunk for chunk in chunks if chunk)


def _trajectory(
    events: list[dict[str, Any]],
    file_changes: list[dict[str, str]],
) -> list[TrajectoryEvent]:
    mapped: list[TrajectoryEvent] = []
    for event in events:
        kind = str(event.get("kind") or event.get("type") or "message")
        if kind in {"assistant", "user", "thought", "message"}:
            mapped.append(TrajectoryEvent(kind="message", payload=event))
        elif kind in {"tool", "tool_call", "action"}:
            mapped.append(TrajectoryEvent(kind="tool_call", payload=event))
        elif kind in {"command", "cmd", "run"}:
            mapped.append(TrajectoryEvent(kind="command", payload=event))
        elif kind in {"file_change", "edit", "write"}:
            mapped.append(TrajectoryEvent(kind="file_change", payload=event))
        else:
            mapped.append(TrajectoryEvent(kind="message", payload=event))
    for change in file_changes:
        mapped.append(TrajectoryEvent(kind="file_change", payload=change))
    return mapped


def _execution_logs(
    *,
    task_id: str,
    model_id: str,
    attempt_id: int,
    workspace: Path,
    outcome: OpenHandsOutcome,
) -> str:
    header = (
        f"task_id={task_id}\n"
        f"model_id={model_id}\n"
        f"attempt_id={attempt_id}\n"
        f"workspace={workspace}\n"
    )
    body = outcome.logs.strip()
    return f"{header}\n{body}".strip()


_LITELLM_PROVIDER_PREFIXES = (
    "openai/",
    "anthropic/",
    "openrouter/",
    "together_ai/",
    "groq/",
    "litellm_proxy/",
    "litellm/",
    "laguna/",
)


def _litellm_model(model_id: str, prefix: str = "litellm_proxy") -> str:
    """OpenHands talks to local LiteLLM/Laguna as litellm_proxy/<model>."""

    raw = model_id.strip()
    if not raw:
        return raw
    lowered = raw.lower()
    if any(lowered.startswith(known) for known in _LITELLM_PROVIDER_PREFIXES):
        return raw
    normalized = prefix.strip().rstrip("/") or "litellm_proxy"
    if lowered.startswith(f"{normalized.lower()}/"):
        return raw
    return f"{normalized}/{raw}"


def _resolve_openhands_command(binary: str) -> list[str] | None:
    configured = os.environ.get("OPENHANDS_BIN", binary).strip()
    if not configured:
        return None
    as_path = Path(configured).expanduser()
    if as_path.is_file():
        return [str(as_path.resolve())]
    found = shutil.which(configured)
    if found:
        return [found]
    scripts = Path(sys.executable).resolve().parent / configured
    if scripts.is_file():
        return [str(scripts)]
    return None


def _missing_openhands_message(binary: str) -> str:
    return (
        f"OpenHands headless CLI not found ({binary!r} is not on PATH). "
        "This venv's openhands-ai package is the HTTP agent-server, not the "
        "headless CLI. Install the OpenHands CLI, put it on PATH, or set OPENHANDS_BIN."
    )


def _cli_error_hint(stderr: str | None, stdout: str | None, *, limit: int = 400) -> str:
    text = (stderr or stdout or "").strip().replace("\n", " ")
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _join_logs(stdout: str | None, stderr: str | None) -> str:
    parts = [part.strip() for part in (stdout or "", stderr or "") if part and part.strip()]
    return "\n".join(parts)


def _parse_event_lines(stdout: str | None) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not stdout:
        return events
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return events
