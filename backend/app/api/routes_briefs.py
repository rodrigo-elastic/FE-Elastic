"""
filename: routes_briefs.py
description: Endpoints for fetching generated briefs and downloading the PDF artifact.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.config import settings
from app.repositories.elasticsearch_repo import get_repo as get_es_repo

router = APIRouter(prefix="/briefs", tags=["briefs"])


class PatchActionItem(BaseModel):
    completed: bool


def _brief_path(meeting_id: str) -> Path:
    return settings.runtime_dir / "briefs" / f"{meeting_id}.json"


def _post_path(meeting_id: str) -> Path:
    return settings.runtime_dir / "post_meeting" / f"{meeting_id}.json"


@router.get("")
async def list_briefs(source: str = "auto") -> dict:
    """History view: briefs and post-meeting outputs.

    `source` query param: `es` forces Elasticsearch, `disk` forces filesystem,
    `auto` (default) prefers ES when available and merges any disk-only items
    so artifacts created before ES came online are still listed.
    """
    es = get_es_repo()
    use_es = source == "es" or (source == "auto" and es.available)

    items: list[dict] = []
    seen_ids: set[str] = set()
    actual_source = "es" if use_es else "disk"

    if use_es:
        for rec in es.list_briefs():
            mid = rec.get("meeting_id")
            seen_ids.add(("brief", mid))
            items.append(
                {
                    "type": "pre_meeting",
                    "meeting_id": mid,
                    "company_name": rec.get("company_name") or rec.get("company_id"),
                    "headline": rec.get("headline"),
                    "ad_hoc": bool(rec.get("ad_hoc")),
                    "generated_at": rec.get("generated_at"),
                    "source": "es",
                }
            )
        for rec in es.list_post_meetings():
            mid = rec.get("meeting_id")
            seen_ids.add(("post", mid))
            items.append(
                {
                    "type": "post_meeting",
                    "meeting_id": mid,
                    "company_id": rec.get("company_id"),
                    "summary": (rec.get("summary") or "")[:160],
                    "action_items": len(rec.get("action_items") or []),
                    "done_tasks_count": sum(1 for a in (rec.get("action_items") or []) if a.get("completed")),
                    "open_tasks_count": len(rec.get("action_items") or []) - sum(1 for a in (rec.get("action_items") or []) if a.get("completed")),
                    "generated_at": rec.get("generated_at"),
                    "source": "es",
                }
            )

    # When source==auto we still walk disk so brand-new local artifacts surface
    # immediately even if the bulk reindex hasn't run yet.
    if source != "es":
        briefs_dir = settings.runtime_dir / "briefs"
        post_dir = settings.runtime_dir / "post_meeting"
        if briefs_dir.exists():
            for p in briefs_dir.glob("*.json"):
                try:
                    rec = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if ("brief", rec.get("meeting_id")) in seen_ids:
                    continue
                items.append(
                    {
                        "type": "pre_meeting",
                        "meeting_id": rec.get("meeting_id"),
                        "company_name": rec.get("company_name") or rec.get("company_id"),
                        "headline": rec.get("headline"),
                        "ad_hoc": bool(rec.get("ad_hoc")),
                        "generated_at": rec.get("generated_at"),
                        "source": "disk",
                    }
                )
        if post_dir.exists():
            for p in post_dir.glob("*.json"):
                try:
                    rec = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if ("post", rec.get("meeting_id")) in seen_ids:
                    continue
                items.append(
                    {
                        "type": "post_meeting",
                        "meeting_id": rec.get("meeting_id"),
                        "company_id": rec.get("company_id"),
                        "summary": (rec.get("summary") or "")[:160],
                        "action_items": len(rec.get("action_items") or []),
                        "done_tasks_count": sum(1 for a in (rec.get("action_items") or []) if a.get("completed")),
                        "open_tasks_count": len(rec.get("action_items") or []) - sum(1 for a in (rec.get("action_items") or []) if a.get("completed")),
                        "generated_at": rec.get("generated_at"),
                        "source": "disk",
                    }
                )

    items.sort(key=lambda x: x.get("generated_at") or "", reverse=True)
    return {"items": items, "source": actual_source, "es_available": es.available}


@router.post("/reindex")
async def reindex_disk_to_es() -> dict:
    """Push every brief and post-meeting on disk into Elasticsearch."""
    es = get_es_repo()
    if not es.available and not es.reconnect():
        raise HTTPException(status_code=503, detail="elasticsearch is not reachable")
    es.ensure_indices()
    counts = es.reindex_from_disk()
    return {"ok": True, "indexed": counts, "es_url": settings.elasticsearch_url}


_RESERVED_BRIEF_PATHS = {"reindex"}


@router.get("/{meeting_id}")
async def get_brief(meeting_id: str, source: str = "auto") -> dict:
    """Fetch a single brief. ES first when available, falls back to disk.

    Returns 200 with `{exists: false}` when not generated yet (instead of 404)
    so the dashboard does not pollute the browser console with expected misses.
    Reserved sibling keywords (e.g. `reindex`) raise 405 so a GET on a POST-only
    path is not silently consumed by the path parameter.
    """
    if meeting_id in _RESERVED_BRIEF_PATHS:
        raise HTTPException(
            status_code=405,
            detail=f"GET not allowed on /briefs/{meeting_id}; this path accepts POST only",
            headers={"Allow": "POST"},
        )
    es = get_es_repo()
    if source != "disk" and es.available:
        rec = es.get_brief(meeting_id)
        if rec is not None:
            rec["_source_used"] = "es"
            return rec
    path = _brief_path(meeting_id)
    if not path.exists():
        return {"exists": False, "meeting_id": meeting_id}
    rec = json.loads(path.read_text(encoding="utf-8"))
    rec["_source_used"] = "disk"
    rec["exists"] = True
    return rec


@router.get("/{meeting_id}/artifact")
async def download_artifact(meeting_id: str):
    path = _brief_path(meeting_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="brief not generated yet")
    record = json.loads(path.read_text(encoding="utf-8"))
    artifact = Path(record["artifact_path"])
    if not artifact.exists():
        raise HTTPException(status_code=404, detail="artifact missing")
    media_type = "application/pdf" if artifact.suffix == ".pdf" else "text/html"
    return FileResponse(path=str(artifact), media_type=media_type, filename=artifact.name)


@router.get("/{meeting_id}/post")
async def get_post_meeting(meeting_id: str, source: str = "auto") -> dict:
    es = get_es_repo()
    if source != "disk" and es.available:
        rec = es.get_post_meeting(meeting_id)
        if rec is not None:
            rec["_source_used"] = "es"
            # Compute task completion counts
            items = rec.get("action_items") or []
            rec["done_tasks_count"] = sum(1 for a in items if a.get("completed"))
            rec["open_tasks_count"] = len(items) - rec["done_tasks_count"]
            return rec
    path = settings.runtime_dir / "post_meeting" / f"{meeting_id}.json"
    if not path.exists():
        return {"exists": False, "meeting_id": meeting_id}
    rec = json.loads(path.read_text(encoding="utf-8"))
    rec["_source_used"] = "disk"
    rec["exists"] = True
    # Compute task completion counts
    items = rec.get("action_items") or []
    rec["done_tasks_count"] = sum(1 for a in items if a.get("completed"))
    rec["open_tasks_count"] = len(items) - rec["done_tasks_count"]
    return rec


@router.patch("/{meeting_id}/action-items/{idx}")
async def patch_action_item(meeting_id: str, idx: int, body: PatchActionItem) -> dict:
    """Mark a single action item complete or incomplete. Updates ES, disk, and SFDC mock."""
    es = get_es_repo()

    rec = None
    if es.available:
        rec = es.get_post_meeting(meeting_id)
    if rec is None:
        path = _post_path(meeting_id)
        if not path.exists():
            raise HTTPException(status_code=404, detail="Post-meeting record not found")
        rec = json.loads(path.read_text(encoding="utf-8"))

    items = rec.get("action_items") or []
    if idx < 0 or idx >= len(items):
        raise HTTPException(status_code=422, detail=f"Index {idx} out of range (0-{len(items) - 1})")

    items[idx]["completed"] = body.completed
    if body.completed:
        items[idx]["completed_at"] = datetime.now(timezone.utc).isoformat()
    else:
        items[idx].pop("completed_at", None)
    rec["action_items"] = items

    # Persist to disk
    disk_path = _post_path(meeting_id)
    disk_path.parent.mkdir(parents=True, exist_ok=True)
    disk_path.write_text(json.dumps(rec, default=str) + "\n", encoding="utf-8")

    # Persist to ES
    if es.available:
        try:
            es._client.index(index="fec-post-meetings", id=meeting_id, document=rec)  # noqa: SLF001
        except Exception:
            pass

    # Update SFDC mock task status
    sfdc_ids = rec.get("salesforce_task_ids") or []
    if idx < len(sfdc_ids):
        from app.integrations import salesforce_mock
        salesforce_mock.update_task(sfdc_ids[idx], status="Completed" if body.completed else "Not Started")

    return {"ok": True, "idx": idx, "completed": body.completed, "item": items[idx]}
