"""
filename: routes_weekly_slides.py
description: Weekly customer status slide deck. Aggregates post-meeting records
for a given week, groups by company, and uses Claude to synthesize slide content
matching the Field Engineering weekly standup format (Actions, Renewals, Cases,
Consumption, Feature Adoption, Risks/Notes/Top of mind).
date: 09-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.integrations.claude_client import get_elastic_service
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/weekly-slides", tags=["weekly-slides"])


# ============================================================ Pydantic output schema =


class SlideRenewal(BaseModel):
    label: str = ""
    notes: str = ""
    risk: str = ""
    amount: str = ""
    date: str = ""


class WeeklySlideOut(BaseModel):
    use_case: str = ""
    temperature: str = "stable"
    temperature_reason: str = ""
    current_actions: List[str] = Field(default_factory=list)
    upcoming_actions: List[str] = Field(default_factory=list)
    renewals: List[SlideRenewal] = Field(default_factory=list)
    cases: List[str] = Field(default_factory=list)
    consumption: str = ""
    wow_pct: str = "N/A"
    feature_adoption: List[str] = Field(default_factory=list)
    risks_notes: List[str] = Field(default_factory=list)


_SLIDE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "use_case": {"type": "string"},
        "temperature": {"type": "string", "enum": ["churn", "stable", "growth"]},
        "temperature_reason": {"type": "string"},
        "current_actions": {"type": "array", "items": {"type": "string"}},
        "upcoming_actions": {"type": "array", "items": {"type": "string"}},
        "renewals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "notes": {"type": "string"},
                    "risk": {"type": "string"},
                    "amount": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["label"],
            },
        },
        "cases": {"type": "array", "items": {"type": "string"}},
        "consumption": {"type": "string"},
        "wow_pct": {"type": "string"},
        "feature_adoption": {"type": "array", "items": {"type": "string"}},
        "risks_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "use_case", "temperature", "current_actions",
        "upcoming_actions", "consumption", "risks_notes",
    ],
}


# ============================================================ Helpers ===============


def _week_bounds(week_start_str: Optional[str]):
    if week_start_str:
        try:
            d = date.fromisoformat(week_start_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid week_start. Use YYYY-MM-DD.")
    else:
        today = date.today()
        d = today - timedelta(days=today.weekday())
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=7)


def _load_post_meetings(demo_mode: bool, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen: set = set()

    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo
        es = get_es_repo()
        if es.available:
            for rec in es.list_post_meetings(limit=500):
                mid = rec.get("meeting_id", "")
                if mid in seen:
                    continue
                if not demo_mode:
                    ga = rec.get("generated_at", "")
                    if not ga:
                        continue
                    try:
                        ts = datetime.fromisoformat(ga.replace("Z", "+00:00"))
                        if not (start <= ts < end):
                            continue
                    except Exception:
                        continue
                records.append(rec)
                seen.add(mid)
    except Exception as exc:
        log.warning("weekly_slides.es_load_failed", error=str(exc))

    post_dir = settings.runtime_dir / "post_meeting"
    if post_dir.exists():
        for p in sorted(post_dir.glob("*.json")):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
                mid = rec.get("meeting_id", p.stem)
                if mid in seen:
                    continue
                if not demo_mode:
                    ga = rec.get("generated_at", "")
                    if not ga:
                        continue
                    ts = datetime.fromisoformat(ga.replace("Z", "+00:00"))
                    if not (start <= ts < end):
                        continue
                records.append(rec)
                seen.add(mid)
            except Exception:
                pass

    return records


def _group_by_company(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for rec in records:
        key = (rec.get("company_name") or rec.get("company_id") or "Unknown").strip()
        grouped.setdefault(key, []).append(rec)
    return grouped


def _extract_sf(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    for rec in sorted(records, key=lambda r: r.get("generated_at", ""), reverse=True):
        sw = rec.get("salesforce_writes") or {}
        if sw:
            return sw
    return {}


def _build_slide(company_name: str, records: List[Dict[str, Any]], sf: Dict[str, Any]) -> Dict[str, Any]:
    summaries = [r.get("summary", "") for r in records if r.get("summary")]
    all_actions: List[Dict[str, Any]] = []
    for rec in records:
        all_actions.extend(rec.get("action_items") or [])
    meddpicc: List[Dict[str, Any]] = []
    for rec in records:
        meddpicc.extend(rec.get("meddpicc_signals") or [])

    opp = sf.get("opportunity") or {}
    account = sf.get("account") or {}

    sf_ctx_lines = []
    if account.get("Name"):
        sf_ctx_lines.append(f"Account: {account['Name']}, Industry: {account.get('Industry', 'N/A')}")
    if opp.get("Name"):
        amt = opp.get("Amount") or 0
        sf_ctx_lines.append(
            f"Opportunity: {opp['Name']}, Stage: {opp.get('StageName', '')}, "
            f"Amount: ${amt:,}, Close: {opp.get('CloseDate', '')}"
        )
    sf_ctx = "\n".join(sf_ctx_lines) or "Not available."

    ai_lines = "\n".join(
        f"- {ai.get('title', '')} (owner: {ai.get('owner_name', 'TBD')}, "
        f"due: {ai.get('due_date', 'TBD')}, impact: {ai.get('impact', 'med')})"
        for ai in all_actions
    ) or "No action items."

    meddpicc_lines = "\n".join(
        f"- [{m.get('category', '')}] {m.get('note', '') or m.get('quote', '')[:120]}"
        for m in meddpicc[:8]
    ) or "No MEDDPICC signals."

    summary_text = "\n\n---\n\n".join(summaries) or "No meeting summaries available."

    system = (
        "You are a Field Engineering weekly standup assistant at Elastic. "
        "You produce structured, concise, executive-ready customer status summaries. "
        "Be specific - use real names, amounts, dates from the input data. "
        "Never invent facts not in the input. If data is missing, say so briefly."
    )

    user = f"""Generate a weekly customer status slide for the FE team standup.

