from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Protocol

from src.adapters.verifiers.pytest_counts import parse_pytest_counts
from src.adapters.verifiers.verifier import Verifier
from src.contracts.scoring import ScoreResult, VerificationRequest

_BUILD_SNIPPET = (
    "from app.main import app\n"
    "assert app is not None\n"
)

_ENDPOINT_SNIPPET = (
    "from app.main import app\n"
    "paths = {getattr(route, 'path', None) for route in app.routes}\n"
    "raise SystemExit(0 if '/health' in paths else 1)\n"
)


class CommandRunner(Protocol):
    def run(self, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        ...


class SubprocessRunner:
    def run(self, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )


class DockerSandboxVerifier(Verifier):
    """Score a workspace inside the health-api Docker sandbox."""

    def __init__(
        self,
        *,
        compose_file: Path,
        runner: CommandRunner | None = None,
        docker: str = "docker",
    ) -> None:
        self._compose_file = compose_file.resolve()
        self._runner = runner or SubprocessRunner()
        self._docker = docker

    def verify(self, request: VerificationRequest) -> ScoreResult:
        request.artefact_dir.mkdir(parents=True, exist_ok=True)
        project = f"health-api-{_safe_id(request.trial_id)}"
        env = {
            "TRIAL_ID": request.trial_id,
            "SKIP_SERVER": "1",
            "RUN_TESTS": "0",
        }
        checks = {
            "container_starts": False,
            "application_builds": False,
            "endpoint_exists": False,
            "tests_pass": False,
        }
        logs: dict[str, str] = {}
        tests_passed = 0
        tests_failed = 0
        build_passed = False

        override = _write_override(request.artefact_dir, request.trial_id, request.workspace)

        try:
            build = self._compose(project, override, ["build"], env)
            logs["build"] = _clip(build.stdout + build.stderr)
            build_passed = build.returncode == 0
            checks["application_builds"] = build_passed

            if build_passed:
                up = self._compose(project, override, ["up", "-d", "--no-build"], env)
                logs["up"] = _clip(up.stdout + up.stderr)
                ps = self._compose(project, override, ["ps", "--status", "running", "--quiet"], env)
                checks["container_starts"] = up.returncode == 0 and bool(ps.stdout.strip())
                logs["ps"] = _clip(ps.stdout + ps.stderr)

            if checks["container_starts"]:
                import_check = self._exec(project, override, ["python", "-c", _BUILD_SNIPPET], env)
                logs["import"] = _clip(import_check.stdout + import_check.stderr)
                if import_check.returncode != 0:
                    checks["application_builds"] = False
                    build_passed = False
                else:
                    endpoint = self._exec(project, override, ["python", "-c", _ENDPOINT_SNIPPET], env)
                    logs["endpoint"] = _clip(endpoint.stdout + endpoint.stderr)
                    checks["endpoint_exists"] = endpoint.returncode == 0

                    pytest_run = self._exec(
                        project,
                        override,
                        ["pytest", "/opt/task/tests", "-q", "--tb=no"],
                        env,
                    )
                    logs["pytest"] = _clip(pytest_run.stdout + pytest_run.stderr)
                    tests_passed, tests_failed = parse_pytest_counts(
                        pytest_run.stdout + "\n" + pytest_run.stderr
                    )
                    checks["tests_pass"] = (
                        pytest_run.returncode == 0 and tests_failed == 0 and tests_passed > 0
                    )
        finally:
            down = self._compose(
                project,
                override,
                ["down", "--remove-orphans", "--volumes"],
                env,
            )
            logs["down"] = _clip(down.stdout + down.stderr)

        passed = (
            checks["container_starts"]
            and checks["application_builds"]
            and checks["endpoint_exists"]
            and checks["tests_pass"]
            and build_passed
        )
        result = ScoreResult(
            passed=passed,
            build_passed=build_passed,
            tests_passed=tests_passed,
            tests_failed=tests_failed,
        )
        self._write_artefact(request, result, checks, logs)
        return result

    def _compose(
        self,
        project: str,
        override: Path,
        extra: list[str],
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        return self._runner.run(
            [
                self._docker,
                "compose",
                "--project-name",
                project,
                "--file",
                str(self._compose_file),
                "--file",
                str(override),
                *extra,
            ],
            env=_merge_env(env),
        )

    def _exec(
        self,
        project: str,
        override: Path,
        command: list[str],
        env: dict[str, str],
    ) -> subprocess.CompletedProcess[str]:
        return self._compose(
            project,
            override,
            ["exec", "-T", "trial", *command],
            env,
        )

    def _write_artefact(
        self,
        request: VerificationRequest,
        result: ScoreResult,
        checks: dict[str, bool],
        logs: dict[str, str],
    ) -> None:
        path = request.artefact_dir / f"{_safe_id(request.trial_id)}.json"
        payload = {
            **result.model_dump(),
            "trial_id": request.trial_id,
            "workspace": str(request.workspace),
            "checks": checks,
            "logs": logs,
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_override(artefact_dir: Path, trial_id: str, workspace: Path) -> Path:
    mount = str(workspace.resolve()).replace("\\", "/")
    override = artefact_dir / f"{_safe_id(trial_id)}.compose.override.yml"
    override.write_text(
        "\n".join(
            [
                "services:",
                "  trial:",
                "    volumes:",
                f'      - "{mount}:/workspace"',
                "    environment:",
                "      SKIP_SERVER: \"1\"",
                "      RUN_TESTS: \"0\"",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return override


def _safe_id(trial_id: str) -> str:
    cleaned = trial_id.replace("/", "_").replace(":", "_").replace(" ", "_")
    return re.sub(r"[^A-Za-z0-9_-]", "_", cleaned)


def _clip(text: str, limit: int = 8000) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[-limit:]


def _merge_env(extra: dict[str, str]) -> dict[str, str] | None:
    import os

    merged = dict(os.environ)
    merged.update(extra)
    return merged
