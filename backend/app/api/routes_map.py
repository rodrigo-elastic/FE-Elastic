"""
filename: routes_map.py
description: Mutual Action Plan (MAP) endpoints. Generates, persists, mutates,
emails, and PDF-renders a joint SA + customer-champion 90-day plan.
date: 05-13-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.map_agent import MapAgent
from app.config import settings
from app.integrations import email_sender
from app.services import pdf_builder
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/map", tags=["map"])


# ============================================================ models ===================


class FromMeetingBody(BaseModel):
    target_close_date: Optional[str] = None
    deal_value_usd: Optional[float] = None
    regenerate: bool = False


class AdHocBody(BaseModel):
    company_name: str
    industry: Optional[str] = None
    size: Optional[str] = None
    target_close_date: Optional[str] = None
    deal_value_usd: Optional[float] = None
    notes: Optional[str] = None


class MilestonePatch(BaseModel):
    status: Optional[str] = None
    date: Optional[str] = None
    owner_elastic: Optional[str] = None
    owner_customer: Optional[str] = None
    blocker_note: Optional[str] = None
    title: Optional[str] = None


class ShareBody(BaseModel):
    customer_email: Optional[str] = ""
    sa_email: Optional[str] = ""


# ============================================================ helpers ==================


def _map_dir() -> Path:
    return settings.runtime_dir / "map"


def _map_path(meeting_id: str) -> Path:
    return _map_dir() / f"{meeting_id}.json"


def _load(meeting_id: str) -> dict:
    p = _map_path(meeting_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"MAP not found for meeting_id={meeting_id}")
    return json.loads(p.read_text(encoding="utf-8"))


def _save(record: dict) -> None:
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    out = _map_dir()
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{record['meeting_id']}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _render_markdown(record: dict) -> str:
    plan = record.get("plan") or {}
    lines = [
        f"# Mutual Action Plan: {record.get('company_name')}",
        "",
        f"**Target close**: {plan.get('target_close_date', '')}  ",
        f"**Status**: {record.get('status', 'draft')}  ",
        f"**Last update**: {record.get('updated_at', '')}",
        "",
        "## Goal",
        plan.get("goal", ""),
        "",
        f"**Success metric**: {plan.get('success_metric', '')}",
        "",
        "## Stakeholders",
    ]
    for s in plan.get("stakeholders", []) or []:
        lines.append(f"- **{s.get('name')}** ({s.get('role')}, {s.get('stance')}): {s.get('notes') or s.get('title') or ''}")
    lines += ["", "## Workstreams"]
    for w in plan.get("workstreams", []) or []:
        lines.append(f"- **{w.get('title')}** [{w.get('status')}] - Elastic: {w.get('owner_elastic')} / Customer: {w.get('owner_customer')}")
        lines.append(f"  {w.get('description')}")
    lines += ["", "## Milestones"]
    for m in plan.get("milestones", []) or []:
        lines.append(
            f"- {m.get('date')} - **{m.get('title')}** [{m.get('status')}] (Elastic: {m.get('owner_elastic')} / Customer: {m.get('owner_customer')})"
        )
        if m.get("blocker_note"):
            lines.append(f"    Blocker if missed: {m.get('blocker_note')}")
    lines += ["", "## Risks"]
    for r in plan.get("risks", []) or []:
        lines.append(f"- [{r.get('severity')}] **{r.get('title')}**: {r.get('description')} (Mitigation: {r.get('mitigation')})")
    cadence = plan.get("cadence") or {}
    lines += [
        "",
        "## Communication cadence",
        f"- Weekly sync: {cadence.get('weekly_sync', '')}",
        f"- MAP review: {cadence.get('map_review_cadence', '')}",
        f"- Escalation: {cadence.get('escalation_path', '')}",
    ]
    return "\n".join(lines)


# ============================================================ endpoints ================


@router.post("/from-meeting/{meeting_id}")
async def from_meeting(meeting_id: str, body: FromMeetingBody) -> dict:
    """Generate a MAP from the meeting dossier + brief + post-meeting record.

    Idempotent: returns the persisted MAP unless regenerate=true is set.
    """
    existing = _map_path(meeting_id)
    if existing.exists() and not body.regenerate:
        return json.loads(existing.read_text(encoding="utf-8"))
    agent = MapAgent()
    return await agent.run(
        {
            "meeting_id": meeting_id,
            "target_close_date": body.target_close_date,
            "deal_value_usd": body.deal_value_usd,
        }
    )


@router.post("/ad-hoc")
async def ad_hoc(body: AdHocBody) -> dict:
    """Generate a MAP from user-typed input (no synthetic meeting required)."""
    agent = MapAgent()
    return await agent.run_ad_hoc(body.model_dump())


@router.get("")
async def list_maps() -> dict:
    """List every MAP on disk."""
    out = []
    d = _map_dir()
    if d.exists():
        for p in d.glob("*.json"):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            plan = rec.get("plan") or {}
            out.append(
                {
                    "meeting_id": rec.get("meeting_id"),
                    "company_name": rec.get("company_name"),
                    "target_close_date": plan.get("target_close_date"),
                    "status": rec.get("status"),
                    "updated_at": rec.get("updated_at"),
                    "ad_hoc": bool(rec.get("ad_hoc")),
                }
            )
    out.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {"items": out}


@router.get("/{meeting_id}")
async def get_map(meeting_id: str) -> dict:
    p = _map_path(meeting_id)
    if not p.exists():
        return {"exists": False, "meeting_id": meeting_id}
    rec = json.loads(p.read_text(encoding="utf-8"))
    rec["exists"] = True
    return rec


@router.put("/{meeting_id}/milestone/{milestone_id}")
async def update_milestone(meeting_id: str, milestone_id: str, body: MilestonePatch) -> dict:
    rec = _load(meeting_id)
    plan = rec.setdefault("plan", {})
    milestones = plan.get("milestones") or []
    target = None
    for m in milestones:
        if m.get("id") == milestone_id:
            target = m
            break
    if target is None:
        raise HTTPException(status_code=404, detail=f"milestone {milestone_id} not found")
    patch = body.model_dump(exclude_unset=True)
    if "status" in patch and patch["status"] not in {"not_started", "in_progress", "blocked", "done", None}:
        raise HTTPException(status_code=422, detail=f"invalid status: {patch['status']}")
    for k, v in patch.items():
        if v is not None:
            target[k] = v
    _save(rec)
    return {"ok": True, "milestone": target, "updated_at": rec["updated_at"]}


@router.post("/{meeting_id}/share")
async def share_map(meeting_id: str, body: ShareBody) -> dict:
    rec = _load(meeting_id)
    subject = f"Mutual Action Plan: {rec.get('company_name')}"
    body_md = _render_markdown(rec)
    results = []
    for to in [body.customer_email, body.sa_email]:
        to = (to or "").strip()
        if not to:
            continue
        try:
            r = email_sender.send(to=to, subject=subject, body_markdown=body_md, meeting_id=meeting_id)
            results.append({"to": to, "ok": True, "mode": r.get("mode")})
        except Exception as exc:
            log.warning("map.share_failed", meeting_id=meeting_id, to=to, error=str(exc))
            results.append({"to": to, "ok": False, "error": str(exc)})
    return {"ok": True, "results": results}


@router.post("/{meeting_id}/pdf")
async def render_map_pdf(meeting_id: str) -> dict:
    """Render the MAP to PDF by piping a brief-shaped payload into the existing pdf_builder."""
    rec = _load(meeting_id)
    plan = rec.get("plan") or {}
    # Build a brief-shaped payload so we can reuse the brief template.
    sections = [
        {"heading": "Goal", "bullets": [plan.get("goal", ""), f"Success metric: {plan.get('success_metric', '')}"]},
        {
            "heading": "Stakeholders",
            "bullets": [
                f"{s.get('name')} ({s.get('role')}, {s.get('stance')}): {s.get('notes') or s.get('title') or ''}"
                for s in plan.get("stakeholders", []) or []
            ],
        },
        {
            "heading": "Workstreams",
            "bullets": [
                f"{w.get('title')} [{w.get('status')}] - Elastic: {w.get('owner_elastic')} / Customer: {w.get('owner_customer')}"
                for w in plan.get("workstreams", []) or []
            ],
        },
        {
            "heading": "Milestones",
            "bullets": [
                f"{m.get('date')} - {m.get('title')} [{m.get('status')}] - {m.get('blocker_note', '')}"
                for m in plan.get("milestones", []) or []
            ],
        },
        {
            "heading": "Risks",
            "bullets": [
                f"[{r.get('severity')}] {r.get('title')}: {r.get('description')} (Mitigation: {r.get('mitigation')})"
                for r in plan.get("risks", []) or []
            ],
        },
        {
            "heading": "Cadence",
            "bullets": [
                f"Weekly sync: {(plan.get('cadence') or {}).get('weekly_sync', '')}",
                f"MAP review: {(plan.get('cadence') or {}).get('map_review_cadence', '')}",
                f"Escalation: {(plan.get('cadence') or {}).get('escalation_path', '')}",
            ],
        },
    ]
    company = {"name": rec.get("company_name") or "", "id": rec.get("company_id") or ""}
    meeting = {"id": f"map-{meeting_id}", "title": f"Mutual Action Plan: {rec.get('company_name')}", "start_time": rec.get("updated_at", "")}
    brief_payload = {"headline": f"Mutual Action Plan - target close {plan.get('target_close_date', '')}", "sections": sections}
    try:
        path = pdf_builder.render_pdf(company=company, meeting=meeting, brief=brief_payload)
    except Exception as exc:
        log.warning("map.pdf_render_failed", meeting_id=meeting_id, error=str(exc))
        raise HTTPException(status_code=500, detail=f"pdf render failed: {exc}")
    return {
        "ok": True,
        "artifact_path": str(path),
        "artifact_url": f"{settings.public_base_url}/api/v1/briefs/{meeting['id']}/artifact",
    }
