"""
filename: test_pre_meeting.py
description: Mock-mode end-to-end test for the Pre-Meeting Researcher agent.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import asyncio
import json
from pathlib import Path

from app.agents.pre_meeting import PreMeetingAgent
from app.config import settings


def test_pre_meeting_runs_end_to_end():
    agent = PreMeetingAgent()
    record = asyncio.run(agent.run({"meeting_id": "revolut-mtg-001"}))

    assert record["meeting_id"] == "revolut-mtg-001"
    assert record["company_id"] == "revolut"
    assert "headline" in record and len(record["headline"]) > 10
    assert isinstance(record["sections"], list) and len(record["sections"]) >= 4

    artifact = Path(record["artifact_path"])
    assert artifact.exists(), "PDF or HTML fallback must exist"

    # Slack mock recorded the post.
    slack_log = settings.runtime_dir / "slack.log"
    assert slack_log.exists()
    last_line = slack_log.read_text(encoding="utf-8").strip().splitlines()[-1]
    payload = json.loads(last_line)
    assert payload["channel"] == "#fe-copilot-briefs"
    assert "Revolut" in payload["text"]


def test_pre_meeting_unknown_meeting_raises():
    agent = PreMeetingAgent()
    try:
        asyncio.run(agent.run({"meeting_id": "does-not-exist"}))
    except ValueError as e:
        assert "not found" in str(e)
        return
    raise AssertionError("expected ValueError")
