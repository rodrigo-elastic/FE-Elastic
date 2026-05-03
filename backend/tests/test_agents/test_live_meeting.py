"""
filename: test_live_meeting.py
description: Mock-mode test for the Live Meeting Companion (Haiku).
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import asyncio

from app.agents.live_meeting import LiveMeetingAgent


def test_live_meeting_emits_competitor_alert():
    agent = LiveMeetingAgent()
    turn = {"speaker": "Customer", "text": "We are paying north of 3 million dollars on Splunk for renewal."}
    out = asyncio.run(agent.run({"turn": turn}))
    assert "alerts" in out
    types = {a["type"] for a in out["alerts"]}
    assert "competitor" in types


def test_live_meeting_silent_on_pleasantries():
    agent = LiveMeetingAgent()
    turn = {"speaker": "Customer", "text": "Thanks for joining. Good morning."}
    out = asyncio.run(agent.run({"turn": turn}))
    assert "alerts" in out
    for a in out["alerts"]:
        assert a["type"] in {"competitor", "meddpicc", "question", "risk"}
