"""
filename: brief_scheduler.py
description: Background asyncio task that fires a continuity Slack message
30 minutes before every external calendar meeting. The message shows what was
covered in previous meetings with that customer and which action items are still
open - no Claude API call, just your own data surfaced at the right moment.
date: 08-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Set

from app.integrations import google_calendar_mock, slack_mock
from app.utils.logging import get_logger

log = get_logger(__name__)

WINDOW_MIN_LO = 25
WINDOW_MIN_HI = 35
CHECK_INTERVAL_SEC = 300

_processed: Set[str] = set()
_INTERNAL_DOMAINS = {"elastic.co", "elasticco.onmicrosoft.com"}
_CONSULTING_RE = re.compile(
    r"consulting|advisory|partners|accenture|deloitte|pwc|kpmg|mckinsey|pinnacle",
    re.IGNORECASE,
)


def _extract_company(ev: Dict[str, Any]) -> str:
    domain_counts: Dict[str, int] = {}
    for att in (ev.get("attendees") or []):
        email = att.get("email", "")
        if not email or "@" not in email:
            continue
        domain = email.split("@", 1)[1].lower()
        if domain in _INTERNAL_DOMAINS or _CONSULTING_RE.search(domain):
            continue
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    if not domain_counts:
        return ""
    top = max(domain_counts, key=domain_counts.__getitem__)
    return top.split(".")[0].replace("-", " ").title()


def _load_post_meetings() -> List[Dict[str, Any]]:
    """Load all post-meeting records from disk, newest first."""
    from app.config import settings
    out = []
    pm_dir = settings.runtime_dir / "post_meeting"
    if not pm_dir.exists():
        return out
    for p in sorted(pm_dir.glob("*.json"), reverse=True):
        try:
            out.append(json.loads(p.read_text()))
        except Exception:
            continue

    # Best-effort: merge ES records not already on disk.
    try:
        from app.repositories.elasticsearch_repo import get_repo
        es = get_repo()
        if es.available:
            existing_ids = {r.get("meeting_id") for r in out}
            for rec in es.list_post_meetings(limit=200):
                if rec.get("meeting_id") not in existing_ids:
                    out.append(rec)
    except Exception:
        pass

    return out


def _history_for(company: str) -> List[Dict[str, Any]]:
    """Return post-meeting records that match this company, newest first."""
    needle = company.lower().replace(" ", "")
    records = []
    for rec in _load_post_meetings():
        name = (rec.get("company_name") or rec.get("company_id") or "").lower().replace(" ", "")
        if needle in name or name in needle:
            records.append(rec)
    return records


def _minutes_to(ev: Dict[str, Any]) -> int:
    try:
        start = datetime.fromisoformat(ev["start"]["dateTime"])
        return int((start - datetime.now(timezone.utc)).total_seconds() / 60)
    except Exception:
        return 0


def _build_slack_message(company: str, ev: Dict[str, Any], history: List[Dict[str, Any]]) -> str:
    mins = _minutes_to(ev)
    title = ev.get("summary", "Meeting")
    invite_context = (ev.get("description") or "").strip()

    lines = [
        f":calendar: *{company} - in {mins} min*",
        f"_{title}_",
    ]

    if history:
        last = history[0]
        last_date = (last.get("generated_at") or "")[:10]
        summary = (last.get("summary") or "").strip()
        # Keep summary to 2 sentences max.
        sentences = re.split(r"(?<=[.!?])\s+", summary)
        short_summary = " ".join(sentences[:2])

        lines += [
            "",
            f"*Last meeting ({last_date}):*",
            short_summary,
        ]

        # Collect open action items across all past meetings (no done/closed flag).
        open_items: List[Dict[str, Any]] = []
        seen_titles: Set[str] = set()
        for rec in history:
            for item in (rec.get("action_items") or []):
                t = item.get("title", "")
                if t and t not in seen_titles:
                    seen_titles.add(t)
                    open_items.append(item)

        if open_items:
            lines += ["", "*Open tasks:*"]
            for item in open_items[:5]:
                owner = item.get("owner_name") or item.get("owner") or "unassigned"
                due = item.get("due_date") or ""
                impact_marker = ":red_circle:" if str(item.get("impact", "")).lower() == "high" else ":white_circle:"
                due_str = f" - due {due}" if due else ""
                lines.append(f"  {impact_marker} {item['title']} ({owner}{due_str})")

    else:
        lines += ["", "_No previous meetings on record for this account._"]

    if invite_context:
        lines += ["", "*Today's agenda (from invite):*", invite_context[:300]]

    return "\n".join(lines)


async def check_and_brief() -> Dict[str, Any]:
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
            skipped.append({"event_id": ev_id, "reason": "already-sent"})
            continue

        company = _extract_company(ev)
        if not company:
            skipped.append({"event_id": ev_id, "reason": "no-external-attendees"})
            continue

        _processed.add(ev_id)
        history = _history_for(company)
        message = _build_slack_message(company, ev, history)

        log.info("brief_scheduler.sending", event_id=ev_id, company=company,
                 past_meetings=len(history))
        result = slack_mock.post_message(channel="#fe-copilot-briefs", text=message)
        triggered.append({
            "event_id": ev_id,
            "company": company,
            "past_meetings": len(history),
            "open_tasks": sum(len(r.get("action_items") or []) for r in history),
            "slack": result,
        })

    return {
        "checked_at": now.isoformat(),
        "window": f"+{WINDOW_MIN_LO}-{WINDOW_MIN_HI} min",
        "events_in_window": len(triggered) + len(skipped),
        "triggered": triggered,
        "skipped": skipped,
    }


async def scheduler_loop() -> None:
    log.info("brief_scheduler.started", interval_sec=CHECK_INTERVAL_SEC)
    while True:
        try:
            summary = await check_and_brief()
            if summary["triggered"]:
                log.info("brief_scheduler.cycle", **summary)
        except Exception as exc:
            log.warning("brief_scheduler.cycle_error", error=str(exc))
        await asyncio.sleep(CHECK_INTERVAL_SEC)
