"""
filename: google_calendar_mock.py
description: Mock Google Calendar feed shaped like Calendar API v3 events. The dashboard reads upcoming events here so the smart-resolver can show which customer each invite actually belongs to (consultants, observers, and internal stakeholders are filtered out).
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List


def _now() -> datetime:
    """Anchor at the actual current time so mock events always look upcoming."""
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def _build_events() -> List[Dict[str, Any]]:
    """Compose the mock event list lazily so offsets are anchored to real-time."""
    n = _now()
    return [
    # 1) Clean case: only Revolut + Elastic. Domain match wins.
    {
        "id": "gcal-evt-001",
        "summary": "Revolut x Elastic - observability cost & SIEM consolidation",
        "description": "Discovery call. Datadog renewal lands November 1. UK banking licence audit prep ongoing.",
        "start": {"dateTime": _iso(n + timedelta(hours=24))},
        "end": {"dateTime": _iso(n + timedelta(hours=24, minutes=45))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co", "responseStatus": "accepted"},
            {"email": "sarah.chen@revolut.com", "responseStatus": "accepted"},
            {"email": "mike.taylor@revolut.com", "responseStatus": "accepted"},
        ],
        "hangoutLink": "https://meet.google.com/fec-mock-rev-001",
    },
    # 2) Tricky: consultant from Accenture + the actual customer (Mercado Libre).
    # Resolver should prefer mercadolibre.com because Accenture is a known consulting firm.
    {
        "id": "gcal-evt-002",
        "summary": "MELI search relevance review - quarterly update",
        "description": "Quarterly review with Mercado Libre engineering and an Accenture observer team.",
        "start": {"dateTime": _iso(n + timedelta(hours=48))},
        "end": {"dateTime": _iso(n + timedelta(hours=49))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co"},
            {"email": "lucia.fernandez@mercadolibre.com"},
            {"email": "diego.alvarez@mercadolibre.com"},
            # Accenture consultant — should NOT be picked as the customer.
            {"email": "j.morales@accenture.com"},
            {"email": "another.consultant@accenture.com"},
        ],
        "hangoutLink": "https://meet.google.com/fec-mock-meli-001",
    },
    # 3) Multi-party: Santander + KPMG + Deloitte + Elastic.
    # Two consulting firms in the room; resolver should still pick Santander.
    {
        "id": "gcal-evt-003",
        "summary": "Santander Splunk renewal review - architecture council",
        "description": "Architecture council with Santander + KPMG advisory + Deloitte risk team.",
        "start": {"dateTime": _iso(n + timedelta(hours=144))},
        "end": {"dateTime": _iso(n + timedelta(hours=144, minutes=60))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co"},
            {"email": "carlos.ruiz@santander.com"},
            {"email": "marina.lopez@santander.com"},
            {"email": "advisor1@kpmg.com"},
            {"email": "risk.lead@deloitte.com"},
        ],
        "hangoutLink": "https://meet.google.com/fec-mock-san-001",
    },
    # 4) Ambiguous: only consultants + a freemail attendee. Title carries the customer name ("BBVA").
    # Resolver falls through domains (no match) and uses title-keyword fallback.
    {
        "id": "gcal-evt-004",
        "summary": "BBVA Mexico - intro call (via Capgemini)",
        "description": "Intro call brokered by Capgemini. BBVA contacts will dial in from a freemail.",
        "start": {"dateTime": _iso(n + timedelta(hours=72))},
        "end": {"dateTime": _iso(n + timedelta(hours=72, minutes=30))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co"},
            {"email": "broker.lead@capgemini.com"},
            {"email": "engagement.partner@capgemini.com"},
            {"email": "j.gomez99@gmail.com"},  # BBVA contact via personal mail
        ],
        "hangoutLink": "https://meet.google.com/fec-mock-bbva-001",
    },
    # 5) Internal-only event (no external attendees). Resolver should flag as "internal".
    {
        "id": "gcal-evt-005",
        "summary": "FE team weekly sync",
        "description": "Internal Elastic FE team weekly.",
        "start": {"dateTime": _iso(n + timedelta(hours=2))},
        "end": {"dateTime": _iso(n + timedelta(hours=2, minutes=45))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co"},
            {"email": "team.lead@elastic.co"},
            {"email": "regional.manager@elastic.co"},
        ],
    },
]



def list_upcoming_events(limit: int = 25) -> List[Dict[str, Any]]:
    """Return events whose end time is in the future."""
    now = datetime.now(timezone.utc)
    out: List[Dict[str, Any]] = []
    for ev in _build_events():
        try:
            end_dt = datetime.fromisoformat(ev["end"]["dateTime"])
        except Exception:
            continue
        if end_dt > now:
            out.append(ev)
    out.sort(key=lambda e: e["start"]["dateTime"])
    return out[:limit]


def find_event(event_id: str) -> Dict[str, Any] | None:
    return next((e for e in _build_events() if e["id"] == event_id), None)