Company: {company_name}
Salesforce: {sf_ctx}

Meeting summaries this week:
{summary_text}

Action items:
{ai_lines}

MEDDPICC signals:
{meddpicc_lines}

Return a JSON object with these exact keys:
{{
  "use_case": "Short description of main Elastic use cases (e.g. 'Security + Observability')",
  "temperature": "churn|stable|growth",
  "temperature_reason": "One sentence explaining the account health signal.",
  "current_actions": ["2-5 in-flight action items. Include owner. One concise line each."],
  "upcoming_actions": ["1-3 planned future actions."],
  "renewals": [{{"label": "Renewal name/description", "notes": "Brief context", "risk": "low|med|high", "amount": "$amount", "date": "YYYY-MM-DD"}}],
  "cases": ["L2 - Title - Status (use format from data if available)"],
  "consumption": "1-2 sentence summary of consumption trend and account health.",
  "wow_pct": "??% or actual week-over-week % if inferable from data",
  "feature_adoption": ["Elastic feature being actively adopted - max 4"],
  "risks_notes": ["Key risk, note, or top-of-mind item - 2-4 items"]
}}

Rules:
- temperature: 'growth' if positive deal signals or expansion; 'churn' if risk, disengagement, or renewal concerns; 'stable' otherwise.
- current_actions: in-flight or due soon. upcoming_actions: planned for future meetings/sprints.
- cases: [] if no case data available.
- renewals: use opportunity data; [] if none.
- Respond with ONLY the JSON object. No markdown. No explanation."""

    mock_payload: Dict[str, Any] = {
        "use_case": "Security + Observability",
        "temperature": "stable",
        "temperature_reason": "Active engagement across multiple workstreams. No major risk signals.",
        "current_actions": [
            f"Follow up on open action items from {company_name} meetings",
            "Send meeting summary and next steps",
        ],
        "upcoming_actions": ["Schedule next business review"],
        "renewals": [],
        "cases": [],
        "consumption": "Stable consumption. On-prem deployment limits telemetry visibility.",
        "wow_pct": "N/A",
        "feature_adoption": ["Elastic Stack", "Agent Builder", "Observability"],
        "risks_notes": ["Review pending action items and ownership assignments"],
    }

    model_name = settings.model_for("post_meeting")

    # Always use the Elastic inference connector - customer data must not leave
    # the Elastic infrastructure. strict=True blocks all fallback paths to the
    # direct Anthropic API.
    try:
        svc = get_elastic_service()
        result: WeeklySlideOut = svc.call_structured(
            system=system,
            user=user,
            schema=_SLIDE_SCHEMA,
            output_model=WeeklySlideOut,
            model=model_name,
            max_tokens=1500,
            effort="high",
            thinking_adaptive=True,
            cache_system=True,
            mock_payload=mock_payload,
            audit_meta={"agent": "weekly_slides", "company": company_name},
            strict=True,
        )
        slide = result.model_dump()
    except RuntimeError as exc:
        # get_elastic_service() raised - Kibana not configured or strict block triggered.
        log.warning("weekly_slides.elastic_required", company=company_name, error=str(exc)[:200])
        raise
    except Exception as exc:
        log.warning("weekly_slides.claude_failed", company=company_name, error=str(exc)[:200])
        slide = mock_payload.copy()

    arr = opp.get("Amount") or 0
    slide["company_name"] = company_name
    slide["arr"] = f"${arr:,}" if arr else ""
    slide["cloud_arr"] = ""
    slide["training_services"] = ""
    slide["renewable_base"] = ""
    slide["open_ne"] = ""
    slide["salesforce_url"] = account.get("Url") or opp.get("Url") or ""
    slide["meeting_count"] = len(records)
    slide["meeting_ids"] = [r.get("meeting_id", "") for r in records]
    slide["updated"] = date.today().isoformat()
    return slide


# ============================================================ Endpoints =============


@router.get("")
def get_weekly_slides(
    week_start: Optional[str] = Query(None, description="Monday YYYY-MM-DD. Defaults to current week."),
    demo: bool = Query(False, description="Use all available post-meetings regardless of date."),
) -> Dict[str, Any]:
    """Generate weekly customer status slides from post-meeting records.

    Groups meetings by company, calls Claude to synthesize slide content
    (actions, renewals, cases, consumption, features, risks/notes).
    Pass demo=true to include all historical meetings when the current week has none.
    """
    start, end = _week_bounds(week_start)
    records = _load_post_meetings(demo, start, end)

    if not records:
        return {
            "ok": True,
            "week_start": start.date().isoformat(),
            "week_end": (end - timedelta(days=1)).date().isoformat(),
            "slides": [],
            "companies": 0,
            "meetings": 0,
            "demo": demo,
        }

    grouped = _group_by_company(records)
    slides = []
    for company_name, company_records in grouped.items():
        sf = _extract_sf(company_records)
        try:
            slide = _build_slide(company_name, company_records, sf)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Elastic inference connector required for customer data. {exc}",
            )
        slides.append(slide)

    return {
        "ok": True,
        "week_start": start.date().isoformat(),
        "week_end": (end - timedelta(days=1)).date().isoformat(),
        "slides": slides,
        "companies": len(slides),
        "meetings": len(records),
        "demo": demo,
    }
