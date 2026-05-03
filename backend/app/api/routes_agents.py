"""
filename: routes_agents.py
description: Trigger endpoints for the three agents (pre, live, post). Each endpoint runs the agent and returns its structured result.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.live_meeting import LiveMeetingAgent
from app.agents.post_meeting import PostMeetingAgent
from app.agents.pre_meeting import PreMeetingAgent
from app.repositories import synthetic
from app.services import transcript_parser
from app.services import vtt_parser

router = APIRouter(prefix="/agents", tags=["agents"])

_pre = PreMeetingAgent()
_post = PostMeetingAgent()
_live = LiveMeetingAgent()


class AdHocPreMeetingRequest(BaseModel):
    """User-typed dossier for the Quick Research flow. Only these fields leave the boundary."""

    company_name: str = Field(..., min_length=1, max_length=120)
    industry: Optional[str] = Field("", max_length=80)
    size: Optional[str] = Field("", max_length=80)
    tech_stack: Optional[str] = Field("", max_length=400, description="Comma-separated list of observability/search/cloud tools.")
    notes: Optional[str] = Field("", max_length=2000, description="Free-form context: what to discuss, recent signals, blockers.")
    meeting_title: Optional[str] = Field("", max_length=160)
    language: Optional[str] = Field("English", max_length=40, description="Output language; English|Spanish|Japanese|German|French.")
    model: Optional[str] = Field("", max_length=60, description="Override model id (claude-haiku-4-5 | claude-sonnet-4-6 | claude-opus-4-7). Empty = use server default.")


class AdHocPostMeetingRequest(BaseModel):
    """Run the Post-Meeting agent against an externally-supplied transcript (Zoom .vtt, Gong export, or pasted plain text)."""

    company_name: str = Field(..., min_length=1, max_length=120)
    meeting_title: Optional[str] = Field("", max_length=160)
    industry: Optional[str] = Field("", max_length=80)
    size: Optional[str] = Field("", max_length=80)
    notes: Optional[str] = Field("", max_length=2000)
    transcript_text: str = Field(..., min_length=20, max_length=200000, description="Raw WebVTT or plain 'Speaker: text' transcript.")
    transcript_source: Optional[str] = Field("uploaded", max_length=40, description="zoom | gong | manual")
    language: Optional[str] = Field("English", max_length=40)
    model: Optional[str] = Field("", max_length=60)


@router.post("/pre-meeting/ad-hoc")
async def run_pre_meeting_ad_hoc(req: AdHocPreMeetingRequest) -> Dict[str, Any]:
    """Quick Research: takes only what the FE typed, no synthetic data lookup. Compliance-friendly."""
    try:
        return await _pre.run_ad_hoc(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pre-meeting/{meeting_id}")
async def run_pre_meeting(meeting_id: str, language: str = "English", model: str = "") -> Dict[str, Any]:
    try:
        return await _pre.run({"meeting_id": meeting_id, "language": language, "model": model})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/post-meeting/from-transcript")
async def run_post_meeting_from_transcript(req: AdHocPostMeetingRequest) -> Dict[str, Any]:
    """Parse a Zoom/Gong/plain transcript and run the Post-Meeting agent on it.

    The transcript itself never leaves the boundary except as part of the prompt to Claude.
    """
    turns = vtt_parser.parse_vtt(req.transcript_text)
    if not turns:
        raise HTTPException(status_code=400, detail="could not parse any speaker turns from transcript")
    try:
        return await _post.run_ad_hoc(
            {
                "company_name": req.company_name,
                "meeting_title": req.meeting_title or "",
                "industry": req.industry or "",
                "size": req.size or "",
                "notes": req.notes or "",
                "transcript_source": req.transcript_source or "uploaded",
                "turns": turns,
                "language": req.language or "English",
                "model": req.model or "",
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/post-meeting/{meeting_id}")
async def run_post_meeting(meeting_id: str, language: str = "English", model: str = "") -> Dict[str, Any]:
    try:
        return await _post.run({"meeting_id": meeting_id, "language": language, "model": model})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/live-meeting/{meeting_id}/turn/{turn_index}")
async def run_live_turn(meeting_id: str, turn_index: int, language: str = "English", model: str = "") -> Dict[str, Any]:
    """Demo helper: replay a single transcript turn and return alerts."""
    transcript = synthetic.transcript_for_meeting(meeting_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail="transcript not found")
    turns = transcript.get("turns", [])
    if turn_index < 0 or turn_index >= len(turns):
        raise HTTPException(status_code=400, detail="turn_index out of range")
    return await _live.run(
        {
            "meeting_id": meeting_id,
            "turn": turns[turn_index],
            "recent_context": transcript_parser.recent_context(transcript, turn_index),
            "language": language,
            "model": model,
        }
    )
