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
    # 3) Multi-party: Banco Atlántico + Helix Advisory + Apex Advisory + Elastic.
    # Two consulting firms in the room; resolver should still pick Banco Atlántico.
    {
        "id": "gcal-evt-003",
        "summary": "Banco Atlántico Splunk renewal review, architecture council",
        "description": "Architecture council with Banco Atlántico + Helix Advisory + Apex Advisory risk team.",
        "start": {"dateTime": _iso(n + timedelta(hours=144))},
        "end": {"dateTime": _iso(n + timedelta(hours=144, minutes=60))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co"},
            {"email": "carlos.ruiz@bancoatlantico.example"},
            {"email": "marina.lopez@bancoatlantico.example"},
            {"email": "advisor1@helixadvisory.example"},
            {"email": "risk.lead@apexadvisory.example"},
        ],
        "hangoutLink": "https://meet.google.com/fec-mock-atl-001",
    },
    # 4) Ambiguous: only consultants + a freemail attendee. Title carries the customer name ("Fjordbank").
    # Resolver falls through domains (no match) and uses title-keyword fallback.
    {
        "id": "gcal-evt-004",
        "summary": "Fjordbank Mexico, intro call (via Vega Consulting)",
        "description": "Intro call brokered by Vega Consulting. Fjordbank contacts will dial in from a freemail.",
        "start": {"dateTime": _iso(n + timedelta(hours=72))},
        "end": {"dateTime": _iso(n + timedelta(hours=72, minutes=30))},
        "organizer": {"email": "rodrigo.careaga@elastic.co"},
        "attendees": [
            {"email": "rodrigo.careaga@elastic.co"},
            {"email": "broker.lead@vegaconsulting.example"},
            {"email": "engagement.partner@vegaconsulting.example"},
            {"email": "j.gomez99@freemail.example"},  # Fjordbank contact via personal mail (RFC 2606 reserved domain)
        ],
        "hangoutLink": "https://meet.google.com/fec-mock-fjord-001",
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
