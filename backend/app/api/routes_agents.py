"""
filename: routes_agents.py
description: Trigger endpoints for the three agents (pre, live, post). Each endpoint runs the agent and returns its structured result.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.live_meeting import LiveMeetingAgent
from app.agents.post_meeting import PostMeetingAgent
from app.agents.pre_meeting import PreMeetingAgent
from app.config import settings
from app.integrations import agent_builder as ab
from app.repositories import synthetic
from app.repositories.elasticsearch_repo import get_repo as get_es_repo
from app.services import transcript_parser
from app.services import vtt_parser

router = APIRouter(prefix="/agents", tags=["agents"])

_pre = PreMeetingAgent()
_post = PostMeetingAgent()
_live = LiveMeetingAgent()


class AdHocPreMeetingRequest(BaseModel):
    """User-typed dossier for the Quick Research flow. Only these fields leave the boundary."""

    company_name: str = Field(..., min_length=1, max_length=120)
    industry: Optional[str] = Field("", max_length=80)
    size: Optional[str] = Field("", max_length=80)
    tech_stack: Optional[str] = Field("", max_length=400, description="Comma-separated list of observability/search/cloud tools.")
    notes: Optional[str] = Field("", max_length=2000, description="Free-form context: what to discuss, recent signals, blockers.")
    meeting_title: Optional[str] = Field("", max_length=160)
    language: Optional[str] = Field("English", max_length=40, description="Output language; English|Spanish|Japanese|German|French.")
    model: Optional[str] = Field("", max_length=60, description="Override model id (claude-haiku-4-5 | claude-sonnet-4-6 | claude-opus-4-7). Empty = use server default.")


class AdHocPostMeetingRequest(BaseModel):
    """Run the Post-Meeting agent against an externally-supplied transcript (Zoom .vtt, Gong export, or pasted plain text)."""

    company_name: str = Field(..., min_length=1, max_length=120)
    meeting_title: Optional[str] = Field("", max_length=160)
    industry: Optional[str] = Field("", max_length=80)
    size: Optional[str] = Field("", max_length=80)
    notes: Optional[str] = Field("", max_length=2000)
    transcript_text: str = Field(..., min_length=20, max_length=200000, description="Raw WebVTT or plain 'Speaker: text' transcript.")
    transcript_source: Optional[str] = Field("uploaded", max_length=40, description="zoom | gong | manual")
    language: Optional[str] = Field("English", max_length=40)
    model: Optional[str] = Field("", max_length=60)


class AgentResearchRequest(AdHocPreMeetingRequest):
    """Quick Research via Kibana Agent Builder. Extends the ad-hoc form with a required agent_id."""

    agent_id: str = Field(..., min_length=1, max_length=120, description="Agent Builder agent id, e.g. fec_field_assistant or fec_user_splunk_displacement.")


# ------------------------------------------------------------------ helpers


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "ad-hoc"


def _parse_markdown_to_sections(text: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Split a markdown string into a headline and a list of section dicts.

    Each ``## Heading`` becomes ``{"heading": str, "bullets": [str, ...]}``.
    The first ``# H1`` or the first non-blank paragraph before any heading is
    returned as the headline. Bullet lines starting with ``- `` or ``* `` are
    collected into the current section's ``bullets`` list.
    """
    headline = ""
    sections: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    preamble_lines: List[str] = []
    in_preamble = True

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if line.startswith("# ") and not line.startswith("## "):
            # H1 - treat as headline, ends preamble
            candidate = line[2:].strip()
            if not headline:
                headline = candidate
            in_preamble = False
            continue

        if line.startswith("## "):
            in_preamble = False
            if current is not None:
                sections.append(current)
            current = {"heading": line[3:].strip(), "bullets": []}
            continue

        if line.startswith("### "):
            # Treat sub-headings as bullet items inside the current section
            if current is not None:
                current["bullets"].append(line[4:].strip())
            continue

        if (line.startswith("- ") or line.startswith("* ")) and current is not None:
            bullet_text = line[2:].strip()
            if bullet_text:
                current["bullets"].append(bullet_text)
            continue

        if in_preamble and line:
            preamble_lines.append(line)

    if current is not None:
        sections.append(current)

    if not headline and preamble_lines:
        headline = preamble_lines[0]

    return headline, sections


