from __future__ import annotations

import inspect
import json
import subprocess
from pathlib import Path

from src.adapters.verifiers import docker_verifier as docker_verifier_mod

from src.adapters.verifiers.docker_verifier import DockerSandboxVerifier
from src.adapters.verifiers.factory import create_verifier
from src.adapters.verifiers.pytest_counts import parse_pytest_counts
from src.adapters.verifiers.verifier import Verifier
from src.contracts.scoring import ScoreResult, VerificationRequest


class FakeRunner:
    def __init__(self, script: dict[str, subprocess.CompletedProcess[str]]) -> None:
        self.script = script
        self.calls: list[list[str]] = []

    def run(self, args: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        self.calls.append(args)
        key = _classify(args)
        return self.script.get(
            key,
            subprocess.CompletedProcess(args, 1, stdout="", stderr=f"unexpected:{key}"),
        )


def _classify(args: list[str]) -> str:
    joined = " ".join(args)
    if "compose" in args and "build" in args:
        return "build"
    if "compose" in args and "up" in args:
        return "up"
    if "compose" in args and "ps" in args:
        return "ps"
    if "compose" in args and "down" in args:
        return "down"
    if "-c" in args and "SystemExit" in joined:
        return "endpoint"
    if "-c" in args:
        return "import"
    if "pytest" in args:
        return "pytest"
    return "other"


def _ok(stdout: str = "", code: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["docker"], code, stdout=stdout, stderr="")


def test_score_result_schema() -> None:
    payload = ScoreResult(
        passed=True,
        build_passed=True,
        tests_passed=3,
        tests_failed=0,
    ).model_dump()
    assert payload == {
        "passed": True,
        "build_passed": True,
        "tests_passed": 3,
        "tests_failed": 0,
    }


def test_parse_pytest_counts() -> None:
    assert parse_pytest_counts("... 3 passed in 0.12s") == (3, 0)
    assert parse_pytest_counts("2 passed, 1 failed in 0.20s") == (2, 1)


def test_verify_writes_artefact_and_returns_score(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    artefact_dir = tmp_path / "artefacts"
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("services: {}\n", encoding="utf-8")

    runner = FakeRunner(
        {
            "build": _ok("built"),
            "up": _ok("started"),
            "ps": _ok("abc123"),
            "import": _ok(""),
            "endpoint": _ok(""),
            "pytest": _ok("3 passed in 0.05s"),
            "down": _ok(""),
        }
    )
    verifier = DockerSandboxVerifier(compose_file=compose, runner=runner)
    result = verifier.verify(
        VerificationRequest(
                trial_id="demo::health-api::agent::model::1",
            workspace=workspace,
            task_path=tmp_path,
            artefact_dir=artefact_dir,
        )
    )
    assert result == ScoreResult(
        passed=True,
        build_passed=True,
        tests_passed=3,
        tests_failed=0,
    )
    artefact = artefact_dir / "demo__health-api__agent__model__1.json"
    data = json.loads(artefact.read_text(encoding="utf-8"))
    assert data["passed"] is True
    assert data["tests_passed"] == 3
    assert data["checks"]["container_starts"] is True
    assert data["checks"]["endpoint_exists"] is True
    assert data["checks"]["tests_pass"] is True
    assert "openhands" not in inspect.getsource(docker_verifier_mod).lower()


def test_create_verifier_is_port_instance() -> None:
    verifier = create_verifier()
    assert isinstance(verifier, Verifier)
    assert "openhands" not in type(verifier).__module__
