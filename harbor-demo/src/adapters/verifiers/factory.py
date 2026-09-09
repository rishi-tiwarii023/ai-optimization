from __future__ import annotations

from pathlib import Path

from src.adapters.verifiers.docker_verifier import DockerSandboxVerifier
from src.adapters.verifiers.verifier import Verifier

_DEFAULT_COMPOSE = (
    Path(__file__).resolve().parents[3]
    / "datasets"
    / "internal-core"
    / "health-api"
    / "environment"
    / "docker-compose.yml"
)


def create_verifier(
    *,
    compose_file: Path | None = None,
) -> Verifier:
    """Compose a Verifier."""
    return DockerSandboxVerifier(compose_file=compose_file or _DEFAULT_COMPOSE)
