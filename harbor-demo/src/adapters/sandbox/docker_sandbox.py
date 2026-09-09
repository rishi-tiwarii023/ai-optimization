from __future__ import annotations

import re
import shutil
from pathlib import Path

from src.contracts.trials import TrialRequest
from src.experiments.loader import REPO_ROOT


class DockerSandbox:
    """Isolated host workspace copied from the task starter. One instance per trial."""

    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace.resolve()

    def mount(self) -> Path:
        self._workspace.mkdir(parents=True, exist_ok=True)
        return self._workspace

    def destroy(self) -> None:
        if self._workspace.exists():
            shutil.rmtree(self._workspace, ignore_errors=True)


class DockerSandboxFactory:
    """Create a fresh sandbox from the task starter for each TrialRequest."""

    def __init__(self, *, repo_root: Path | None = None, work_root: Path | None = None) -> None:
        self._repo_root = repo_root or REPO_ROOT
        self._work_root = work_root or (self._repo_root / "artefacts" / "workspaces")

    def create(self, request: TrialRequest) -> DockerSandbox:
        workspace = self._work_root / _safe_id(request.trial_id)
        if workspace.exists():
            shutil.rmtree(workspace)
        workspace.mkdir(parents=True, exist_ok=True)
        starter = _task_dir(request, self._repo_root) / "starter"
        if starter.is_dir():
            shutil.copytree(starter, workspace, dirs_exist_ok=True)
        return DockerSandbox(workspace)


def _task_dir(request: TrialRequest, repo_root: Path) -> Path:
    raw = request.task.path
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = repo_root / path
        return path
    return repo_root / "datasets" / "internal-core" / request.task.id


def _safe_id(trial_id: str) -> str:
    cleaned = trial_id.replace("/", "_").replace(":", "_").replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_-]", "_", cleaned)
