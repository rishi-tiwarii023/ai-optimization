from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field


class ScoreResult(BaseModel):
    """Deterministic verifier output schema."""

    passed: bool
    build_passed: bool
    tests_passed: int = Field(ge=0)
    tests_failed: int = Field(ge=0)


class VerificationRequest(BaseModel):
    """Input for a verifier."""

    trial_id: str
    workspace: Path
    task_path: Path
    artefact_dir: Path
 