"""
filename: map_agent.py
description: Mutual Action Plan (MAP) agent. Builds a joint 90-day path from
discovery to signature using the meeting dossier, the pre-meeting brief, and any
post-meeting record. Output is structured JSON the SA can edit inline.
date: 05-13-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.agents.base import Agent
from app.agents.schemas import MutualActionPlanOut
from app.config import settings
from app.integrations.claude_client import get_service
from app.repositories import synthetic
from app.utils.logging import get_logger

log = get_logger(__name__)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "ad-hoc"


SYSTEM = """You are an Elastic Senior Solutions Architect writing a Mutual Action Plan with a customer champion. Your job: turn the discovery context into a 90-day path to signature with shared accountability. Be specific, dated, and honest about blockers.

Hard rules:
- Every milestone has an ISO 8601 date (YYYY-MM-DD).
- Every workstream has BOTH an Elastic owner and a customer owner, named by role (e.g. "Solutions Architect", "Platform Lead"). Use roles, not personal names, unless the dossier explicitly names someone.
- Never invent stakeholder names. If the dossier does not name a person for a role, use the role label as the name (e.g. "Procurement Lead").
- Surface blockers explicitly in each milestone's blocker_note.
- Never use the em dash character. Use commas, parentheses, colons, or periods.
- Workstreams: 3 to 6 parallel tracks (POV setup, security review, procurement, technical evaluation, executive alignment, commercial).
- Milestones: include kickoff, requirements signoff, POV criteria, mid-POV review, success criteria validation, commercial proposal, security/legal review, executive review, contract signature, go-live. Each milestone references a workstream_id when relevant.
- Risks: legal review windows, infosec questionnaire, budget freeze, competing project, holiday seasonality. Be specific to this account.
- Cadence: weekly sync, MAP review cadence, escalation path on both sides.

