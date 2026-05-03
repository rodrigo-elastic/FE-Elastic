"""
filename: test_claude_client.py
description: Unit tests for ClaudeService construction and mock-mode behavior.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import pytest

from app.agents.schemas import LiveAlertsOut
from app.integrations import claude_client


def test_mock_mode_auto_enables_with_placeholder_key(monkeypatch):
    monkeypatch.setattr(claude_client.settings, "anthropic_api_key", "sk-ant-replace-me", raising=False)
    svc = claude_client.ClaudeService()
    assert svc.mock_mode is True
    assert svc._client is None


def test_mock_mode_explicit_off_with_real_key(monkeypatch):
    monkeypatch.setattr(claude_client.settings, "anthropic_api_key", "sk-ant-real-XXX", raising=False)
    svc = claude_client.ClaudeService(mock_mode=False)
    assert svc.mock_mode is False


def test_call_structured_returns_validated_pydantic_in_mock_mode():
    svc = claude_client.ClaudeService(api_key="", mock_mode=True)
    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {"alerts": {"type": "array"}},
        "required": ["alerts"],
    }
    result = svc.call_structured(
        system="frozen",
        user="anything",
        schema=schema,
        output_model=LiveAlertsOut,
        mock_payload={"alerts": []},
    )
    assert isinstance(result, LiveAlertsOut)
    assert result.alerts == []


def test_invalid_mock_payload_raises_validation_error():
    svc = claude_client.ClaudeService(api_key="", mock_mode=True)
    schema = {"type": "object", "properties": {"alerts": {"type": "array"}}, "required": ["alerts"]}
    with pytest.raises(Exception):  # pydantic ValidationError
        svc.call_structured(
            system="frozen",
            user="anything",
            schema=schema,
            output_model=LiveAlertsOut,
            mock_payload={"not_alerts": True},
        )
