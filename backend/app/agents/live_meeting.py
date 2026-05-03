"""
filename: live_meeting.py
description: Live Meeting Companion. Per-turn alert generation on Haiku 4.5; falls back to a heuristic mock when the API key is absent.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import Any, Dict

from app.agents.base import Agent
from app.agents.prompts import language_instruction, language_preamble, live_meeting as prompt
from app.agents.schemas import LiveAlertsOut
from app.config import settings
from app.integrations.claude_client import get_service
from app.utils.logging import get_logger

log = get_logger(__name__)


class LiveMeetingAgent(Agent):
    name = "live_meeting"

    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        turn = payload["turn"]
        recent = payload.get("recent_context") or []
        log.info("live_meeting.turn", speaker=turn.get("speaker"))

        language = payload.get("language") or "English"
        result: LiveAlertsOut = get_service().call_structured(
            system=prompt.SYSTEM,
            user=language_preamble(language) + prompt.render_user_prompt(turn, recent) + language_instruction(language),
            schema=prompt.OUTPUT_SCHEMA,
            output_model=LiveAlertsOut,
            model=settings.model_for("live_meeting"),
            max_tokens=512,
            mock_payload=prompt.mock_response_for(turn.get("text", "")),
            audit_meta={"agent": "live_meeting", "meeting_id": payload.get("meeting_id"), "speaker": turn.get("speaker")},
        )
        return result.model_dump()
