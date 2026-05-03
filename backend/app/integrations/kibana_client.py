"""
filename: kibana_client.py
description: Thin Kibana HTTP wrapper. Idempotently creates the data views FE Copilot needs (briefs, post-meetings, audit, battlecards) plus an importable saved-objects dashboard.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)

DASHBOARD_PATH = Path(__file__).resolve().parents[2] / "data" / "seed" / "kibana-dashboard.ndjson"

DATA_VIEWS = [
    {"id": "fec-briefs", "title": "fec-briefs", "name": "FE Copilot Briefs", "time_field": "generated_at"},
    {"id": "fec-post-meetings", "title": "fec-post-meetings", "name": "FE Copilot Post-Meetings", "time_field": "generated_at"},
    {"id": "fec-audit", "title": "fec-audit", "name": "FE Copilot Audit", "time_field": "ts"},
    {"id": "fec-battlecards", "title": "fec-battlecards", "name": "FE Copilot Battlecards", "time_field": None},
]


def _headers() -> Dict[str, str]:
    return {"kbn-xsrf": "true", "Content-Type": "application/json"}


def ping() -> bool:
    try:
        r = httpx.get(f"{settings.kibana_url}/api/status", headers=_headers(), timeout=4.0)
        return r.status_code < 500
    except Exception:
        return False


def setup_data_views() -> Dict[str, Any]:
    """Idempotently create the four FE Copilot data views in Kibana."""
    base = settings.kibana_url
    statuses: List[Dict[str, Any]] = []
    if not ping():
        return {"ok": False, "error": "Kibana unreachable", "url": base, "items": []}

    for dv in DATA_VIEWS:
        body: Dict[str, Any] = {
            "data_view": {
                "title": dv["title"],
                "name": dv["name"],
                "id": dv["id"],
            },
            "override": True,
        }
        if dv["time_field"]:
            body["data_view"]["timeFieldName"] = dv["time_field"]
        try:
            r = httpx.post(
                f"{base}/api/data_views/data_view",
                headers=_headers(),
                json=body,
                timeout=10.0,
            )
            statuses.append(
                {
                    "id": dv["id"],
                    "name": dv["name"],
                    "status": r.status_code,
                    "ok": r.status_code in (200, 201),
                }
            )
        except Exception as exc:
            statuses.append({"id": dv["id"], "ok": False, "error": str(exc)})
            log.warning("kibana.create_data_view_failed", id=dv["id"], error=str(exc))
    return {"ok": True, "url": base, "items": statuses}


def import_dashboard() -> Dict[str, Any]:
    """Import the bundled dashboard ndjson into Kibana via the saved-objects API."""
    if not DASHBOARD_PATH.exists():
        return {"ok": False, "error": "dashboard ndjson missing", "items": []}
    if not ping():
        return {"ok": False, "error": "Kibana unreachable", "items": []}
    try:
        with DASHBOARD_PATH.open("rb") as fh:
            files = {"file": ("kibana-dashboard.ndjson", fh, "application/ndjson")}
            r = httpx.post(
                f"{settings.kibana_url}/api/saved_objects/_import",
                params={"overwrite": "true"},
                headers={"kbn-xsrf": "true"},
                files=files,
                timeout=20.0,
            )
        return {"ok": r.status_code == 200, "status": r.status_code, "body": r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text}
    except Exception as exc:
        log.warning("kibana.import_dashboard_failed", error=str(exc))
        return {"ok": False, "error": str(exc)}


def discover_url(index: str = "fec-briefs") -> str:
    return f"{settings.kibana_url}/app/discover#/?_g=()&_a=(index:{index})"
