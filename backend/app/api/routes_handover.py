"""
filename: routes_handover.py
description: SA-to-CA account handover. Collects briefs and post-meeting records
for a named account, calls Claude to generate a structured handover document,
emails it to the incoming CA/AE, and fires a Slack notification.
date: 08-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.integrations import email_sender, slack_mock
from app.integrations.claude_client import MODEL_HAIKU, get_service
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/handover", tags=["handover"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class HandoverRequest(BaseModel):
    company_name: str
    to_email: str
    to_name: str = ""
    from_name: str = "SA"
    notes: str = ""


# ---------------------------------------------------------------------------
# Helper: collect account data from disk
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lower-case, collapse whitespace for fuzzy matching."""
    return re.sub(r"\s+", " ", text.strip().lower())


def _matches(name: str, target: str) -> bool:
    """Return True when `name` is a substring of `target` or vice versa."""
    n = _normalize(name)
    t = _normalize(target)
    return n in t or t in n


def _collect_account_data(company_name: str) -> Dict[str, Any]:
    """Scan runtime dirs and return all records that match `company_name`."""
    briefs_dir: Path = settings.runtime_dir / "briefs"
    pm_dir: Path = settings.runtime_dir / "post_meeting"

    briefs: List[Dict[str, Any]] = []
    post_meetings: List[Dict[str, Any]] = []

    if briefs_dir.exists():
        for p in sorted(briefs_dir.glob("*.json")):
            try:
                rec: Dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            candidate = rec.get("company_name") or rec.get("company_id") or ""
            if _matches(company_name, candidate):
                briefs.append(rec)

    if pm_dir.exists():
        for p in sorted(pm_dir.glob("*.json")):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            candidate = rec.get("company_name") or rec.get("company_id") or ""
            if _matches(company_name, candidate):
                post_meetings.append(rec)

    return {
        "briefs": briefs,
        "post_meetings": post_meetings,
        "brief_count": len(briefs),
        "pm_count": len(post_meetings),
    }


# ---------------------------------------------------------------------------
# Helper: build handover text via Claude
# ---------------------------------------------------------------------------


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", _normalize(text)).strip("-")


