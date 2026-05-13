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
from app.repositories import synthetic
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
    from_email: str = ""
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
    """Scan runtime dirs + synthetic repo and return everything we have on the
    account: pre-meeting briefs, post-meeting records, scheduled meetings,
    open support tickets, news snippets, and the company dossier itself.

    Every record is timestamped where possible so the Claude prompt downstream
    can produce a real chronological handover instead of a vague summary."""
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

    # Synthetic enrichment: resolve the company id and pull the dossier,
    # upcoming/past meetings, open tickets, and recent news so the handover
    # has real dates and stakeholders to cite.
    company: Dict[str, Any] = {}
    upcoming: List[Dict[str, Any]] = []
    past: List[Dict[str, Any]] = []
    tickets: List[Dict[str, Any]] = []
    news: List[Dict[str, Any]] = []

    matched_company = None
    for c in synthetic.companies():
        if _matches(company_name, c.get("name", "")) or _matches(company_name, c.get("id", "")):
            matched_company = c
            break
    if matched_company:
        cid = matched_company.get("id", "")
        company = matched_company
        for m in synthetic.meetings():
            if m.get("company_id") != cid:
                continue
            (upcoming if m.get("is_upcoming") else past).append(m)
        tickets = synthetic.tickets_for(cid) or []
        news = synthetic.news_for(cid) or []

    # Pull explicit action items + MEDDPICC out of the post-meeting records so
    # the prompt sees them as first-class lists rather than buried in a blob.
    action_items: List[Dict[str, Any]] = []
    meddpicc: List[Dict[str, Any]] = []
    for pm in post_meetings:
        for ai in (pm.get("action_items") or []):
            if isinstance(ai, dict):
                action_items.append({**ai, "source_meeting": pm.get("meeting_id"), "source_date": pm.get("generated_at")})
        for sig in (pm.get("meddpicc_signals") or []):
            if isinstance(sig, dict):
                meddpicc.append({**sig, "source_meeting": pm.get("meeting_id"), "source_date": pm.get("generated_at")})

    return {
        "company": company,
        "briefs": briefs,
        "post_meetings": post_meetings,
        "upcoming_meetings": upcoming,
        "past_meetings": past,
        "tickets": tickets,
        "open_tickets": [t for t in tickets if (t.get("status") or "").lower() in ("open", "in_progress", "new")],
        "news": news[:8],
        "action_items": action_items,
        "meddpicc": meddpicc,
        "brief_count": len(briefs),
        "pm_count": len(post_meetings),
        "upcoming_count": len(upcoming),
        "past_count": len(past),
        "open_ticket_count": sum(1 for t in tickets if (t.get("status") or "").lower() in ("open", "in_progress", "new")),
        "action_item_count": len(action_items),
        "meddpicc_count": len(meddpicc),
    }


