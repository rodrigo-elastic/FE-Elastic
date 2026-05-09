"""
filename: google_calendar_mock.py
description: Mock Google Calendar feed shaped like Calendar API v3 events. The dashboard reads upcoming events here so the smart-resolver can show which customer each invite actually belongs to (consultants, observers, and internal stakeholders are filtered out). All companies and consultants here are fictional demo data.
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
    # 1) Clean case: only Northwind Pay + Elastic. Domain match wins.
    {
        "id": "gcal-evt-001",
        "summary": "Northwind Pay x Elastic, observability cost & SIEM consolidation",
        "description": "Discovery call. Datadog renewal lands November 1. EU banking licence audit prep ongoing.",
        "start": {"dateTime": _iso(n + timedelta(hours=24))},
        "end": {"dateTime": _iso(n + timedelta(hours=24, minutes=45))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co", "responseStatus": "accepted"},
            {"email": "sarah.chen@northwindpay.example", "responseStatus": "accepted"},
            {"email": "mike.taylor@northwindpay.example", "responseStatus": "accepted"},
        ],
        "hangoutLink": "https://meet.google.com/fec-mock-nw-001",
    },
    # 2) Tricky: consultant from Pinnacle Consulting + the actual customer (Mercado Atlas).
    # Resolver should prefer mercadoatlas.example because Pinnacle Consulting is a known consulting firm.
    {
        "id": "gcal-evt-002",
        "summary": "Mercado Atlas search relevance review, quarterly update",
        "description": "Quarterly review with Mercado Atlas engineering and a Pinnacle Consulting observer team.",
        "start": {"dateTime": _iso(n + timedelta(hours=48))},
        "end": {"dateTime": _iso(n + timedelta(hours=49))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co"},
            {"email": "lucia.fernandez@mercadoatlas.example"},
            {"email": "diego.alvarez@mercadoatlas.example"},
            # Pinnacle Consulting consultant, should NOT be picked as the customer.
            {"email": "j.morales@pinnacleconsulting.example"},
            {"email": "another.consultant@pinnacleconsulting.example"},
        ],
        "hangoutLink": "https://meet.google.com/fec-mock-meli-001",
    },
    # 3) Searchlight Capital follow-up - the displacement-confirmation working session.
    {
        "id": "gcal-evt-003",
        "summary": "Searchlight Capital x Elastic, displacement review with CFO",
        "description": "60-day Splunk renewal lock; CFO Sandra Park bringing the TCO case to the renewal review.",
        "start": {"dateTime": _iso(n + timedelta(hours=72))},
        "end": {"dateTime": _iso(n + timedelta(hours=72, minutes=45))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co"},
            {"email": "priya.sharma@searchlightcap.example"},
            {"email": "james.liu@searchlightcap.example"},
            {"email": "sandra.park@searchlightcap.example"},
        ],
        "hangoutLink": "https://meet.google.com/fec-mock-slc-002",
    },
    # 4) Internal-only event (no external attendees). Resolver should flag as "internal".
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
    # Scheduler test event - always 30 min away so the auto-brief fires on check.
    {
        "id": "gcal-evt-scheduler-test",
        "summary": "Searchlight Capital x Elastic - Splunk displacement discovery",
        "description": "Splunk renewal in 60 days. DORA audit gap. Decision maker is CFO.",
        "start": {"dateTime": _iso(n + timedelta(minutes=30))},
        "end": {"dateTime": _iso(n + timedelta(minutes=75))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co", "responseStatus": "accepted"},
            {"email": "james.liu@searchlightcap.example", "responseStatus": "accepted"},
            {"email": "priya.sharma@searchlightcap.example", "responseStatus": "accepted"},
        ],
        "hangoutLink": "https://meet.google.com/fec-mock-slc-001",
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
