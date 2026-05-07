"""
filename: routes_autoops.py
description: AutoOps webhook relay and alert surface for FE Copilot. Receives
AutoOps webhook payloads (Slack/PagerDuty-style JSON), persists them to a local
store, and exposes them as a REST surface so the meeting brief and Field
Assistant can show live cluster health signals. Pre-populated with demo data
from the fe-summit-hackathon-ed0e8e cluster.
date: 05-06-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import pathlib
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/autoops", tags=["autoops"])

_STORE_PATH = pathlib.Path(__file__).parent.parent.parent.parent / "data" / "autoops_events.json"
_store_lock = threading.Lock()

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


# ── Local store helpers ────────────────────────────────────────────────────────

def _read() -> List[Dict[str, Any]]:
    try:
        if _STORE_PATH.exists():
            return json.loads(_STORE_PATH.read_text()) or []
    except Exception:
        pass
    return []


def _write(events: List[Dict[str, Any]]) -> None:
    try:
        _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STORE_PATH.write_text(json.dumps(events, indent=2))
    except Exception as exc:
        log.warning("autoops.store_write_failed", error=str(exc))


# ── Pydantic models ────────────────────────────────────────────────────────────

class AutoOpsWebhookPayload(BaseModel):
    """Matches the AutoOps outbound webhook shape (Slack/generic JSON connector)."""
    id: Optional[str] = Field(None, max_length=80)
    cluster_id: Optional[str] = Field(None, max_length=120)
    cluster_name: Optional[str] = Field(None, max_length=120)
    region: Optional[str] = Field(None, max_length=60)
    severity: Optional[str] = Field("info", max_length=20)
    category: Optional[str] = Field(None, max_length=60)
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    recommendation: Optional[str] = Field(None, max_length=1000)
    timestamp: Optional[str] = Field(None, max_length=40)
    resolved: bool = False
    resolved_at: Optional[str] = Field(None, max_length=40)


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/webhook")
def receive_webhook(payload: AutoOpsWebhookPayload) -> Dict[str, Any]:
    """Receive an AutoOps outbound webhook event and persist it to the local store."""
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event: Dict[str, Any] = payload.model_dump()
    if not event.get("id"):
        event["id"] = f"ao_{now.replace(':', '').replace('-', '')[:15]}"
    if not event.get("timestamp"):
        event["timestamp"] = now

    with _store_lock:
        events = _read()
        events = [e for e in events if e.get("id") != event["id"]]
        events.insert(0, event)
        _write(events[:100])

    log.info("autoops.webhook_received", event_id=event["id"], severity=event.get("severity"))
    return {"ok": True, "event_id": event["id"]}


@router.get("/alerts")
def list_alerts(limit: int = 20, cluster_id: Optional[str] = None) -> Dict[str, Any]:
    """Return recent AutoOps alerts, sorted by severity then recency."""
    events = _read()
    if cluster_id:
        events = [e for e in events if e.get("cluster_id") == cluster_id]
    events = sorted(
        events,
        key=lambda e: (
            SEVERITY_ORDER.get(e.get("severity", "info"), 99),
            e.get("timestamp", ""),
        ),
        reverse=False,
    )
    return {
        "alerts": events[:limit],
        "total": len(events),
        "cluster": cluster_id or "all",
    }


@router.get("/summary")
def summary() -> Dict[str, Any]:
    """Return a compact summary for embedding in meeting briefs and agent context."""
    events = _read()
    active = [e for e in events if not e.get("resolved")]
    resolved = [e for e in events if e.get("resolved")]

    criticals = [e for e in active if e.get("severity") == "critical"]
    warnings = [e for e in active if e.get("severity") == "warning"]

    clusters = list({e.get("cluster_name") or e.get("cluster_id") for e in events if e.get("cluster_id")})

    top_alerts = sorted(
        active,
        key=lambda e: SEVERITY_ORDER.get(e.get("severity", "info"), 99),
    )[:3]

    return {
        "clusters": clusters,
        "active_count": len(active),
        "resolved_count": len(resolved),
        "criticals": len(criticals),
        "warnings": len(warnings),
        "top_alerts": [
            {
                "title": e.get("title"),
                "severity": e.get("severity"),
                "category": e.get("category"),
                "recommendation": e.get("recommendation"),
                "timestamp": e.get("timestamp"),
            }
            for e in top_alerts
        ],
        "health": "critical" if criticals else ("warning" if warnings else "green"),
    }


@router.get("/competitive")
def competitive_card() -> Dict[str, Any]:
    """Return the AutoOps vs Splunk competitive talking points for brief injection."""
    return {
        "competitor": "Splunk",
        "differentiator": "AutoOps",
        "points": [
            "AutoOps is free for all Elastic tiers - Cloud and self-managed. Splunk has no equivalent native diagnostic tool.",
            "Each Splunk cluster health check requires a Professional Services engagement (~$15k-25k per engagement). AutoOps runs continuously, 24/7, at zero cost.",
            "AutoOps monitors 100+ metrics and surfaces root-cause recommendations with ES|QL commands ready to paste. Splunk relies on manual SPL queries to diagnose the same issues.",
            "AutoOps covers JVM pressure, shard allocation, slow queries, indexing bottlenecks, and mapping issues - all in one view. Splunk requires separate tools for cluster ops.",
        ],
        "proof_url": "https://www.elastic.co/platform/autoops",
    }
