"""
filename: routes_battlecards.py
description: Battlecard lookup endpoints. Reads from Elasticsearch when available, falls back to the seed JSON so the demo works offline. Also exposes the per-competitor Agent Builder specialist (fec_battlecard_<slug>) so the FE Copilot UI can route chat directly to the specialist when an FE opens a battlecard.
date: 13-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.2.0"
__status__ = "Development"

import json
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.integrations import agent_builder as ab
from app.repositories.elasticsearch_repo import BATTLECARDS_SEED_PATH, get_repo as get_es_repo
from scripts.sync_battlecard_agents import agent_id_for, skill_id_for

router = APIRouter(prefix="/battlecards", tags=["battlecards"])

MASTER_AGENT_ID = "fec_field_assistant"


def _load_seed() -> list:
    if not BATTLECARDS_SEED_PATH.exists():
        return []
    return json.loads(BATTLECARDS_SEED_PATH.read_text(encoding="utf-8"))


def _match_local(name: str) -> dict | None:
    """Case-insensitive substring match against the seed file."""
    name_l = (name or "").lower().strip()
    if not name_l:
        return None
    for card in _load_seed():
        if name_l == card.get("competitor_slug"):
            return card
        comp = card.get("competitor", "").lower()
        if comp in name_l or name_l in comp:
            return card
    return None


def _resolve_card(name: str) -> Optional[dict]:
    es = get_es_repo()
    card = None
    if es.available:
        card = es.find_battlecard(name)
    if not card:
        card = _match_local(name)
    return card


def _attach_agent_refs(card: Dict[str, Any]) -> Dict[str, Any]:
    slug = card.get("competitor_slug") or card.get("competitor") or ""
    card = dict(card)
    card["agent_id"] = agent_id_for(slug)
    card["skill_id"] = skill_id_for(slug)
    return card


@router.get("")
async def list_battlecards() -> dict:
    es = get_es_repo()
    cards = es.list_battlecards() if es.available else []
    if not cards:
        cards = _load_seed()
    cards = [_attach_agent_refs(c) for c in cards]
    return {"items": cards, "source": "es" if es.available and cards else "seed"}


@router.get("/by-competitor/{name}")
async def get_by_competitor(name: str) -> dict:
    card = _resolve_card(name)
    if not card:
        raise HTTPException(status_code=404, detail=f"no battlecard for '{name}'")
    return _attach_agent_refs(card)


@router.get("/by-competitor/{name}/agent")
async def get_competitor_agent(name: str) -> dict:
    """Return the specialist Agent Builder agent id for this competitor and
    whether it is actually deployed in Kibana. The FE Copilot UI calls this
    when the FE opens a battlecard so it knows which agent_id to converse with.
    """
    card = _resolve_card(name)
    if not card:
        raise HTTPException(status_code=404, detail=f"no battlecard for '{name}'")
    slug = card.get("competitor_slug") or card.get("competitor")
    aid = agent_id_for(slug)
    sid = skill_id_for(slug)

    available = False
    if ab.is_live():
        result = ab.get_agent(aid)
        available = isinstance(result, dict) and not result.get("error") and bool(result.get("id"))
    else:
        # Local-store fallback: an agent persisted on disk also counts as available.
        local = [a for a in (ab._read_local_agents() or []) if a.get("id") == aid]
        available = bool(local)

    kibana_url = (ab._base_url() or "").rstrip("/")
    return {
        "competitor": card.get("competitor"),
        "competitor_slug": slug,
        "agent_id": aid,
        "skill_id": sid,
        "available": available,
        "agent_url": f"{kibana_url}/app/agent_builder/agents/{aid}" if kibana_url else None,
        "fallback_agent_id": MASTER_AGENT_ID,
    }


class AskRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(None, max_length=120)


@router.post("/by-competitor/{name}/ask")
async def ask_competitor_agent(name: str, payload: AskRequest) -> dict:
    """Route a chat turn to the per-competitor specialist agent. Falls back to
    the master FE Copilot if the specialist is not deployed in Kibana."""
    card = _resolve_card(name)
    if not card:
        raise HTTPException(status_code=404, detail=f"no battlecard for '{name}'")
    if not ab.is_live():
        raise HTTPException(
            status_code=409,
            detail="Agent Builder not live: set KIBANA_API_KEY.",
        )

    slug = card.get("competitor_slug") or card.get("competitor")
    primary = agent_id_for(slug)

    # Resolve target: specialist if it exists in Kibana, otherwise master agent.
    target = primary
    specialist_available = False
    pre = ab.get_agent(primary)
    if isinstance(pre, dict) and not pre.get("error") and pre.get("id"):
        specialist_available = True
    else:
        target = MASTER_AGENT_ID

    result = ab.converse(target, payload.message, payload.conversation_id)
    if isinstance(result, dict) and result.get("error"):
        detail = result.get("body") or result.get("exception") or "Agent Builder request failed"
        raise HTTPException(status_code=502, detail=str(detail)[:500])

    # Annotate so the UI can show which agent handled the turn.
    if isinstance(result, dict):
        result.setdefault("_routing", {})
        result["_routing"].update(
            {
                "competitor": card.get("competitor"),
                "agent_id": target,
                "specialist_available": specialist_available,
                "fell_back_to_master": target == MASTER_AGENT_ID,
            }
        )
    return result


@router.post("/reseed")
async def reseed_battlecards() -> dict:
    """Force-reindex all cards from the seed file. Idempotent. Used when the seed
    schema evolves (for example after the vertical/is_main_competitor expansion)."""
    es = get_es_repo()
    if not es.available:
        # Fall back to seed-only mode; nothing to do.
        return {"ok": False, "reason": "es_unavailable", "seed_count": len(_load_seed())}
    return es.reseed_battlecards()
