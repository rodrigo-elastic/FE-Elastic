"""
filename: routes_meetings.py
description: Read endpoints for meetings, companies, calendar, transcripts. Backed by the synthetic repository.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json

from fastapi import APIRouter, HTTPException

from app.config import settings
from app.repositories import synthetic

router = APIRouter(prefix="/meetings", tags=["meetings"])


@router.get("")
async def list_meetings() -> list:
    """All meetings, decorated with the company name and an `is_upcoming` flag."""
    companies_by_id = {c["id"]: c for c in synthetic.companies()}
    upcoming_ids = {ev["meeting_id"] for ev in synthetic.upcoming_calendar()}
    items = []
    for m in synthetic.meetings():
        company = companies_by_id.get(m["company_id"], {})
        items.append(
            {
                **m,
                "company_name": company.get("name"),
                "company_industry": company.get("industry"),
                "is_upcoming": m["id"] in upcoming_ids,
            }
        )
    items.sort(key=lambda x: x["start_time"])
    return items


@router.get("/upcoming")
async def list_upcoming() -> list:
    return synthetic.upcoming_calendar()


@router.get("/{meeting_id}")
async def get_meeting(meeting_id: str) -> dict:
    meeting = synthetic.find_meeting(meeting_id)
    if meeting is not None:
        company = synthetic.find_company(meeting["company_id"]) or {}
        transcript = synthetic.transcript_for_meeting(meeting_id)
        return {
            "meeting": meeting,
            "company": company,
            "transcript": transcript,
            "news": synthetic.news_for(company.get("id", "")),
            "tickets": synthetic.tickets_for(company.get("id", "")),
        }

    # Ad-hoc meeting (Quick Research brief or uploaded transcript) — fall back to the
    # snapshot stashed alongside the artifact.
    for sub in ("briefs", "post_meeting"):
        path = settings.runtime_dir / sub / f"{meeting_id}.json"
        if path.exists():
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("ad_hoc"):
                return {
                    "meeting": record.get("meeting_snapshot") or {},
                    "company": record.get("company_snapshot") or {},
                    "transcript": record.get("transcript_snapshot"),
                    "news": [],
                    "tickets": [],
                }

    raise HTTPException(status_code=404, detail="meeting not found")
