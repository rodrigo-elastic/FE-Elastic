"""
filename: run_pipeline.py
description: End-to-end smoke test of the agent chain on synthetic data. Runs the Pre-Meeting agent against the upcoming Acme meeting, the Post-Meeting agent against a past Acme meeting, and a single Live alert demo.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import argparse
import asyncio
import json

from app.agents.live_meeting import LiveMeetingAgent
from app.agents.post_meeting import PostMeetingAgent
from app.agents.pre_meeting import PreMeetingAgent
from app.repositories import synthetic
from app.services import transcript_parser

PRE_MEETING_DEFAULT = "northwind-mtg-001"
POST_MEETING_DEFAULT = "northwind-mtg-prev-001"


async def _run(pre_id: str, post_id: str) -> dict:
    pre = await PreMeetingAgent().run({"meeting_id": pre_id})
    post = await PostMeetingAgent().run({"meeting_id": post_id})

    transcript = synthetic.transcript_for_meeting(post_id)
    sample_turn_idx = min(4, len(transcript["turns"]) - 1)
    live = await LiveMeetingAgent().run(
        {
            "turn": transcript["turns"][sample_turn_idx],
            "recent_context": transcript_parser.recent_context(transcript, sample_turn_idx),
        }
    )

    return {
        "pre_meeting": {
            "meeting_id": pre_id,
            "headline": pre["headline"],
            "section_count": len(pre["sections"]),
            "artifact_path": pre["artifact_path"],
        },
        "post_meeting": {
            "meeting_id": post_id,
            "summary": post["summary"][:200] + "...",
            "action_items": len(post["action_items"]),
            "salesforce_task_ids": post["salesforce_task_ids"],
            "email_draft_path": post["email_draft_path"],
        },
        "live_meeting": {
            "meeting_id": post_id,
            "turn_index": sample_turn_idx,
            "alert_count": len(live["alerts"]),
            "alerts": live["alerts"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the FE Copilot agent pipeline end to end.")
    parser.add_argument("--pre", default=PRE_MEETING_DEFAULT, help="meeting_id for Pre-Meeting agent")
    parser.add_argument("--post", default=POST_MEETING_DEFAULT, help="meeting_id for Post-Meeting agent")
    args = parser.parse_args()

    result = asyncio.run(_run(args.pre, args.post))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
