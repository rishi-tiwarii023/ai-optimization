from __future__ import annotations

from abc import ABC, abstractmethod

from src.contracts.scoring import ScoreResult, VerificationRequest


class Verifier(ABC):
    """Port for scoring a trial workspace."""

    @abstractmethod
    def verify(self, request: VerificationRequest) -> ScoreResult:
        """Run deterministic checks and persist a JSON artefact."""
