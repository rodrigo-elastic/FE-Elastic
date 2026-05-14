"""
filename: war_room.py
description: Deal Strategy War Room. Four specialist agents (Competitive, Compliance,
Cost, Renewal) run in parallel against a dossier, then a Senior FE synthesizer
merges the four takes into exactly three bullets the FE will say in the next
customer call. All five calls go through `claude_client.get_service()`; Haiku is
forced on every leg so the non-streaming endpoint completes well under the 60s
ECS edge timeout.
date: 13-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.agents.schemas import (
    WarRoomCompetitiveOut,
    WarRoomComplianceOut,
    WarRoomCostOut,
    WarRoomRenewalOut,
    WarRoomSynthesisOut,
)
from app.integrations.claude_client import MODEL_HAIKU, get_service
from app.utils.logging import get_logger

log = get_logger(__name__)


# ----------------------------------------------------------------------------- SYSTEM
# All four prompts are intentionally short, role-based, and contain no proper names.
# The synthesizer prompt enforces the JSON shape; Pydantic enforces it again on parse.

COMPETITIVE_SYSTEM = (
    "You are an Elastic Competitive Architect. Read the customer's incumbent stack, "
    "name the deal-killer competitor, and emit one sharp talking point that flips the "
    "meeting in 15 seconds. Cite the battlecard angle you used."
)

COMPLIANCE_SYSTEM = (
    "You are an Elastic Field Compliance Architect. Identify the top regulation the "
    "customer must satisfy and the Elastic control that lands the proof point. Two sentences."
)

COST_SYSTEM = (
    "You are an Elastic Pricing Architect. Given the customer's ingest volume and "
    "incumbent, produce the TCO delta in one number plus the line item that drives it. "
    "Use ASCII hyphens only."
)

RENEWAL_SYSTEM = (
    "You are an Elastic Renewal Architect. Identify the most urgent lever (renewal date, "
    "audit deadline, board mandate) and the play to use this week."
)

SYNTHESIZER_SYSTEM = (
    "You are a Senior Field Engineer running war-room sync. Read the four specialist takes. "
    "Emit exactly three bullets the FE will say in the next customer call. Each bullet "
    "starts with the verb. No bullet duplicates another. No proper names. Output JSON: "
    "{bullets: [string, string, string], confidence: low|medium|high, why: string}."
)


# ----------------------------------------------------------------------------- SCHEMAS

_COMPETITIVE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["competitor", "talking_point", "battlecard_angle", "summary"],
    "properties": {
        "competitor": {"type": "string"},
        "talking_point": {"type": "string"},
        "battlecard_angle": {"type": "string"},
        "summary": {"type": "string"},
    },
}

_COMPLIANCE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["regulation", "elastic_control", "summary"],
    "properties": {
        "regulation": {"type": "string"},
        "elastic_control": {"type": "string"},
        "summary": {"type": "string"},
    },
}

_COST_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tco_delta_usd", "driving_line_item", "summary"],
    "properties": {
        "tco_delta_usd": {"type": "number"},
        "driving_line_item": {"type": "string"},
        "summary": {"type": "string"},
    },
}

_RENEWAL_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["urgent_lever", "play_this_week", "summary"],
    "properties": {
        "urgent_lever": {"type": "string"},
        "play_this_week": {"type": "string"},
        "summary": {"type": "string"},
    },
}

_SYNTH_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["bullets", "confidence", "why"],
    "properties": {
        "bullets": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Exactly three bullets the FE will say in the next customer call. Each one must start with a verb and not duplicate another.",
        },
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "why": {"type": "string"},
    },
}


# ----------------------------------------------------------------------------- MOCKS
# Deterministic fallbacks so the demo path always returns something usable when the
# Anthropic key is missing or credits are exhausted.

def _mock_competitive(dossier: Dict[str, Any]) -> Dict[str, Any]:
    incumbent = _infer_incumbent(dossier) or "Splunk"
    return {
        "competitor": incumbent,
        "talking_point": (
            f"Open the meeting with: every dollar paid to {incumbent} for ingest is a dollar that does not "
            "buy retention; Elastic collapses search, observability, and SIEM onto one tier-aware data store."
        ),
        "battlecard_angle": "Single data plane",
        "summary": (
            f"{incumbent} is the deal-killer because the customer is paying ingest-based pricing for a stack "
            "that still needs a separate logs tool. Elastic ships APM, logs, and security on one cluster, "
            "one query language - the FE should lead with the consolidation story."
        ),
    }


def _mock_compliance(dossier: Dict[str, Any]) -> Dict[str, Any]:
    industry = ((dossier.get("company") or {}).get("industry") or "").lower()
    if "financ" in industry or "bank" in industry or "fintech" in industry:
        reg, ctrl = "DORA", "Elastic Security Detections + searchable cold-tier audit retention"
    elif "health" in industry:
        reg, ctrl = "HIPAA", "field-level encryption + role-based access control"
    elif "public" in industry or "gov" in industry:
        reg, ctrl = "FedRAMP Moderate", "Elastic Cloud on GovCloud + audit log shipping"
    else:
        reg, ctrl = "SOC 2 Type II", "Elastic Security with append-only audit indices"
    return {
        "regulation": reg,
        "elastic_control": ctrl,
        "summary": (
            f"{reg} is the binding constraint for this customer. Elastic lands the proof point with {ctrl}, "
            "which is native and demonstrable in a 30-minute walkthrough."
        ),
    }


def _mock_cost(dossier: Dict[str, Any]) -> Dict[str, Any]:
    incumbent = _infer_incumbent(dossier) or "Splunk"
    return {
        "tco_delta_usd": 1_850_000.0,
        "driving_line_item": f"{incumbent} ingest license at list price for ~3 TB/day",
        "summary": (
            f"Annual TCO delta vs {incumbent} lands at roughly 1.85M USD in the customer's favor. "
            "The single line item that drives it is ingest-based licensing on the incumbent versus "
            "Elastic's resource-based pricing with frozen-tier offload."
        ),
    }


def _mock_renewal(dossier: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "urgent_lever": "Incumbent contract co-terminates with the next board review window",
        "play_this_week": (
            "Schedule a joint exec readout that frames the renewal as a consolidation decision, "
            "not a tool swap; pre-wire the champion with the 1-page TCO delta before the readout."
        ),
        "summary": (
            "The urgent lever is the co-terminating incumbent contract landing inside the board review window. "
            "This week: book the joint exec readout and pre-wire the champion with the TCO one-pager."
        ),
    }


def _mock_synthesis(_: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "bullets": [
            "Open with the consolidation story: one cluster replaces ingest-based licensing and a separate logs tool.",
            "Anchor the proof in the binding regulation and the native Elastic control that satisfies it.",
            "Close by booking the joint exec readout this week, framed as a renewal-window consolidation decision.",
        ],
        "confidence": "high",
        "why": (
            "All four specialist takes converge on a single narrative - consolidate the incumbent, "
            "satisfy the regulation natively, and use the renewal window as the forcing function."
        ),
    }


def _infer_incumbent(dossier: Dict[str, Any]) -> Optional[str]:
    """Return the most plausible deal-killer competitor for a dossier.

    Looks at the company's observability stack first (Splunk/Datadog/AppDynamics are
    the canonical ones for this demo), then falls back to None.
    """
    company = dossier.get("company") or {}
    stack = company.get("tech_stack") or {}
    obs = [s.lower() for s in (stack.get("observability") or [])]
    for needle in ("splunk", "datadog", "appdynamics", "new relic", "dynatrace"):
        if any(needle in item for item in obs):
            return needle.title() if needle != "appdynamics" else "AppDynamics"
    return None


# ----------------------------------------------------------------------------- USER PROMPT

def _render_user_prompt(dossier: Dict[str, Any], focus: Optional[str], battlecard: Optional[Dict[str, Any]]) -> str:
    """Build the single user-message body shared across all five calls.

    Each specialist re-reads the same compact dossier; only the SYSTEM prompt
    changes the perspective. Keeping the user body identical maximizes prompt-cache
    reuse across the four parallel legs.
    """
    company = dossier.get("company") or {}
    meeting = dossier.get("meeting") or {}
    parts: List[str] = []
    parts.append("CUSTOMER:")
    parts.append(f"- name: {company.get('name', 'Unknown')}")
    parts.append(f"- industry: {company.get('industry', 'Unknown')}")
    parts.append(f"- size: {company.get('size', 'Unknown')}")
    stack = company.get("tech_stack") or {}
    if stack:
        for k in ("observability", "search", "cloud", "other"):
            vals = stack.get(k) or []
            if vals:
                parts.append(f"- {k}: {', '.join(vals)}")
    if company.get("description"):
        parts.append(f"- description: {company['description']}")
    parts.append("")
    parts.append("MEETING:")
    parts.append(f"- title: {meeting.get('title', 'Unknown')}")
    if meeting.get("notes"):
        parts.append(f"- notes: {meeting['notes']}")
    if focus:
        parts.append("")
        parts.append(f"FE FOCUS FOR THIS WAR ROOM: {focus}")
    if battlecard:
        parts.append("")
        parts.append("RELEVANT BATTLECARD:")
        parts.append(f"- competitor: {battlecard.get('competitor')}")
        parts.append(f"- tagline: {battlecard.get('tagline')}")
        angles = [tp.get("angle") for tp in (battlecard.get("talking_points") or []) if tp.get("angle")]
        if angles:
            parts.append(f"- angles available: {', '.join(angles)}")
    return "\n".join(parts)


# ----------------------------------------------------------------------------- AGENTS

def _load_battlecards() -> List[Dict[str, Any]]:
    path = Path(__file__).resolve().parents[2] / "data" / "seed" / "battlecards.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []


def _battlecard_for(competitor: Optional[str]) -> Optional[Dict[str, Any]]:
    if not competitor:
        return None
    slug = competitor.lower().replace(" ", "")
    for bc in _load_battlecards():
        if slug == (bc.get("competitor_slug") or "").lower().replace(" ", ""):
            return bc
        if competitor.lower() in (bc.get("competitor") or "").lower():
            return bc
    return None


async def _run_specialist(
    *,
    role: str,
    system: str,
    schema: Dict[str, Any],
    output_model: Any,
    user: str,
    max_tokens: int,
    mock_payload: Dict[str, Any],
    audit_meta: Dict[str, Any],
) -> Any:
    """Shell that calls the blocking SDK in a thread so asyncio.gather actually parallelizes."""
    svc = get_service()
    return await asyncio.to_thread(
        svc.call_structured,
        system=system,
        user=user,
        schema=schema,
        output_model=output_model,
        model=MODEL_HAIKU,
        max_tokens=max_tokens,
        effort="low",
        thinking_adaptive=False,
        cache_system=True,
        mock_payload=mock_payload,
        audit_meta={"agent": f"war_room_{role}", **audit_meta},
    )


async def run_competitive(dossier: Dict[str, Any], focus: Optional[str], audit_meta: Dict[str, Any]) -> WarRoomCompetitiveOut:
    incumbent = _infer_incumbent(dossier)
    battlecard = _battlecard_for(incumbent)
    return await _run_specialist(
        role="competitive",
        system=COMPETITIVE_SYSTEM,
        schema=_COMPETITIVE_SCHEMA,
        output_model=WarRoomCompetitiveOut,
        user=_render_user_prompt(dossier, focus, battlecard),
        max_tokens=600,
        mock_payload=_mock_competitive(dossier),
        audit_meta=audit_meta,
    )


async def run_compliance(dossier: Dict[str, Any], focus: Optional[str], audit_meta: Dict[str, Any]) -> WarRoomComplianceOut:
    return await _run_specialist(
        role="compliance",
        system=COMPLIANCE_SYSTEM,
        schema=_COMPLIANCE_SCHEMA,
        output_model=WarRoomComplianceOut,
        user=_render_user_prompt(dossier, focus, None),
        max_tokens=600,
        mock_payload=_mock_compliance(dossier),
        audit_meta=audit_meta,
    )


async def run_cost(dossier: Dict[str, Any], focus: Optional[str], audit_meta: Dict[str, Any]) -> WarRoomCostOut:
    return await _run_specialist(
        role="cost",
        system=COST_SYSTEM,
        schema=_COST_SCHEMA,
        output_model=WarRoomCostOut,
        user=_render_user_prompt(dossier, focus, None),
        max_tokens=600,
        mock_payload=_mock_cost(dossier),
        audit_meta=audit_meta,
    )


async def run_renewal(dossier: Dict[str, Any], focus: Optional[str], audit_meta: Dict[str, Any]) -> WarRoomRenewalOut:
    return await _run_specialist(
        role="renewal",
        system=RENEWAL_SYSTEM,
        schema=_RENEWAL_SCHEMA,
        output_model=WarRoomRenewalOut,
        user=_render_user_prompt(dossier, focus, None),
        max_tokens=600,
        mock_payload=_mock_renewal(dossier),
        audit_meta=audit_meta,
    )


async def run_synthesizer(
    *,
    competitive: WarRoomCompetitiveOut,
    compliance: WarRoomComplianceOut,
    cost: WarRoomCostOut,
    renewal: WarRoomRenewalOut,
    focus: Optional[str],
    audit_meta: Dict[str, Any],
) -> WarRoomSynthesisOut:
    user_lines = [
        "FOUR SPECIALIST TAKES (consume verbatim, do not invent facts):",
        "",
        "[COMPETITIVE]",
        competitive.summary,
        f"talking_point: {competitive.talking_point}",
        f"battlecard_angle: {competitive.battlecard_angle}",
        "",
        "[COMPLIANCE]",
        compliance.summary,
        f"regulation: {compliance.regulation}",
        f"elastic_control: {compliance.elastic_control}",
        "",
        "[COST]",
        cost.summary,
        f"tco_delta_usd: {cost.tco_delta_usd}",
        f"driving_line_item: {cost.driving_line_item}",
        "",
        "[RENEWAL]",
        renewal.summary,
        f"urgent_lever: {renewal.urgent_lever}",
        f"play_this_week: {renewal.play_this_week}",
    ]
    if focus:
        user_lines.append("")
        user_lines.append(f"FE FOCUS: {focus}")
    user = "\n".join(user_lines)

    svc = get_service()
    return await asyncio.to_thread(
        svc.call_structured,
        system=SYNTHESIZER_SYSTEM,
        user=user,
        schema=_SYNTH_SCHEMA,
        output_model=WarRoomSynthesisOut,
        model=MODEL_HAIKU,
        max_tokens=800,
        effort="low",
        thinking_adaptive=False,
        cache_system=True,
        mock_payload=_mock_synthesis({}),
        audit_meta={"agent": "war_room_synthesizer", **audit_meta},
    )


async def run_war_room(dossier: Dict[str, Any], focus: Optional[str] = None, *, audit_meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Run the four specialists in parallel, then the synthesizer; return the merged dict.

    Total wall clock on cold-start Haiku lands around 18-25s when the four legs
    overlap fully; the synthesizer is a single additional Haiku call.
    """
    audit_meta = audit_meta or {}
    competitive, compliance, cost, renewal = await asyncio.gather(
        run_competitive(dossier, focus, audit_meta),
        run_compliance(dossier, focus, audit_meta),
        run_cost(dossier, focus, audit_meta),
        run_renewal(dossier, focus, audit_meta),
    )
    synthesis = await run_synthesizer(
        competitive=competitive,
        compliance=compliance,
        cost=cost,
        renewal=renewal,
        focus=focus,
        audit_meta=audit_meta,
    )
    company = dossier.get("company") or {}
    meeting = dossier.get("meeting") or {}
    return {
        "meeting_id": meeting.get("id", ""),
        "company_id": company.get("id"),
        "company_name": company.get("name"),
        "focus": focus,
        "competitive": competitive.model_dump(),
        "compliance": compliance.model_dump(),
        "cost": cost.model_dump(),
        "renewal": renewal.model_dump(),
        "synthesis": synthesis.model_dump(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
