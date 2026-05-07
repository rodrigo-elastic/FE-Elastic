"""
filename: routes_audit.py
description: Read endpoints for the append-only audit log of Claude calls. Compliance surface.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json

from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
async def list_audit(limit: int = 200) -> dict:
    """Return the most recent audit entries (newest first), plus aggregate token usage."""
    path = settings.runtime_dir / "audit.jsonl"
    if not path.exists():
        return {"entries": [], "totals": {"calls": 0, "input_tokens": 0, "output_tokens": 0}}

    _SCRUB = {"company_name", "meeting_id", "company", "account_name"}
    entries: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            for k in _SCRUB:
                entry.pop(k, None)
            entries.append(entry)
        except json.JSONDecodeError:
            continue

    totals = {
        "calls": len(entries),
        "input_tokens": sum(int(e.get("input_tokens", 0)) for e in entries),
        "output_tokens": sum(int(e.get("output_tokens", 0)) for e in entries),
    }
    entries.reverse()
    return {"entries": entries[:limit], "totals": totals}
