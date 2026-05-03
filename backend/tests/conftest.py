"""
filename: conftest.py
description: Pytest fixtures shared across the suite. Generates synthetic data once per session and forces ClaudeService into mock mode regardless of the host env (so a real ANTHROPIC_API_KEY never gets called from tests).
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import pytest

from app.integrations import claude_client
from app.repositories import synthetic
from scripts.generate_synthetic_data import generate


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_synthetic():
    generate(seed=42, num_companies=3)
    synthetic.reset_cache()
    yield


@pytest.fixture(autouse=True)
def _force_mock_claude(monkeypatch, tmp_path):
    from app.repositories import elasticsearch_repo

    # Force mock mode regardless of host env.
    monkeypatch.setattr(claude_client.settings, "anthropic_api_key", "", raising=False)
    # Isolate artifacts (audit log, slack/sfdc logs, briefs) per test so the demo
    # runtime/ directory is never touched by the test suite.
    monkeypatch.setattr(claude_client.settings, "runtime_dir", tmp_path, raising=False)
    # Make ES unreachable for the test process so reads/writes degrade to disk.
    monkeypatch.setattr(claude_client.settings, "elasticsearch_url", "http://127.0.0.1:1", raising=False)
    claude_client.reset_service()
    elasticsearch_repo.reset_repo()
    yield
    claude_client.reset_service()
    elasticsearch_repo.reset_repo()
