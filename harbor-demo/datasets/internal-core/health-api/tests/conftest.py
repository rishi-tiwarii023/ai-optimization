from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TASK_ROOT = Path(__file__).resolve().parents[1]
STARTER_ROOT = TASK_ROOT / "starter"

for candidate in (Path.cwd(), STARTER_ROOT, TASK_ROOT):
    path = str(candidate)
    if path not in sys.path:
        sys.path.insert(0, path)

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client
