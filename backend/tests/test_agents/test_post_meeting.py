"""
filename: test_post_meeting.py
description: Mock-mode end-to-end test for the Post-Meeting Action Engine.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import asyncio
import json

from app.agents.post_meeting import PostMeetingAgent
from app.config import settings


def test_post_meeting_runs_end_to_end():
    agent = PostMeetingAgent()
    record = asyncio.run(agent.run({"meeting_id": "northwind-mtg-prev-001"}))

    assert record["meeting_id"] == "northwind-mtg-prev-001"
    assert isinstance(record["action_items"], list) and len(record["action_items"]) >= 1
    assert all("source_quote" in a for a in record["action_items"])

    # Salesforce mock log got at least one task per action item.
    sfdc_log = settings.runtime_dir / "salesforce.log"
    assert sfdc_log.exists()
    lines = sfdc_log.read_text(encoding="utf-8").strip().splitlines()
    # The log now mixes task writes with extended SF writes (notes, MEDDPICC, etc.);
    # filter to Task records via the Subject field.
    task_records = [json.loads(line) for line in lines if "\"Subject\"" in line]
    subjects = {r["Subject"] for r in task_records}
    assert all(a["title"] in subjects for a in record["action_items"])
    # Each task carries the meeting id as WhatId so the dashboard can link tasks back.
    matching = [r for r in task_records if r.get("WhatId") == "northwind-mtg-prev-001"]
    assert len(matching) >= len(record["action_items"])

    # Extended SF sync should also include a ContentNote and a MEDDPICC update.
    actions_seen = {json.loads(l).get("_action") for l in lines if l.strip()}
    assert "ContentNote.create" in actions_seen
    assert "Opportunity.update.meddpicc" in actions_seen

    # Email draft persisted.
    email_path = settings.runtime_dir / "emails" / "northwind-mtg-prev-001.json"
    assert email_path.exists()
    email = json.loads(email_path.read_text(encoding="utf-8"))
    assert email["subject"]
    assert "rodrigo" in email["body_markdown"].lower() or len(email["body_markdown"]) > 50


def test_post_meeting_meddpicc_categories_are_valid():
    agent = PostMeetingAgent()
    record = asyncio.run(agent.run({"meeting_id": "northwind-mtg-prev-001"}))
    valid = {
        "Metrics",
        "Economic Buyer",
        "Decision Criteria",
        "Decision Process",
        "Identify Pain",
        "Champion",
        "Competition",
    }
    for s in record["meddpicc_signals"]:
        assert s["category"] in valid
