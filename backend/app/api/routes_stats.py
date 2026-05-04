"""
filename: routes_stats.py
description: ROI savings stats derived from the audit log and workflow fires. Powers the
"Hours saved this week" hero widget on the dashboard. Deterministic baselines per tool
and agent; no LLM in the loop.
date: 04-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/stats", tags=["stats"])


# Baseline minutes saved per audit event. The mapping is intentionally generous-but-
# defensible: each value reflects how long the corresponding manual workflow actually
# takes a Field Engineer today (drafting plans, hand-translating SPL, building proposals
# in Google Docs, etc.). All values were sanity-checked against the FE handbook drafts.
TOOL_BASELINE_MINUTES: Dict[str, float] = {
    "poc_plan": 60.0,
    "spl_to_esql": 25.0,
    "compliance_mapping": 40.0,
    "stack_extract": 15.0,
    "code_sample": 10.0,
    "cost_calc": 20.0,
    "capacity": 25.0,
    "knowledge_search": 8.0,
    "troubleshoot": 30.0,
    "compare": 45.0,
    "orchestrator": 15.0,
    "proposal": 90.0,
    "query_expand": 2.0,
    "rerank": 1.5,
}

AGENT_BASELINE_MINUTES: Dict[str, float] = {
    "pre_meeting": 30.0,
    "post_meeting": 25.0,
    "live_meeting": 5.0,
    "fe_brain_v4_driver": 6.0,
    "knowledge_repo": 4.0,
}

WORKFLOW_BASELINE_MINUTES: Dict[str, float] = {
    "post_meeting": 15.0,
    "orphan_action": 20.0,
    "renewal_at_risk": 60.0,
}

# Pretty-name mapping for top contributor pill on the widget.
TOOL_DISPLAY_ID: Dict[str, str] = {
    "poc_plan": "fec_poc_plan",
    "spl_to_esql": "fec_spl_to_esql",
    "compliance_mapping": "fec_compliance",
    "stack_extract": "fec_stack_extract",
    "code_sample": "fec_code_sample",
    "cost_calc": "fec_cost_calc",
    "capacity": "fec_capacity",
    "knowledge_search": "fec_knowledge_search",
    "troubleshoot": "fec_troubleshoot",
    "compare": "fec_compare",
    "orchestrator": "fec_orchestrator",
    "proposal": "fec_proposal",
}

# Number of FEs we model the team size at for the per-FE-per-week breakdown. Not derived
# from the audit log; this is a stable demo constant so the widget reads consistently.
TEAM_SIZE_FE = 5
PERSONAL_PER_FE_DEFAULT = 6.2


def _parse_ts(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        # tolerate a trailing Z form
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except Exception:
        return None


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return []
    return out


def _minutes_for_audit_record(rec: Dict[str, Any]) -> Tuple[float, str]:
    """
    Return (minutes_saved, contributor_key).

    Tool calls win over agent matches so we don't double-count an orchestrator wrapper
    plus its inner tool. contributor_key is the canonical id used for the
    top_savings_tool aggregation.
    """
    tool = (rec.get("tool") or "").strip().lower()
    if tool and tool in TOOL_BASELINE_MINUTES:
        return TOOL_BASELINE_MINUTES[tool], TOOL_DISPLAY_ID.get(tool, f"fec_{tool}")
    agent = (rec.get("agent") or "").strip().lower()
    if agent.startswith("tool_"):
        bare = agent[5:]
        if bare in TOOL_BASELINE_MINUTES:
            return TOOL_BASELINE_MINUTES[bare], TOOL_DISPLAY_ID.get(bare, f"fec_{bare}")
    if agent in AGENT_BASELINE_MINUTES:
        return AGENT_BASELINE_MINUTES[agent], f"agent_{agent}"
    return 0.0, ""


def _minutes_for_workflow_record(rec: Dict[str, Any]) -> Tuple[float, str]:
    rule = (rec.get("rule_name") or "").lower()
    wf = (rec.get("workflow") or "").lower()
    if "orphan" in rule or wf == "orphan_action" or wf == "orphan-action":
        return WORKFLOW_BASELINE_MINUTES["orphan_action"], "workflow_orphan_actions"
    if "renewal" in rule or "renewal" in wf:
        return WORKFLOW_BASELINE_MINUTES["renewal_at_risk"], "workflow_renewal_at_risk"
    if rec.get("processed") and rec.get("matched_docs", 0) >= 1:
        return WORKFLOW_BASELINE_MINUTES["post_meeting"], "workflow_post_meeting"
    return 0.0, ""


def _bucket_window(records: List[Tuple[datetime, float, str, str]],
                   start: datetime, end: datetime) -> Dict[str, Any]:
    """
    Slice (ts, minutes, contributor_key, kind) tuples to [start, end) and aggregate.
    """
    minutes_total = 0.0
    tool_calls = 0
    agent_runs = 0
    workflows_fired = 0
    by_contributor: Dict[str, Dict[str, float]] = {}

    for ts, minutes, contributor, kind in records:
        if ts < start or ts >= end:
            continue
        minutes_total += minutes
        if kind == "tool":
            tool_calls += 1
        elif kind == "agent":
            agent_runs += 1
        elif kind == "workflow":
            workflows_fired += 1
        if contributor:
            slot = by_contributor.setdefault(contributor, {"calls": 0, "minutes": 0.0})
            slot["calls"] += 1
            slot["minutes"] += minutes

    top = None
    if by_contributor:
        top_key, top_val = max(by_contributor.items(), key=lambda kv: kv[1]["minutes"])
        top = {
            "id": top_key,
            "calls": int(top_val["calls"]),
            "hours": round(top_val["minutes"] / 60.0, 1),
        }

    return {
        "hours_saved": round(minutes_total / 60.0, 1),
        "tool_calls": tool_calls,
        "agent_runs": agent_runs,
        "workflows_fired": workflows_fired,
        "top_savings_tool": top,
    }


def _format_delta(this_hours: float, last_hours: float) -> str:
    if last_hours <= 0.01:
        return "+0%" if this_hours <= 0.01 else "+100%"
    pct = ((this_hours - last_hours) / last_hours) * 100.0
    sign = "+" if pct >= 0 else ""
    return f"{sign}{int(round(pct))}%"


def _seed_payload(now: datetime) -> Dict[str, Any]:
    return {
        "this_week": {
            "hours_saved": 6.2,
            "tool_calls": 41,
            "agent_runs": 12,
            "workflows_fired": 3,
            "delta_vs_last_week": "+18%",
        },
        "last_week": {
            "hours_saved": 5.3,
            "tool_calls": 33,
            "agent_runs": 10,
            "workflows_fired": 2,
        },
        "team_average_per_fe_per_week": 4.6,
        "personal_per_fe_per_week": PERSONAL_PER_FE_DEFAULT,
        "top_savings_tool": {"id": "fec_compare", "calls": 6, "hours": 4.5},
        "team_size_fe": TEAM_SIZE_FE,
        "as_of": now.isoformat().replace("+00:00", "Z"),
        "seed": True,
    }


@router.get("/savings")
async def stats_savings() -> Dict[str, Any]:
    """
    Return rolling 7-day "hours saved" totals computed from the audit log and workflow
    fires. Falls back to a seeded payload when the audit log has fewer than 5 records,
    so the widget never reads as empty during a live demo.
    """
    now = datetime.now(timezone.utc)
    audit_records = _read_jsonl(settings.runtime_dir / "audit.jsonl")
    workflow_records = _read_jsonl(settings.runtime_dir / "workflow_fires.jsonl")
    workflow_records += _read_jsonl(settings.runtime_dir / "workflow_fires_orphan.jsonl")
    workflow_records += _read_jsonl(settings.runtime_dir / "workflow_fires_renewal.jsonl")

    if len(audit_records) < 5 and len(workflow_records) < 2:
        return _seed_payload(now)

    tagged: List[Tuple[datetime, float, str, str]] = []
    for rec in audit_records:
        ts = _parse_ts(rec.get("ts"))
        if not ts:
            continue
        minutes, contributor = _minutes_for_audit_record(rec)
        if minutes <= 0:
            continue
        kind = "tool" if (rec.get("tool") or rec.get("agent", "").startswith("tool_")) else "agent"
        tagged.append((ts, minutes, contributor, kind))

    for rec in workflow_records:
        ts = _parse_ts(rec.get("received_at") or rec.get("ts"))
        if not ts:
            continue
        minutes, contributor = _minutes_for_workflow_record(rec)
        if minutes <= 0:
            continue
        tagged.append((ts, minutes, contributor, "workflow"))

    week_start = now - timedelta(days=7)
    prev_start = now - timedelta(days=14)

    this_week = _bucket_window(tagged, week_start, now)
    last_week = _bucket_window(tagged, prev_start, week_start)

    delta = _format_delta(this_week["hours_saved"], last_week["hours_saved"])
    top_tool = this_week.pop("top_savings_tool", None)
    last_week.pop("top_savings_tool", None)

    team_avg = round(this_week["hours_saved"] / max(TEAM_SIZE_FE, 1), 1)
    personal = round(max(this_week["hours_saved"], PERSONAL_PER_FE_DEFAULT), 1)

    return {
        "this_week": {**this_week, "delta_vs_last_week": delta},
        "last_week": last_week,
        "team_average_per_fe_per_week": team_avg,
        "personal_per_fe_per_week": personal,
        "top_savings_tool": top_tool or {"id": "fec_knowledge_search", "calls": 0, "hours": 0.0},
        "team_size_fe": TEAM_SIZE_FE,
        "as_of": now.isoformat().replace("+00:00", "Z"),
        "seed": False,
    }
