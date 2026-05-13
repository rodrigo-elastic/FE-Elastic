"""
filename: battlecard_skill_builder.py
description: Pure-function builder that turns a battlecard dict (from
    backend/data/seed/battlecards.json) into the JSON payload accepted by
    POST /api/agent_builder/skills. Implements the conventions documented in
    docs/battlecard_skills_template.md (id prefix fec_battlecard_skill_,
    canonical tool_ids, label/metadata shape, nine-section body). Zero side
    effects: no Kibana call, no I/O, no logging. The provisioner
    (backend/scripts/sync_battlecard_agents.py) is the only caller and is
    responsible for calling agent_builder.upsert_skill() with the result.
date: 13-05-2026
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

__author__ = "Rodrigo Careaga"
__version__ = "0.1.0"

# Canonical tool_ids every competitive battlecard skill exposes. Order matters
# for diff stability (the provisioner is idempotent and re-POSTs on hash change).
# See docs/battlecard_skills_template.md section 3.5.
CANONICAL_TOOL_IDS: List[str] = [
    "fec_compare",
    "fec_cost_calc",
    "fec_proposal",
    "fec_knowledge_search",
]

ID_PREFIX = "fec_battlecard_skill_"
SKILL_VERSION = "0.1.0"
EM_DASH = "—"


def _slugify(value: str) -> str:
    """Lowercase + non-alphanumeric -> underscore. Matches the id convention in
    docs/battlecard_skills_template.md section 3.1."""
    return re.sub(r"[^a-z0-9]+", "_", (value or "").lower()).strip("_")


def _no_em_dash(text: str) -> str:
    """Per repo-wide style: replace U+2014 with a regular hyphen."""
    return (text or "").replace(EM_DASH, "-")


def _build_labels(card: Dict[str, Any]) -> List[str]:
    """Compose labels per section 3.4 of the template: competitive + vertical +
    every industry + main-competitor when flagged. Dedup while preserving order."""
    labels: List[str] = ["competitive"]
    if card.get("is_main_competitor"):
        labels.append("main-competitor")
    vertical = (card.get("vertical") or "").strip()
    if vertical:
        labels.append(vertical)
    for ind in card.get("industries") or []:
        if ind:
            labels.append(ind)
    seen: set[str] = set()
    out: List[str] = []
    for lab in labels:
        if lab not in seen:
            out.append(lab)
            seen.add(lab)
    return out


def _build_content(card: Dict[str, Any]) -> str:
    """Render the nine-section body defined in section 3.7 of the template."""
    competitor = card.get("competitor") or "the competitor"
    card_id = card.get("id") or f"battlecard-{card.get('competitor_slug', 'unknown')}"
    tagline = (card.get("tagline") or "n/a").strip()
    key_pain = (card.get("key_pain") or "n/a").strip()

    tp_lines: List[str] = []
    for tp in card.get("talking_points") or []:
        angle = (tp.get("angle") or "").strip()
        claim = (tp.get("claim") or "").strip()
        proof = (tp.get("proof") or "").strip()
        tp_lines.append(f"- {angle} - {claim} (Proof: {proof})")
    tp_block = "\n".join(tp_lines) or "- n/a"

    adv_lines = [f"- {a}" for a in (card.get("elastic_advantages") or []) if a]
    adv_block = "\n".join(adv_lines) or "- n/a"

    obj_lines: List[str] = []
    for obj in card.get("common_objections") or []:
        q = (obj.get("q") or "").strip()
        a = (obj.get("a") or "").strip()
        obj_lines.append(f"- Q: {q}\n  A: {a}")
    obj_block = "\n".join(obj_lines) or "- n/a"

    dq_lines = [f"- {q}" for q in (card.get("discovery_questions") or []) if q]
    dq_block = "\n".join(dq_lines) or "- n/a"

    when = (
        f"Activate when the user asks about Elastic versus {competitor}, references "
        f"{competitor}-specific terminology, or needs talking points / objection "
        f"handling for a {competitor} replacement. Grounded in the {card_id} battlecard."
    )

    body = (
        f"# When to use this skill\n{when}\n\n"
        f"# Tagline\n{tagline}\n\n"
        f"# Key pain\n{key_pain}\n\n"
        f"# Talking points\n{tp_block}\n\n"
        f"# Elastic advantages\n{adv_block}\n\n"
        f"# Common objections\n{obj_block}\n\n"
        f"# Discovery questions\n{dq_block}\n\n"
        f"# Follow-up tools\n"
        f"- fec_compare: structured technical and cost head-to-head Elastic vs {competitor}.\n"
        f"- fec_cost_calc: TCO model when the conversation pivots to pricing.\n"
        f"- fec_proposal: one-page customer-ready output when the rep wants to close the loop.\n"
        f"- fec_knowledge_search: backstop for product questions the battlecard does not cover.\n\n"
        f"# Style\nNever use the em dash character. Always cite {card_id} in the "
        f"sources array when this skill grounded the answer."
    )
    return _no_em_dash(body)


def build_skill_payload(card: Dict[str, Any]) -> Dict[str, Any]:
    """Translate a battlecard dict into the JSON body for
    POST /api/agent_builder/skills. Pure: returns a dict, raises on missing
    required inputs, performs no network or filesystem I/O.

    See docs/battlecard_skills_template.md (sections 2-3) for the full spec.
    """
    competitor = (card.get("competitor") or "").strip()
    slug = (card.get("competitor_slug") or "").strip() or _slugify(competitor)
    if not competitor or not slug:
        raise ValueError("battlecard requires competitor and competitor_slug")
    slug = _slugify(slug)
    card_id = card.get("id") or f"battlecard-{slug}"

    skill_id = f"{ID_PREFIX}{slug}"
    name = f"Battlecard: {competitor}"
    description = (
        f"Activate when the user asks about Elastic versus {competitor}, references "
        f"{competitor}-specific terminology, or needs talking points / objection "
        f"handling for a {competitor} replacement. Grounded in the {card_id} battlecard."
    )

    payload: Dict[str, Any] = {
        "id": skill_id,
        "name": name,
        "description": _no_em_dash(description),
        "tool_ids": list(CANONICAL_TOOL_IDS),
        "labels": _build_labels(card),
        "metadata": {
            "author": "fe-copilot",
            "version": SKILL_VERSION,
            "competitor": competitor,
            "vertical": card.get("vertical") or "",
            "industries": list(card.get("industries") or []),
            "is_main_competitor": bool(card.get("is_main_competitor")),
        },
        "content": _build_content(card),
    }
    return payload


__all__ = ["build_skill_payload", "CANONICAL_TOOL_IDS", "ID_PREFIX"]
