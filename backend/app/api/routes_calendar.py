"""
filename: routes_calendar.py
description: Read endpoints for the Google Calendar mock plus the smart-resolver. The dashboard renders this as a "Calendar inbox" so the FE sees their next meetings with the customer auto-detected (consultants and observers filtered out).
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from fastapi import APIRouter, HTTPException

from app.integrations import google_calendar_mock
from app.services import company_resolver

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/events")
async def list_events() -> dict:
    """Upcoming Google Calendar events with the smart-resolver guess for each."""
    events = google_calendar_mock.list_upcoming_events()
    enriched = []
    for ev in events:
        resolution = company_resolver.resolve_event(ev)
        enriched.append(
            {
                "id": ev["id"],
                "summary": ev.get("summary"),
                "description": ev.get("description"),
                "start": ev.get("start"),
                "end": ev.get("end"),
                "organizer": ev.get("organizer"),
                "attendees": ev.get("attendees"),
                "hangout_link": ev.get("hangoutLink"),
                "resolution": resolution,
            }
        )
    return {"items": enriched, "count": len(enriched)}


@router.get("/events/{event_id}")
async def get_event(event_id: str) -> dict:
    ev = google_calendar_mock.find_event(event_id)
    if ev is None:
        raise HTTPException(status_code=404, detail="event not found")
    return {**ev, "resolution": company_resolver.resolve_event(ev)}
