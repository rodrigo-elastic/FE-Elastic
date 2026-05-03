"""
filename: test_health.py
description: Smoke test for /health and /version endpoints.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_version_returns_version() -> None:
    response = client.get("/api/v1/version")
    assert response.status_code == 200
    body = response.json()
    assert "version" in body
    assert body["service"] == "fe-copilot"