The output is consumed as structured JSON; do not wrap in prose."""


_STAKEHOLDER = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "name": {"type": "string"},
        "role": {
            "type": "string",
            "enum": [
                "economic_buyer",
                "technical_evaluator",
                "champion",
                "blocker",
                "executive_sponsor",
                "procurement",
                "legal",
                "security",
                "other",
            ],
        },
        "title": {"type": "string"},
        "stance": {"type": "string", "enum": ["aligned", "neutral", "skeptical"]},
        "notes": {"type": "string"},
    },
    "required": ["name", "role", "stance"],
}

_WORKSTREAM = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "description": {"type": "string"},
        "owner_elastic": {"type": "string"},
        "owner_customer": {"type": "string"},
        "status": {"type": "string", "enum": ["not_started", "in_progress", "blocked", "done"]},
    },
    "required": ["id", "title", "description", "owner_elastic", "owner_customer", "status"],
}

_MILESTONE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "id": {"type": "string"},
        "title": {"type": "string"},
        "date": {"type": "string", "description": "ISO 8601 YYYY-MM-DD"},
        "owner_elastic": {"type": "string"},
        "owner_customer": {"type": "string"},
        "status": {"type": "string", "enum": ["not_started", "in_progress", "blocked", "done"]},
        "blocker_note": {"type": "string"},
        "workstream_id": {"type": "string"},
    },
    "required": ["id", "title", "date", "owner_elastic", "owner_customer", "status", "blocker_note"],
}

_RISK = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "title": {"type": "string"},
        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
        "description": {"type": "string"},
        "mitigation": {"type": "string"},
    },
    "required": ["title", "severity", "description", "mitigation"],
}

_CADENCE = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "weekly_sync": {"type": "string"},
        "map_review_cadence": {"type": "string"},
        "escalation_path": {"type": "string"},
    },
    "required": ["weekly_sync", "map_review_cadence", "escalation_path"],
}

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "goal": {"type": "string"},
        "target_close_date": {"type": "string"},
        "deal_value_usd": {"type": "number"},
        "success_metric": {"type": "string"},
        "stakeholders": {"type": "array", "items": _STAKEHOLDER},
        "workstreams": {"type": "array", "items": _WORKSTREAM},
        "milestones": {"type": "array", "items": _MILESTONE},
        "risks": {"type": "array", "items": _RISK},
        "cadence": _CADENCE,
    },
    "required": [
        "goal",
        "target_close_date",
        "success_metric",
        "stakeholders",
        "workstreams",
        "milestones",
        "risks",
        "cadence",
    ],
}


def _render_user_prompt(
    *,
    company: Dict[str, Any],
    meeting: Dict[str, Any],
    brief: Optional[Dict[str, Any]],
    post: Optional[Dict[str, Any]],
    target_close_date: Optional[str],
    deal_value_usd: Optional[float],
) -> str:
    parts = ["# Mutual Action Plan request", ""]
    parts.append(f"- Target close date: {target_close_date or 'pick a reasonable 90-day date from today'}")
    if deal_value_usd:
        parts.append(f"- Deal value (USD): {deal_value_usd}")
    parts.append("")
    parts.append("# Company")
    parts.append(f"- Name: {company.get('name')}")
    parts.append(f"- Industry: {company.get('industry')}")
    parts.append(f"- Size: {company.get('size')}")
    parts.append(f"- HQ: {company.get('headquarters', 'unknown')}")
    ts = company.get("tech_stack", {}) or {}
    parts.append(
        "- Tech stack: "
        f"observability={ts.get('observability', [])}, search={ts.get('search', [])}, cloud={ts.get('cloud', [])}"
    )
    parts.append("")
    parts.append("# Meeting")
    parts.append(f"- Title: {meeting.get('title')}")
    parts.append(f"- Time: {meeting.get('start_time')}")
    parts.append(f"- Attendees: {', '.join(meeting.get('attendees', []) or [])}")
    parts.append("")
    if brief:
        parts.append("# Pre-meeting brief headline")
        parts.append(brief.get("headline", ""))
        parts.append("")
        for sec in (brief.get("sections") or [])[:6]:
            parts.append(f"## {sec.get('heading')}")
            for b in sec.get("bullets", [])[:5]:
                parts.append(f"- {b}")
            parts.append("")
    if post:
        parts.append("# Post-meeting summary")
        parts.append((post.get("summary") or "")[:1200])
        parts.append("")
        ais = post.get("action_items") or []
        if ais:
            parts.append("# Action items captured")
            for a in ais[:10]:
                parts.append(f"- {a.get('title')} (owner: {a.get('owner_name')}, due: {a.get('due_date')})")
            parts.append("")
    parts.append(
        "Produce the Mutual Action Plan now as a single JSON object matching the schema. "
        "Pick dates between today and the target close. Use role labels for owners. "
        "If the dossier names a real person for a role, you may use that name; otherwise use the role label."
    )
    return "\n".join(parts)


def _mock_map(company_name: str, target_close_date: str, deal_value_usd: Optional[float]) -> Dict[str, Any]:
    """Offline-mode MAP used when no Claude API key is configured."""
    today = datetime.now(timezone.utc).date().isoformat()
    return {
        "goal": (
            f"Consolidate {company_name}'s observability and search stack onto Elastic, "
            f"with a signed contract by {target_close_date}. Headline metric: 30 percent TCO reduction "
            "vs incumbent at parity coverage, validated by a 6 week POV."
        ),
        "target_close_date": target_close_date,
        "deal_value_usd": deal_value_usd,
        "success_metric": "30 percent TCO reduction at parity coverage; POV ingest at sustained peak rate.",
        "stakeholders": [
            {"name": "Director of Platform Engineering", "role": "technical_evaluator", "title": "Platform lead", "stance": "aligned", "notes": "Owns POV criteria."},
            {"name": "CFO", "role": "economic_buyer", "title": "Finance", "stance": "neutral", "notes": "Will sign above the budget envelope."},
            {"name": "Platform Lead", "role": "champion", "title": "Day-to-day owner", "stance": "aligned", "notes": ""},
            {"name": "Procurement Lead", "role": "procurement", "title": "Sourcing", "stance": "neutral", "notes": "Two-week paper cycle."},
            {"name": "Security Lead", "role": "security", "title": "Infosec", "stance": "skeptical", "notes": "Questionnaire is the gate."},
        ],
        "workstreams": [
            {"id": "ws-pov", "title": "POV setup and execution", "description": "Stand up the Elastic Cloud cluster, ingest the agreed sources, and validate the success criteria.", "owner_elastic": "Solutions Architect", "owner_customer": "Platform Lead", "status": "in_progress"},
            {"id": "ws-security", "title": "Security review", "description": "Run the infosec questionnaire and SOC 2 evidence package.", "owner_elastic": "Security Engineer", "owner_customer": "Security Lead", "status": "not_started"},
            {"id": "ws-procurement", "title": "Procurement and legal", "description": "MSA redline, order form, sourcing approval.", "owner_elastic": "Account Executive", "owner_customer": "Procurement Lead", "status": "not_started"},
            {"id": "ws-exec", "title": "Executive alignment", "description": "Brief the CFO and CIO on TCO model and consolidation scope.", "owner_elastic": "Regional VP", "owner_customer": "CIO Office", "status": "not_started"},
        ],
        "milestones": [
            {"id": "ms-kickoff", "title": "Joint kickoff", "date": today, "owner_elastic": "Solutions Architect", "owner_customer": "Platform Lead", "status": "done", "blocker_note": "If kickoff slips the 90 day clock slips with it.", "workstream_id": "ws-pov"},
            {"id": "ms-req", "title": "POV requirements signoff", "date": _shift(today, 7), "owner_elastic": "Solutions Architect", "owner_customer": "Platform Lead", "status": "in_progress", "blocker_note": "Without signed criteria the POV is unfalsifiable.", "workstream_id": "ws-pov"},
            {"id": "ms-mid", "title": "Mid-POV review", "date": _shift(today, 28), "owner_elastic": "Solutions Architect", "owner_customer": "Platform Lead", "status": "not_started", "blocker_note": "Identifies blockers in time to remediate before close.", "workstream_id": "ws-pov"},
            {"id": "ms-success", "title": "Success criteria validation", "date": _shift(today, 45), "owner_elastic": "Solutions Architect", "owner_customer": "Platform Lead", "status": "not_started", "blocker_note": "Hard gate to commercial.", "workstream_id": "ws-pov"},
            {"id": "ms-security", "title": "Infosec questionnaire complete", "date": _shift(today, 35), "owner_elastic": "Security Engineer", "owner_customer": "Security Lead", "status": "not_started", "blocker_note": "Two week SLA on customer side.", "workstream_id": "ws-security"},
            {"id": "ms-proposal", "title": "Commercial proposal delivered", "date": _shift(today, 50), "owner_elastic": "Account Executive", "owner_customer": "Procurement Lead", "status": "not_started", "blocker_note": "Pricing requires CFO sign.", "workstream_id": "ws-procurement"},
            {"id": "ms-legal", "title": "MSA redline complete", "date": _shift(today, 65), "owner_elastic": "Legal", "owner_customer": "Legal", "status": "not_started", "blocker_note": "Holiday window risk.", "workstream_id": "ws-procurement"},
            {"id": "ms-exec", "title": "Executive review", "date": _shift(today, 75), "owner_elastic": "Regional VP", "owner_customer": "CIO Office", "status": "not_started", "blocker_note": "Last chance to defuse incumbent counter.", "workstream_id": "ws-exec"},
            {"id": "ms-sig", "title": "Contract signature", "date": target_close_date, "owner_elastic": "Account Executive", "owner_customer": "Procurement Lead", "status": "not_started", "blocker_note": "The whole plan is anchored here.", "workstream_id": "ws-procurement"},
            {"id": "ms-go", "title": "Production go-live", "date": _shift(target_close_date, 30), "owner_elastic": "Customer Architect", "owner_customer": "Platform Lead", "status": "not_started", "blocker_note": "Handover to CA assumed.", "workstream_id": "ws-pov"},
        ],
        "risks": [
            {"title": "Incumbent counter-offer", "severity": "high", "description": "Datadog or Splunk will discount aggressively at renewal.", "mitigation": "Anchor on TCO and consolidation, not feature checklist."},
            {"title": "Infosec questionnaire slippage", "severity": "medium", "description": "Customer security team is small and queued.", "mitigation": "Send the pre-filled SOC 2 package on day 1."},
            {"title": "Budget freeze at fiscal year end", "severity": "medium", "description": "Procurement cycle stalls in late Q4.", "mitigation": "Pull the commercial close in by 2 weeks."},
        ],
        "cadence": {
            "weekly_sync": "30 minutes every Tuesday, SA + Platform Lead, agenda is the open milestones list.",
            "map_review_cadence": "Full MAP review every other Friday with the AE and the customer champion.",
            "escalation_path": "Elastic side: SA to Regional VP. Customer side: champion to CIO Office. Triggered by any milestone in blocked status for 5 business days.",
        },
    }


def _shift(date_str: str, days: int) -> str:
    """Return YYYY-MM-DD shifted by `days`."""
    from datetime import date, timedelta
    try:
        y, m, d = [int(x) for x in date_str.split("-")[:3]]
        out = date(y, m, d) + timedelta(days=days)
        return out.isoformat()
    except Exception:
        return date_str


class MapAgent(Agent):
    name = "map"

    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        meeting_id = payload["meeting_id"]
        meeting = synthetic.find_meeting(meeting_id)
        if meeting is None:
            raise ValueError(f"meeting_id {meeting_id} not found in synthetic data")
        company = synthetic.find_company(meeting["company_id"])
        if company is None:
            raise ValueError(f"company {meeting['company_id']} not found")

        # Load any existing brief and post-meeting record for grounding.
        brief = _load_json(settings.runtime_dir / "briefs" / f"{meeting_id}.json")
        post = _load_json(settings.runtime_dir / "post_meeting" / f"{meeting_id}.json")

        target_close_date = (payload.get("target_close_date") or "").strip() or _shift(
            datetime.now(timezone.utc).date().isoformat(), 90
        )
        deal_value_usd = payload.get("deal_value_usd")

        return await self._generate(
            company=company,
            meeting=meeting,
            brief=brief,
            post=post,
            target_close_date=target_close_date,
            deal_value_usd=deal_value_usd,
            meeting_id=meeting_id,
        )

    async def run_ad_hoc(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        name = (payload.get("company_name") or "").strip()
        if not name:
            raise ValueError("company_name is required")
        slug_id = _slug(name)
        meeting_id = f"ad-hoc-map-{slug_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        company = {
            "id": f"ad-hoc-{slug_id}",
            "name": name,
            "industry": (payload.get("industry") or "").strip() or "Unknown",
            "size": (payload.get("size") or "").strip() or "Unknown",
            "headquarters": None,
            "tech_stack": {"observability": [], "search": [], "cloud": [], "other": []},
            "description": (payload.get("notes") or "").strip() or None,
        }
        meeting = {
            "id": meeting_id,
            "company_id": company["id"],
            "title": f"MAP workshop with {name}",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "attendees": [],
            "notes": payload.get("notes"),
        }
        target_close_date = (payload.get("target_close_date") or "").strip() or _shift(
            datetime.now(timezone.utc).date().isoformat(), 90
        )
        deal_value_usd = payload.get("deal_value_usd")
        return await self._generate(
            company=company,
            meeting=meeting,
            brief=None,
            post=None,
            target_close_date=target_close_date,
            deal_value_usd=deal_value_usd,
            meeting_id=meeting_id,
            ad_hoc=True,
        )

    async def _generate(
        self,
        *,
        company: Dict[str, Any],
        meeting: Dict[str, Any],
        brief: Optional[Dict[str, Any]],
        post: Optional[Dict[str, Any]],
        target_close_date: str,
        deal_value_usd: Optional[float],
        meeting_id: str,
        ad_hoc: bool = False,
    ) -> Dict[str, Any]:
        log.info("map.start", meeting_id=meeting_id, company=company.get("name"))
        user_prompt = _render_user_prompt(
            company=company,
            meeting=meeting,
            brief=brief,
            post=post,
            target_close_date=target_close_date,
            deal_value_usd=deal_value_usd,
        )
        result: MutualActionPlanOut = get_service().call_structured(
            system=SYSTEM,
            user=user_prompt,
            schema=OUTPUT_SCHEMA,
            output_model=MutualActionPlanOut,
            model="claude-haiku-4-5",
            # MAP output is dense (workstreams + 8-12 milestones + stakeholders
            # + risks + cadence). 4096 ran out mid-generation; 6144 fits.
            max_tokens=6144,
            effort="medium",
            mock_payload=_mock_map(company.get("name") or "the customer", target_close_date, deal_value_usd),
            audit_meta={"agent": "map", "meeting_id": meeting_id, "company_id": company.get("id")},
        )
        plan = result.model_dump()
        record = {
            "meeting_id": meeting_id,
            "company_id": company.get("id"),
            "company_name": company.get("name"),
            "ad_hoc": ad_hoc,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "status": "draft",
            "plan": plan,
        }
        out_dir = settings.runtime_dir / "map"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{meeting_id}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        # Best-effort ES write; disk is authoritative.
        try:
            from app.repositories.elasticsearch_repo import get_repo as get_es_repo
            es = get_es_repo()
            if es.available and hasattr(es, "_client"):
                es._client.index(index="fec-maps", id=meeting_id, document=record)  # noqa: SLF001
        except Exception as exc:
            log.warning("map.es_index_failed", meeting_id=meeting_id, error=str(exc))
        log.info("map.complete", meeting_id=meeting_id)
        return record


def _load_json(path):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None
