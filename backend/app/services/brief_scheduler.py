"""
filename: brief_scheduler.py
description: Background asyncio task that polls the calendar every 5 minutes and
auto-generates a pre-meeting brief for any event starting in 25-35 minutes.
Slack notification fires automatically via pre_meeting.run_ad_hoc.
date: 08-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Set

from app.agents.pre_meeting import PreMeetingAgent
from app.integrations import google_calendar_mock
from app.utils.logging import get_logger

log = get_logger(__name__)

# Window: generate brief when meeting starts in [WINDOW_MIN_LO, WINDOW_MIN_HI] minutes.
WINDOW_MIN_LO = 25
WINDOW_MIN_HI = 35
CHECK_INTERVAL_SEC = 300  # 5 min

# In-memory dedup set - resets on restart, which is fine for a demo.
_processed: Set[str] = set()
_agent = PreMeetingAgent()

# Internal domain suffix - emails from these are Elastic employees, not customers.
_INTERNAL_DOMAINS = {"elastic.co", "elasticco.onmicrosoft.com"}

_CONSULTING_KEYWORDS = re.compile(
    r"consulting|advisory|partners|accenture|deloitte|pwc|kpmg|mckinsey|pinnacle",
    re.IGNORECASE,
)


def _extract_company(ev: Dict[str, Any]) -> str:
    """Guess the customer company from attendee email domains. Returns empty string if unclear."""
    attendees = ev.get("attendees") or []
    domain_counts: Dict[str, int] = {}
    for att in attendees:
        email = att.get("email", "")
        if not email or "@" not in email:
            continue
        domain = email.split("@", 1)[1].lower()
        if domain in _INTERNAL_DOMAINS:
            continue
        if _CONSULTING_KEYWORDS.search(domain):
            continue
        domain_counts[domain] = domain_counts.get(domain, 0) + 1

    if not domain_counts:
        return ""
    # Take the most common external domain; strip TLD for a readable company name.
    top_domain = max(domain_counts, key=domain_counts.__getitem__)
    company = top_domain.split(".")[0].replace("-", " ").title()
    return company


async def check_and_brief() -> Dict[str, Any]:
    """Check the calendar window and generate briefs for matching events.
    Safe to call manually (test endpoint) and from the scheduler loop.
    Returns a summary dict."""
    now = datetime.now(timezone.utc)
    window_lo = now + timedelta(minutes=WINDOW_MIN_LO)
    window_hi = now + timedelta(minutes=WINDOW_MIN_HI)

    events = google_calendar_mock.list_upcoming_events()
    triggered = []
    skipped = []

    for ev in events:
        try:
            start_dt = datetime.fromisoformat(ev["start"]["dateTime"])
        except Exception:
            continue

        if not (window_lo <= start_dt <= window_hi):
            continue

        ev_id = ev["id"]
        if ev_id in _processed:
            skipped.append({"event_id": ev_id, "reason": "already-processed"})
            continue

        company = _extract_company(ev)
        if not company:
            skipped.append({"event_id": ev_id, "reason": "no-external-attendees"})
            continue

        _processed.add(ev_id)
        log.info("brief_scheduler.generating", event_id=ev_id, company=company,
                 start=ev["start"]["dateTime"])
        try:
            result = await _agent.run_ad_hoc({
                "company_name": company,
                "meeting_title": ev.get("summary", ""),
                "notes": (ev.get("description") or "")[:500],
            })
            triggered.append({
                "event_id": ev_id,
                "company": company,
                "meeting_id": result.get("meeting_id"),
            })
            log.info("brief_scheduler.done", event_id=ev_id, company=company)
        except Exception as exc:
            log.warning("brief_scheduler.failed", event_id=ev_id, error=str(exc))
            _processed.discard(ev_id)
            skipped.append({"event_id": ev_id, "reason": str(exc)})

    return {
        "checked_at": now.isoformat(),
        "window": f"+{WINDOW_MIN_LO}-{WINDOW_MIN_HI} min",
        "events_in_window": len(triggered) + len(skipped),
        "triggered": triggered,
        "skipped": skipped,
    }


async def scheduler_loop() -> None:
    """Long-running asyncio task. Started from the FastAPI lifespan."""
    log.info("brief_scheduler.started", interval_sec=CHECK_INTERVAL_SEC)
    while True:
        try:
            summary = await check_and_brief()
            if summary["triggered"]:
                log.info("brief_scheduler.cycle", **summary)
        except Exception as exc:
            log.warning("brief_scheduler.cycle_error", error=str(exc))
        await asyncio.sleep(CHECK_INTERVAL_SEC)