def _list_known_accounts() -> List[Dict[str, Any]]:
    """Union of accounts from synthetic + disk briefs + disk post-meetings.
    Powers the autocomplete on the workspace handover modal so the FE can
    only pick accounts the system actually has data on."""
    seen: Dict[str, Dict[str, Any]] = {}

    def _add(name: str, source: str, company_id: str = ""):
        if not name:
            return
        key = name.strip().lower()
        if key in seen:
            seen[key]["sources"].add(source)
            return
        seen[key] = {
            "name": name.strip(),
            "id": company_id or _slug(name),
            "sources": {source},
        }

    for c in synthetic.companies():
        _add(c.get("name", ""), "synthetic", c.get("id", ""))

    briefs_dir = settings.runtime_dir / "briefs"
    if briefs_dir.exists():
        for p in briefs_dir.glob("*.json"):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            _add(rec.get("company_name") or rec.get("company_id") or "", "brief")

    pm_dir = settings.runtime_dir / "post_meeting"
    if pm_dir.exists():
        for p in pm_dir.glob("*.json"):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            _add(rec.get("company_name") or rec.get("company_id") or "", "post_meeting")

    out = []
    for v in seen.values():
        v["sources"] = sorted(v["sources"])
        out.append(v)
    out.sort(key=lambda x: x["name"].lower())
    return out


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
        "You are preparing a thorough account handover document for a new Customer "
        "Architect (CA) taking over from a Solutions Architect (SA). The CA needs "
        "enough context to walk into the next call without re-reading every record. "
        "Write a long, specific, evidence-cited document with these sections:\n"
        "1) Account Overview (industry, size, tech stack, why Elastic is in the picture)\n"
        "2) Chronological Timeline - every interaction with an ISO date, format `YYYY-MM-DD: <event>`. "
        "Include every brief, post-meeting, upcoming meeting, and ticket open/close event you can find.\n"
        "3) Key Stakeholders - name, title, email if known, role on the deal (champion / economic buyer / blocker / technical).\n"
        "4) Open Action Items - one per line: `[OWNER] DUE YYYY-MM-DD - title (impact: low|med|high)` followed by a one-sentence description. List ALL of them; do not summarise.\n"
        "5) Deal Status - MEDDPICC signals if available, opportunity stage, ARR, renewal date, competitor incumbents.\n"
        "6) Open Support Tickets - subject, priority, status, age. Flag anything P1 / open more than 14 days.\n"
        "7) Risks and Watchouts - what the new CA should not say, deadlines they must hit, dependencies they inherit.\n"
        "8) Recommended Next Three Actions - concrete, time-boxed, owner-assigned.\n\n"
        "Hard rules:\n"
        "- Use only the data provided. Do NOT invent stakeholder names, dates, or facts.\n"
        "- Every concrete claim must reference an ISO date or a meeting id.\n"
        "- Plain ASCII punctuation only. No em dashes, no smart quotes.\n"
        "- If a section has no data, write 'No data on file' rather than making something up.\n"
        "- The document goes to a human reading on their phone. Be skimmable: short bullets, bold section headers, no walls of prose."
    )

    company_ctx = json.dumps(account_data.get("company") or {}, indent=2, ensure_ascii=False)
    brief_ctx = json.dumps(account_data["briefs"], indent=2, ensure_ascii=False)
    pm_ctx = json.dumps(account_data["post_meetings"], indent=2, ensure_ascii=False)
    upcoming_ctx = json.dumps(account_data.get("upcoming_meetings") or [], indent=2, ensure_ascii=False)
    past_ctx = json.dumps(account_data.get("past_meetings") or [], indent=2, ensure_ascii=False)
    tickets_ctx = json.dumps(account_data.get("tickets") or [], indent=2, ensure_ascii=False)
    news_ctx = json.dumps(account_data.get("news") or [], indent=2, ensure_ascii=False)
    action_items_ctx = json.dumps(account_data.get("action_items") or [], indent=2, ensure_ascii=False)
    meddpicc_ctx = json.dumps(account_data.get("meddpicc") or [], indent=2, ensure_ascii=False)

    to_line = f"New owner: {to_name}" if to_name else ""
    notes_line = f"Additional context from {from_name}: {notes}" if notes else ""

    user_parts = [
        f"Account: {company_name}",
        f"Handover from: {from_name}",
        to_line,
        notes_line,
        "",
        "=== COMPANY DOSSIER ===",
        company_ctx,
        "",
        f"=== PRE-MEETING BRIEFS ({account_data['brief_count']}) ===",
        brief_ctx,
        "",
        f"=== POST-MEETING RECORDS ({account_data['pm_count']}) ===",
        pm_ctx,
        "",
        f"=== UPCOMING MEETINGS ({account_data.get('upcoming_count', 0)}) ===",
        upcoming_ctx,
        "",
        f"=== PAST MEETINGS ({account_data.get('past_count', 0)}) ===",
        past_ctx,
        "",
        f"=== ACTION ITEMS EXTRACTED ({account_data.get('action_item_count', 0)}) ===",
        action_items_ctx,
        "",
        f"=== MEDDPICC SIGNALS ({account_data.get('meddpicc_count', 0)}) ===",
        meddpicc_ctx,
        "",
        f"=== SUPPORT TICKETS (open: {account_data.get('open_ticket_count', 0)}) ===",
        tickets_ctx,
        "",
        f"=== RECENT NEWS ({len(account_data.get('news') or [])}) ===",
        news_ctx,
        "",
        "Generate the full account handover document now.",
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

    # get_service() now returns ElasticInferenceService (Kibana-routed) which
    # wraps a direct ClaudeService at `._direct`. Reach for the inner
    # ClaudeService when we need raw access to the Anthropic SDK client; the
    # handover doc is plain text, not structured, so we bypass the
    # structured-call paths and call messages.create directly.
    inner = getattr(svc, "_direct", svc)
    client: Anthropic = getattr(inner, "_client", None)
    if client is None:
        raise RuntimeError(
            "Anthropic client not available. Set ANTHROPIC_API_KEY or run in mock mode."
        )

    # Bumped from 1500 to 4000 tokens because the new prompt asks for a
    # chronological timeline + every action item + MEDDPICC + tickets, which
    # consistently runs longer than the old vague summary.
    response = client.messages.create(
        model=MODEL_HAIKU,
        max_tokens=4000,
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


@router.get("/accounts")
async def list_accounts() -> Dict[str, Any]:
    """List every account the system has data on. Powers the handover modal's
    autocomplete so the FE can only pick accounts that actually exist."""
    accounts = _list_known_accounts()
    return {"accounts": accounts, "count": len(accounts)}


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

    # 3. Send emails. Two messages with different framings:
    #    a) Recipient (the CA) gets the full handover doc + intro framed as
    #       "this account is now yours; here's everything we know".
    #    b) Sender (the SA who triggered) gets a confirmation copy with the
    #       same doc body + a header framed as "you just handed off X; the
    #       receiving CA got the doc below".
    slug = _slug(req.company_name)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    deliveries: List[Dict[str, Any]] = []

    recipient_intro = (
        f"Hi {req.to_name or 'CA'},\n\n"
        f"{req.from_name} has handed over the {req.company_name} account to you. "
        f"The full context below was generated from {account_data['brief_count']} "
        f"pre-meeting brief(s) and {account_data['pm_count']} post-meeting "
        "record(s) plus all current ticket and renewal signals on file.\n\n"
        f"Reply to {req.from_email or req.from_name} with any handover questions.\n\n"
        "---\n\n"
    )
    recipient_subject = f"Account Handover - {req.company_name}"
    recipient_body = recipient_intro + handover_text
    recipient_result = email_sender.send(
        to=req.to_email,
        subject=recipient_subject,
        body_markdown=recipient_body,
        meeting_id=f"handover-{slug}-{ts}-to-ca",
    )
    deliveries.append({
        "role": "recipient",
        "to": req.to_email,
        "subject": recipient_subject,
        "body": recipient_body,
        **recipient_result,
    })

    if req.from_email and req.from_email.strip():
        sender_intro = (
            f"Hi {req.from_name},\n\n"
            f"Confirming you handed off the {req.company_name} account to "
            f"{req.to_name or req.to_email} at {req.to_email}.\n\n"
            f"They received {account_data['brief_count']} brief(s), "
            f"{account_data['pm_count']} post-meeting record(s), "
            f"{account_data.get('open_ticket_count', 0)} open ticket(s), "
            f"and {account_data.get('action_item_count', 0)} extracted action item(s). "
            "Same document below for your records.\n\n"
            "---\n\n"
        )
        sender_subject = f"[Copy] Account Handover sent - {req.company_name}"
        sender_body = sender_intro + handover_text
        sender_result = email_sender.send(
            to=req.from_email,
            subject=sender_subject,
            body_markdown=sender_body,
            meeting_id=f"handover-{slug}-{ts}-confirm",
        )
        deliveries.append({
            "role": "sender_copy",
            "to": req.from_email,
            "subject": sender_subject,
            "body": sender_body,
            **sender_result,
        })

    # 4. Slack notification
    slack_mock.post_message(
        channel="#fe-copilot",
        text=(
            f":handshake: Account handover triggered for *{req.company_name}*"
            f" -> {req.to_email}"
            + (f" (from {req.from_name})" if req.from_name and req.from_name != "SA" else "")
            + (f", copy to {req.from_email}" if req.from_email else "")
        ),
    )

    log.info(
        "handover.generate.done",
        company=req.company_name,
        to=req.to_email,
        cc=req.from_email or None,
        briefs=account_data["brief_count"],
        post_meetings=account_data["pm_count"],
    )

    return {
        "ok": True,
        "company_name": req.company_name,
        "to_email": req.to_email,
        "from_email": req.from_email or None,
        "deliveries": deliveries,
        "handover": handover_text,
        "brief_count": account_data["brief_count"],
        "pm_count": account_data["pm_count"],
    }
