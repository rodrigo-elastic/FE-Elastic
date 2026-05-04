"""
filename: routes_battlecards.py
description: Battlecard lookup endpoints. Reads from Elasticsearch when available, falls back to the seed JSON so the demo works offline.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.repositories.elasticsearch_repo import BATTLECARDS_SEED_PATH, get_repo as get_es_repo

router = APIRouter(prefix="/battlecards", tags=["battlecards"])


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


@router.get("")
async def list_battlecards() -> dict:
    es = get_es_repo()
    cards = es.list_battlecards() if es.available else []
    if not cards:
        cards = _load_seed()
    return {"items": cards, "source": "es" if es.available and cards else "seed"}


@router.get("/by-competitor/{name}")
async def get_by_competitor(name: str) -> dict:
    es = get_es_repo()
    card = None
    if es.available:
        card = es.find_battlecard(name)
    if not card:
        card = _match_local(name)
    if not card:
        raise HTTPException(status_code=404, detail=f"no battlecard for '{name}'")
    return card


@router.post("/reseed")
async def reseed_battlecards() -> dict:
    """Force-reindex all cards from the seed file. Idempotent. Used when the seed
    schema evolves (for example after the vertical/is_main_competitor expansion)."""
    es = get_es_repo()
    if not es.available:
        # Fall back to seed-only mode; nothing to do.
        return {"ok": False, "reason": "es_unavailable", "seed_count": len(_load_seed())}
    return es.reseed_battlecards()