def _steps_to_sources(steps: List[Any]) -> Dict[str, Any]:
    """Convert Kibana Agent Builder step list to the ``sources_used`` structure expected by the brief viewer.

    Tool call types recognised:
    - ``fec_knowledge_search`` - adds to ``"knowledge"`` with query and snippet
    - ``fec_compare``          - adds to ``"competitive"`` with competitor name
    - ``fec_cost_calc``        - adds to ``"cost_calc"`` with raw params
    - anything else            - adds to ``"tools"`` with tool_id
    Reasoning steps are silently ignored.
    """
    sources: Dict[str, Any] = {
        "knowledge": [],
        "competitive": [],
        "cost_calc": [],
        "tools": [],
    }

    for step in steps or []:
        if not isinstance(step, dict):
            continue
        step_type = step.get("type", "")
        if step_type == "reasoning":
            continue
        if step_type != "tool_call":
            continue

        tool_id = step.get("tool_id", "")
        params = step.get("params") or {}
        result = step.get("result") or {}

        if tool_id == "fec_knowledge_search":
            snippet = ""
            if isinstance(result, dict):
                hits = result.get("hits") or result.get("results") or []
                if hits and isinstance(hits, list):
                    first = hits[0]
                    snippet = (first.get("text") or first.get("content") or "")[:200]
            sources["knowledge"].append({
                "query": params.get("query", ""),
                "snippet": snippet,
            })
        elif tool_id == "fec_compare":
            sources["competitive"].append({
                "competitor": params.get("competitor") or params.get("competitor_name") or "",
            })
        elif tool_id == "fec_cost_calc":
            sources["cost_calc"].append({"params": params})
        else:
            sources["tools"].append({"tool_id": tool_id})

    return sources


