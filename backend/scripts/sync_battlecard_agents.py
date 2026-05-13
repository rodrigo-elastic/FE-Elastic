"""
filename: sync_battlecard_agents.py
description: Per-competitor Agent Builder provisioner. Reads backend/data/seed/battlecards.json and, for each card, upserts one specialist Kibana Agent Builder agent (id fec_battlecard_<slug>) plus one canonical SKILL.md-shaped skill (id fec_battlecard_skill_<slug>) grounded exclusively in that competitor's battlecard content and the FE Copilot tool catalogue (fec_compare, fec_cost_calc, fec_proposal, fec_knowledge_search). Idempotent (upsert), dry-run safe when KIBANA_API_KEY is missing. Run with: PYTHONPATH=backend python -m scripts.sync_battlecard_agents.
date: 13-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from app.integrations import agent_builder as ab


SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "seed" / "battlecards.json"

# Tool ids every battlecard agent should be able to call. These are registered by
# scripts/sync_agent_builder.py and live in the MCP_TOOLS catalogue.
BATTLECARD_TOOL_IDS: List[str] = [
    "fec_compare",
    "fec_cost_calc",
    "fec_proposal",
    "fec_knowledge_search",
]

AGENT_ID_RE = re.compile(r"^[a-z0-9_-]{3,80}$")


def _slugify(raw: str) -> str:
    """Normalise a competitor_slug to match the Agent Builder id regex
    `[a-z0-9_-]{3,80}`. Spaces, dots, and other separators all collapse to `_`."""
    s = (raw or "").strip().lower()
    s = re.sub(r"[^a-z0-9_-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_-")
    return s or "competitor"


def agent_id_for(slug: str) -> str:
    aid = f"fec_battlecard_{_slugify(slug)}"
    return aid[:80]


def skill_id_for(slug: str) -> str:
    sid = f"fec_battlecard_skill_{_slugify(slug)}"
    return sid[:80]


# ============================================================ Prompt builders =========


def _format_talking_points(card: Dict[str, Any]) -> str:
    lines: List[str] = []
    for i, tp in enumerate(card.get("talking_points") or [], 1):
        angle = tp.get("angle", "").strip()
        claim = tp.get("claim", "").strip()
        proof = tp.get("proof", "").strip()
        lines.append(f"{i}. {angle}\n   - Claim: {claim}\n   - Proof: {proof}")
    return "\n".join(lines) or "(none)"


def _format_objections(card: Dict[str, Any]) -> str:
    lines: List[str] = []
    for i, ob in enumerate(card.get("common_objections") or [], 1):
        q = ob.get("q", "").strip()
        a = ob.get("a", "").strip()
        lines.append(f"{i}. Objection: {q}\n   Response: {a}")
    return "\n".join(lines) or "(none)"


def _format_bullets(items: List[str]) -> str:
    items = items or []
    return "\n".join(f"- {x}" for x in items) or "- (none)"


def build_instructions(card: Dict[str, Any]) -> str:
    competitor = card.get("competitor", "(unknown)")
    tagline = card.get("tagline", "")
    key_pain = card.get("key_pain", "")
    vertical = card.get("vertical", "")
    industries = card.get("industries") or []

    return (
        f"You are an Elastic competitive specialist focused exclusively on {competitor}. "
        f"Your job is to coach Elastic Field Engineers running head-to-head competitive motions against {competitor}: discovery, objection handling, displacement playbooks, renewal disruption, and cost reframes. "
        f"You are NOT a general-purpose assistant; if the question is not about Elastic vs {competitor} (or a closely related competitive topic), say so briefly and hand back to the master FE Copilot.\n\n"
        f"## Tagline\n{tagline}\n\n"
        f"## Key pain {competitor} leaves on the table\n{key_pain}\n\n"
        f"## Talking points (claim + proof you must cite when relevant)\n{_format_talking_points(card)}\n\n"
        f"## Elastic advantages\n{_format_bullets(card.get('elastic_advantages') or [])}\n\n"
        f"## Common {competitor} objections and how to handle them\n{_format_objections(card)}\n\n"
        f"## Discovery questions to ask the customer\n{_format_bullets(card.get('discovery_questions') or [])}\n\n"
        f"## Target context\nVertical: {vertical}. Industries: {', '.join(industries) or '(any)'}.\n\n"
        "## Rules of engagement\n"
        f"- Ground every competitive claim in the talking points or advantages listed above. If the question goes beyond those, say what you do not know rather than inventing a number or a feature.\n"
        f"- Be honest about gaps. If the battlecard does not claim Elastic wins on a given workload, do NOT claim it does; recommend a deeper discovery question instead.\n"
        f"- When the customer pushback matches a known objection, use the prepared response verbatim or paraphrased; always cite which objection you are answering.\n"
        f"- For cost or TCO questions, call the fec_cost_calc tool with the customer's daily ingest GB and retention months. Do not estimate from memory.\n"
        f"- For deep technical or feature-by-feature head-to-heads, call the fec_compare tool with competitor='{competitor}'.\n"
        f"- For docs-grounded answers (Elastic capabilities, sizing, ES|QL, ILM, detection rules), call fec_knowledge_search.\n"
        f"- For one-page customer-facing deliverables (proposal, displacement plan), call fec_proposal with the meeting_id the FE supplies.\n"
        f"- Refuse to give advice that contradicts this battlecard. If an FE pushes you to over-claim, point them back to the master FE Copilot.\n"
        f"- Never use the em dash character. Use commas, parentheses, colons, or periods.\n"
        f"- Keep responses tight: 4 to 8 sentences for chat, structured bullets when comparing.\n"
    )


def build_skill_markdown(card: Dict[str, Any]) -> str:
    """Canonical SKILL.md shape: YAML frontmatter (name, description, when_to_use, tool_ids) + markdown body."""
    competitor = card.get("competitor", "(unknown)")
    slug = card.get("competitor_slug", competitor)
    sid = skill_id_for(slug)
    when_to_use = (
        f"Use this skill whenever the Field Engineer asks anything about {competitor}: head-to-head comparisons, "
        f"renewal displacement, objection handling, discovery questions, cost reframes, or competitive proof points. "
        f"Activate on any mention of {competitor}, its product names, or its parent company."
    )
    description = (
        f"Elastic competitive playbook for {competitor}. Talking points, objection handlers, "
        f"discovery questions, and Say-This / Don't-Say-This guidance grounded in the FE Copilot battlecard."
    )

    frontmatter = (
        "---\n"
        f"name: {sid}\n"
        f"description: {description}\n"
        f"when_to_use: {when_to_use}\n"
        f"tool_ids: [{', '.join(BATTLECARD_TOOL_IDS)}]\n"
        "---\n\n"
    )

    say_this = []
    dont_say = []
    for tp in (card.get("talking_points") or [])[:3]:
        say_this.append(f"\"{tp.get('claim','').strip()}\" - cite the angle: {tp.get('angle','').strip()}.")
    for ob in (card.get("common_objections") or [])[:3]:
        dont_say.append(f"Do not concede on: \"{ob.get('q','').strip()}\" without using the prepared response.")

    body = (
        f"# {competitor} Competitive Playbook\n\n"
        f"**Tagline.** {card.get('tagline','')}\n\n"
        f"**Key pain.** {card.get('key_pain','')}\n\n"
        f"## Talking points\n{_format_talking_points(card)}\n\n"
        f"## Elastic advantages\n{_format_bullets(card.get('elastic_advantages') or [])}\n\n"
        f"## Objection handlers\n{_format_objections(card)}\n\n"
        f"## Discovery questions\n{_format_bullets(card.get('discovery_questions') or [])}\n\n"
        f"## Say this\n{_format_bullets(say_this)}\n\n"
        f"## Do not say this\n{_format_bullets(dont_say) if dont_say else '- (no canned traps for this competitor)'}\n\n"
        f"## Tools available\n"
        f"- fec_compare: structured technical and cost comparison Elastic vs {competitor}.\n"
        f"- fec_cost_calc: 12-month TCO with the customer's ingest GB and retention months.\n"
        f"- fec_knowledge_search: Elastic docs grounding for any product-specific follow-up.\n"
        f"- fec_proposal: one-page customer-facing displacement proposal.\n"
    )
    return frontmatter + body


# ============================================================ Payload builders =========


def build_agent_payload(card: Dict[str, Any]) -> Dict[str, Any]:
    competitor = card.get("competitor", "(unknown)")
    slug = card.get("competitor_slug", competitor)
    agent_id = agent_id_for(slug)
    if not AGENT_ID_RE.match(agent_id):
        raise ValueError(f"computed agent_id '{agent_id}' violates {AGENT_ID_RE.pattern}")

    labels = ["battlecard", "competitive"]
    vertical = card.get("vertical")
    if vertical:
        labels.append(vertical)
    for ind in card.get("industries") or []:
        labels.append(ind)
    # Dedupe preserving order.
    seen: set = set()
    labels = [x for x in labels if not (x in seen or seen.add(x))]

    tool_ids = list(BATTLECARD_TOOL_IDS)
    skill_id = skill_id_for(slug)

    description = (
        f"Elastic competitive specialist for {competitor}. "
        f"Tagline: {card.get('tagline','').strip()} "
        f"Grounded in the FE Copilot battlecard and the {', '.join(BATTLECARD_TOOL_IDS)} tools."
    )[:380]

    # Kibana 9.x agent schema accepts id/name/description/labels/configuration.{instructions,tools}.
    # `skill_ids` is NOT in the config schema on this stack; the skill content
    # is already baked into the instructions, so we keep the reference only in
    # the returned object for downstream tooling.
    payload: Dict[str, Any] = {
        "id": agent_id,
        "name": f"{competitor} Competitive Specialist",
        "description": description,
        "labels": labels,
        "configuration": {
            "instructions": build_instructions(card),
            "tools": [{"tool_ids": tool_ids}],
        },
    }
    # Stash for non-Kibana callers (the routes module reads skill_id_for() directly).
    payload["_skill_id"] = skill_id
    return payload


def build_skill_payload(card: Dict[str, Any]) -> Dict[str, Any]:
    competitor = card.get("competitor", "(unknown)")
    slug = card.get("competitor_slug", competitor)
    sid = skill_id_for(slug)

    return {
        "id": sid,
        "name": f"{competitor} Competitive Playbook",
        "description": (
            f"When the FE asks anything about {competitor} (head-to-head, renewal displacement, "
            f"objection handling, discovery, cost reframe), activate this playbook."
        ),
        "content": build_skill_markdown(card),
        "tool_ids": list(BATTLECARD_TOOL_IDS),
        "tags": ["battlecard", "competitive", _slugify(slug)],
    }


# ============================================================ Entry point ==============


def _load_seed() -> List[Dict[str, Any]]:
    if not SEED_PATH.exists():
        raise FileNotFoundError(f"battlecards seed not found at {SEED_PATH}")
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def _is_error(result: Any) -> bool:
    return isinstance(result, dict) and bool(result.get("error"))


def _existing(result: Any) -> bool:
    """Heuristic: a successful GET returns the resource id; a dry-run record returns dry_run=True."""
    if not isinstance(result, dict):
        return False
    if result.get("error") or result.get("dry_run"):
        return False
    return bool(result.get("id"))


def main() -> int:
    summary: Dict[str, Any] = {
        "created": [],
        "updated": [],
        "skills_synced": [],
        "skipped_dry_run": [],
        "errors": [],
    }

    cards = _load_seed()
    live = ab.is_live()

    if not live:
        print(
            "KIBANA_API_KEY not set; running in dry-run mode. No agents will be created in Kibana.",
            file=sys.stderr,
        )

    for card in cards:
        competitor = card.get("competitor", "(unknown)")
        slug = card.get("competitor_slug") or competitor
        try:
            skill_payload = build_skill_payload(card)
            agent_payload = build_agent_payload(card)
        except Exception as exc:
            summary["errors"].append({"competitor": competitor, "stage": "build", "error": str(exc)})
            continue

        if not live:
            summary["skipped_dry_run"].append(
                {"competitor": competitor, "agent_id": agent_payload["id"], "skill_id": skill_payload["id"]}
            )
            continue

        # Skill first so the agent can reference it. Some Kibana versions do not
        # expose /api/agent_builder/skills; a 404 is a soft-fail (the agent's
        # instructions already bake the playbook content in directly).
        skill_result = ab.upsert_skill(skill_payload)
        if _is_error(skill_result):
            status = skill_result.get("status") if isinstance(skill_result, dict) else None
            if status == 404:
                summary.setdefault("skills_unsupported", []).append(skill_payload["id"])
            else:
                summary["errors"].append({"competitor": competitor, "stage": "skill", "result": skill_result})
            # Continue with the agent anyway; the agent is still useful on its own.
        else:
            summary["skills_synced"].append(skill_payload["id"])

        # Was the agent already present before we PUT/POST?
        pre_existing = False
        try:
            pre = ab.get_agent(agent_payload["id"]) if live else None
            pre_existing = _existing(pre)
        except Exception:
            pre_existing = False

        # Strip private metadata keys before sending to Kibana (it rejects unknown fields).
        clean_agent = {k: v for k, v in agent_payload.items() if not k.startswith("_")}
        agent_result = ab.upsert_agent(clean_agent)
        if _is_error(agent_result):
            summary["errors"].append({"competitor": competitor, "stage": "agent", "result": agent_result})
            continue

        entry = {"competitor": competitor, "agent_id": agent_payload["id"]}
        if pre_existing:
            summary["updated"].append(entry)
        else:
            summary["created"].append(entry)

    summary["totals"] = {
        "cards": len(cards),
        "created": len(summary["created"]),
        "updated": len(summary["updated"]),
        "skills_synced": len(summary["skills_synced"]),
        "skills_unsupported": len(summary.get("skills_unsupported") or []),
        "errors": len(summary["errors"]),
        "dry_run": len(summary["skipped_dry_run"]),
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
