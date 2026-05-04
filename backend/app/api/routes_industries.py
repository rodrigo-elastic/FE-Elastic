"""
filename: routes_industries.py
description: Industries catalog endpoints. Reads the canonical 20-industry catalog from data/seed/industries.json. Each industry links out to battlecards, demo scenarios, and FE Copilot tools so the page can drive cross-navigation across the app.
date: 04-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/industries", tags=["industries"])

# The canonical seed lives at <repo>/data/seed/industries.json. From this file
# (backend/app/api/routes_industries.py) the repo root is parents[3].
INDUSTRIES_SEED_PATH = (
    Path(__file__).resolve().parents[3] / "data" / "seed" / "industries.json"
)


def _load_seed() -> List[Dict[str, Any]]:
    if not INDUSTRIES_SEED_PATH.exists():
        return []
    try:
        data = json.loads(INDUSTRIES_SEED_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return data


@router.get("")
def list_industries() -> Dict[str, Any]:
    items = _load_seed()
    return {"items": items, "count": len(items), "source": "seed"}


@router.get("/{industry_id}")
def get_industry(industry_id: str) -> Dict[str, Any]:
    industry_id = (industry_id or "").strip().lower()
    if not industry_id:
        raise HTTPException(status_code=400, detail="industry_id is required")
    for item in _load_seed():
        if item.get("id", "").lower() == industry_id:
            return item
    raise HTTPException(status_code=404, detail=f"industry not found: {industry_id}")