@router.post("/pre-meeting/agent-research")
async def run_pre_meeting_agent_research(req: AgentResearchRequest) -> Dict[str, Any]:
    """Kibana Agent Builder research: builds an account brief using the specified agent.

    The agent handles tool selection, competitive lookups, and knowledge retrieval
    autonomously. The response is normalised into the same brief viewer format as
    the ad-hoc Quick Research endpoint so the existing meeting.html UI can render it
    without any changes.
    """
    name = req.company_name.strip()
    slug_id = _slug(name)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    meeting_id = f"agent-{slug_id}-{timestamp}"

    industry = (req.industry or "").strip() or "Unknown"
    size = (req.size or "").strip() or "Unknown"
    stack = (req.tech_stack or "").strip()
    notes = (req.notes or "").strip()
    title = (req.meeting_title or "").strip() or f"Discovery with {name}"

    stack_line = f"Incumbent tech stack: {stack}" if stack else "Incumbent tech stack: not specified"
    notes_line = f"Additional context: {notes}" if notes else ""

    prompt_parts = [
        f"You are preparing a pre-meeting research brief for an Elastic Field Engineer.",
        f"Account: {name}",
        f"Industry: {industry}",
        f"Company size: {size}",
        stack_line,
        f"Meeting title: {title}",
    ]
    if notes_line:
        prompt_parts.append(notes_line)

    prompt_parts += [
        "",
        "Please produce a thorough pre-meeting brief covering:",
        "1. Competitive analysis vs the incumbent stack and key differentiators for Elastic",
        "2. TCO comparison and cost-savings narrative relevant to their size and industry",
        "3. Tailored discovery questions to uncover pain points and expansion opportunities",
        "4. A realistic migration path from their current stack to Elastic",
        "5. Key risks and objections to prepare for, with recommended responses",
        "",
        "Format your response in Markdown with a top-level heading as the brief headline,"
        " then ## sections for each topic above, using bullet points.",
    ]
    research_prompt = "\n".join(prompt_parts)

    raw = ab.converse(req.agent_id, research_prompt)

    if not isinstance(raw, dict):
        raise HTTPException(status_code=502, detail="agent_builder.converse returned unexpected type")

    if raw.get("error") or raw.get("dry_run"):
        label = "dry_run" if raw.get("dry_run") else "error"
        raise HTTPException(status_code=502, detail=f"agent_builder.converse returned {label}: {raw}")

    response_block = raw.get("response") or {}
    response_text = response_block.get("message") or response_block.get("text") or ""
    steps = raw.get("steps") or []
    model_usage = raw.get("model_usage") or {}

    headline, sections = _parse_markdown_to_sections(response_text)
    if not headline:
        headline = f"Agent research brief for {name}"

    sources_used = _steps_to_sources(steps)

    record: Dict[str, Any] = {
        "meeting_id": meeting_id,
        "company_name": name,
        "ad_hoc": True,
        "agent_research": True,
        "agent_id": req.agent_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "headline": headline,
        "sections": sections,
        "sources_used": sources_used,
        "steps": steps,
        "model_usage": model_usage,
        "company_snapshot": {
            "name": name,
            "industry": industry,
            "size": size,
            "tech_stack_notes": stack,
        },
        "meeting_snapshot": {
            "id": meeting_id,
            "title": title,
            "notes": notes,
        },
    }

    out_dir = settings.runtime_dir / "briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{meeting_id}.json").write_text(
        json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    get_es_repo().index_brief(record)

    return record


@router.post("/pre-meeting/ad-hoc")
async def run_pre_meeting_ad_hoc(req: AdHocPreMeetingRequest) -> Dict[str, Any]:
    """Quick Research: takes only what the FE typed, no synthetic data lookup. Compliance-friendly."""
    try:
        return await _pre.run_ad_hoc(req.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/pre-meeting/{meeting_id}")
async def run_pre_meeting(meeting_id: str, language: str = "English", model: str = "") -> Dict[str, Any]:
    try:
        return await _pre.run({"meeting_id": meeting_id, "language": language, "model": model})
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/post-meeting/from-transcript")
async def run_post_meeting_from_transcript(req: AdHocPostMeetingRequest) -> Dict[str, Any]:
    """Parse a Zoom/Gong/plain transcript and run the Post-Meeting agent on it.

    The transcript itself never leaves the boundary except as part of the prompt to Claude.
    """
    turns = vtt_parser.parse_vtt(req.transcript_text)
    if not turns:
        raise HTTPException(status_code=400, detail="could not parse any speaker turns from transcript")
    try:
        return await _post.run_ad_hoc(
            {
                "company_name": req.company_name,
                "meeting_title": req.meeting_title or "",
                "industry": req.industry or "",
                "size": req.size or "",
                "notes": req.notes or "",
                "transcript_source": req.transcript_source or "uploaded",
                "turns": turns,
                "language": req.language or "English",
                "model": req.model or "",
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/post-meeting/{meeting_id}")
async def run_post_meeting(meeting_id: str, language: str = "English", model: str = "") -> Dict[str, Any]:
    """Run the post-meeting agent against a meeting on file.

    Synthetic meeting ids hit `_post.run()` which expects a real transcript.
    Ad-hoc Quick Research briefs (id pattern: `ad-hoc-<slug>-<timestamp>`)
    have no transcript on disk - we synthesise turns from the brief's
    discovery questions + talking points so the demo flow stays connected:
    Quick Research -> Pre-Meeting brief -> Post-Meeting output without a
    manual transcript upload.
    """
    # Transcript-only artifacts (id pattern: `transcript-<slug>-<ts>`) come from
    # the standalone Quick Research transcript analyzer; there is no source
    # meeting to re-run. Return the persisted post-meeting doc instead so the
    # meeting.html "Run Post-Meeting" CTA stays idempotent rather than 404-ing.
    if meeting_id.startswith("transcript-"):
        try:
            es = get_es_repo()
            if es.available and hasattr(es, "get_post_meeting"):
                doc = es.get_post_meeting(meeting_id)
                if doc:
                    return doc
        except Exception:
            pass
        disk = settings.runtime_dir / "post_meeting" / f"{meeting_id}.json"
        if disk.exists():
            try:
                return json.loads(disk.read_text(encoding="utf-8"))
            except Exception:
                pass
        raise HTTPException(
            status_code=404,
            detail=f"transcript artifact {meeting_id} has no stored post-meeting result. Re-upload the transcript from Quick Research.",
        )

    try:
        return await _post.run({"meeting_id": meeting_id, "language": language, "model": model})
    except ValueError:
        # Fall through to ad-hoc synthesis if a brief exists for this id.
        pass

    brief = _load_brief_for_meeting(meeting_id)
    if brief is None:
        raise HTTPException(
            status_code=404,
            detail=f"meeting {meeting_id} not found and no brief on file. Run Quick Research first or pick a meeting from the workspace.",
        )

    try:
        return await _post.run_ad_hoc(
            {
                "company_name": brief.get("company_name") or "Customer",
                "meeting_title": brief.get("meeting_title") or "Discovery call",
                "industry": (brief.get("dossier") or {}).get("company_industry") or "",
                "size": (brief.get("dossier") or {}).get("company_size") or "",
                "notes": "Synthesised post-meeting from Quick Research brief; no recorded transcript.",
                "transcript_source": "synthesised_from_brief",
                "turns": _synth_turns_from_brief(brief),
                "language": language,
                "model": model,
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _load_brief_for_meeting(meeting_id: str) -> Optional[Dict[str, Any]]:
    """Return the persisted brief JSON for an ad-hoc meeting_id, or None."""
    path = settings.runtime_dir / "briefs" / f"{meeting_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
    # ES fallback: ad-hoc briefs are indexed too.
    try:
        from app.repositories.elasticsearch_repo import get_repo
        es = get_repo()
        if es.available:
            doc = es.get_brief(meeting_id) if hasattr(es, "get_brief") else None
            if doc:
                return doc
    except Exception:
        pass
    return None


def _synth_turns_from_brief(brief: Dict[str, Any]) -> List[Dict[str, str]]:
    """Build a minimal speaker-turn list from a brief's discovery + talking points
    so the post-meeting prompt has structured input to chew on."""
    customer_name = brief.get("company_name") or "Customer"
    turns: List[Dict[str, str]] = [
        {
            "speaker": "Field Engineer",
            "text": brief.get("headline") or f"Discovery call with {customer_name} on observability and platform consolidation.",
        }
    ]
    for section in brief.get("sections", []) or []:
        heading = (section.get("heading") or "").lower()
        bullets = section.get("bullets") or []
        if not bullets:
            continue
        if "discovery" in heading or "question" in heading:
            for b in bullets[:5]:
                turns.append({"speaker": "Field Engineer", "text": str(b)})
                turns.append({"speaker": f"{customer_name} contact", "text": "Acknowledged; we'll come back with a written answer after this call."})
        elif "talking" in heading or "pain" in heading or "risk" in heading:
            for b in bullets[:3]:
                turns.append({"speaker": f"{customer_name} contact", "text": str(b)})
    if len(turns) < 3:
        turns.append({"speaker": f"{customer_name} contact", "text": "We're looking to consolidate observability vendors and bring the cost down."})
        turns.append({"speaker": "Field Engineer", "text": "Understood. We'll follow up with a TCO comparison and a phased migration plan."})
    return turns


@router.post("/live-meeting/{meeting_id}/turn/{turn_index}")
async def run_live_turn(meeting_id: str, turn_index: int, language: str = "English", model: str = "") -> Dict[str, Any]:
    """Demo helper: replay a single transcript turn and return alerts."""
    transcript = synthetic.transcript_for_meeting(meeting_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail="transcript not found")
    turns = transcript.get("turns", [])
    if turn_index < 0 or turn_index >= len(turns):
        raise HTTPException(status_code=400, detail="turn_index out of range")
    return await _live.run(
        {
            "meeting_id": meeting_id,
            "turn": turns[turn_index],
            "recent_context": transcript_parser.recent_context(transcript, turn_index),
            "language": language,
            "model": model,
        }
    )


@router.post("/pre-meeting/scheduler/check-now")
async def scheduler_check_now(force: bool = False) -> Dict[str, Any]:
    """Manually trigger one scheduler cycle. Pass ?force=true to reset the dedup set."""
    from app.services import brief_scheduler
    if force:
        brief_scheduler._processed.clear()
    return await brief_scheduler.check_and_brief()
