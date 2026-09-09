from __future__ import annotations

from fastapi.testclient import TestClient


def test_application_starts(client: TestClient) -> None:
    assert client.app is not None


def test_health_returns_http_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200


def test_health_body_equals_status_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.json() == {"status": "ok"}
