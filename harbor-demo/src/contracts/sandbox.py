from __future__ import annotations

from pathlib import Path
from typing import Protocol


class SandboxSession(Protocol):
    """Mounted trial workspace. DockerSandbox implements this."""

    def mount(self) -> Path:
        """Expose the workspace path OpenHands should edit."""