def _build_handover(
    *,
    company_name: str,
    to_name: str,
    from_name: str,
    notes: str,
    account_data: Dict[str, Any],
) -> str:
    """Call Claude (Haiku) and return the handover document as plain text."""
    system = (
        "You are preparing a structured account handover document for a new Customer Advocate"
        " (CA) taking over from a Solutions Architect (SA). Write a clear, concise handover"
        " with these sections:\n"
        "1) Account Overview\n"
        "2) Relationship History (chronological)\n"
        "3) Open Action Items\n"
        "4) Key Stakeholders\n"
        "5) Deal Status and Next Steps\n"
        "6) Risks and Watchouts\n"
        "Use only the data provided. Be direct and specific. Do not invent information."
        " Use plain ASCII punctuation - no em dashes or special characters."
    )

    brief_ctx = json.dumps(account_data["briefs"], indent=2, ensure_ascii=False)
    pm_ctx = json.dumps(account_data["post_meetings"], indent=2, ensure_ascii=False)

    to_line = f"New owner: {to_name}" if to_name else ""
    notes_line = f"Additional context from {from_name}: {notes}" if notes else ""

    user_parts = [
        f"Account: {company_name}",
        f"Handover from: {from_name}",
        to_line,
        notes_line,
        "",
        f"=== PRE-MEETING BRIEFS ({account_data['brief_count']}) ===",
        brief_ctx,
        "",
        f"=== POST-MEETING RECORDS ({account_data['pm_count']}) ===",
        pm_ctx,
        "",
        "Generate the account handover document now.",
    ]
    user = "\n".join(p for p in user_parts if p is not None)

    svc = get_service()

    if svc.mock_mode:
        # Return a deterministic stub so the feature works in offline / demo mode.
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return (
            f"ACCOUNT HANDOVER - {company_name.upper()}\n"
            f"Generated: {ts}\n"
            f"From: {from_name}  ->  To: {to_name or 'CA'}\n\n"
            "1) ACCOUNT OVERVIEW\n"
            f"   {company_name} is an active Elastic account.\n\n"
            "2) RELATIONSHIP HISTORY\n"
            f"   {account_data['brief_count']} brief(s) and"
            f" {account_data['pm_count']} post-meeting record(s) on file.\n\n"
            "3) OPEN ACTION ITEMS\n"
            "   See post-meeting records for full action item list.\n\n"
            "4) KEY STAKEHOLDERS\n"
            "   See meeting briefs for stakeholder details.\n\n"
            "5) DEAL STATUS AND NEXT STEPS\n"
            "   Review Salesforce for current opportunity stage.\n\n"
            "6) RISKS AND WATCHOUTS\n"
            "   No critical risks flagged at handover time.\n"
            + (f"\nNotes from {from_name}: {notes}\n" if notes else "")
        )

    from anthropic import Anthropic  # noqa: PLC0415

    client: Anthropic = svc._client  # type: ignore[attr-defined]

    response = client.messages.create(
        model=MODEL_HAIKU,
        max_tokens=1500,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
    )

    text = ""
    for block in response.content:
        if getattr(block, "type", None) == "text":
            text = block.text
            break

    if not text:
        raise RuntimeError("Claude returned an empty response for the handover document.")

    return text


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/preview/{company_name}")
async def preview_account(company_name: str) -> Dict[str, Any]:
    """Return the data that would be included in a handover, without generating it.

    Useful for the UI to show how many records exist before the SA sends.
    """
    data = _collect_account_data(company_name)
    return {
        "company_name": company_name,
        "brief_count": data["brief_count"],
        "pm_count": data["pm_count"],
        "brief_ids": [b.get("meeting_id") for b in data["briefs"]],
        "pm_ids": [p.get("meeting_id") for p in data["post_meetings"]],
    }


@router.post("/generate")
async def generate_handover(req: HandoverRequest) -> Dict[str, Any]:
    """Generate and deliver the SA-to-CA account handover document.

    Steps:
    1. Collect briefs + post-meeting records for the named account.
    2. Call Claude (Haiku) to write the structured handover.
    3. Email the document to the incoming CA/AE.
    4. Fire a Slack notification.
    5. Return the handover text and counts to the caller.
    """
    if not req.company_name.strip():
        raise HTTPException(status_code=422, detail="company_name is required")
    if not req.to_email.strip():
        raise HTTPException(status_code=422, detail="to_email is required")

    log.info(
        "handover.generate.start",
        company=req.company_name,
        to=req.to_email,
    )

    # 1. Collect data
    account_data = _collect_account_data(req.company_name)

    # 2. Build the handover document
    try:
        handover_text = _build_handover(
            company_name=req.company_name,
            to_name=req.to_name,
            from_name=req.from_name,
            notes=req.notes,
            account_data=account_data,
        )
    except Exception as exc:
        log.error("handover.claude_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Claude error: {exc}") from exc

    # 3. Send email
    slug = _slug(req.company_name)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    email_sender.send(
        to=req.to_email,
        subject=f"Account Handover: {req.company_name}",
        body_markdown=handover_text,
        meeting_id=f"handover-{slug}-{ts}",
    )

    # 4. Slack notification
    slack_mock.post_message(
        channel="#fe-copilot",
        text=(
            f":handshake: Account handover triggered for *{req.company_name}*"
            f" -> {req.to_email}"
            + (f" (from {req.from_name})" if req.from_name and req.from_name != "SA" else "")
        ),
    )

    log.info(
        "handover.generate.done",
        company=req.company_name,
        to=req.to_email,
        briefs=account_data["brief_count"],
        post_meetings=account_data["pm_count"],
    )

    return {
        "ok": True,
        "company_name": req.company_name,
        "to_email": req.to_email,
        "handover": handover_text,
        "brief_count": account_data["brief_count"],
        "pm_count": account_data["pm_count"],
    }
