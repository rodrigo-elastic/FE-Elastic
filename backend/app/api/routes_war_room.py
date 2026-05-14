"""
filename: routes_war_room.py
description: Deal Strategy War Room HTTP surface. One non-streaming POST that
runs the four specialist agents + synthesizer in parallel and returns the merged
dict; one Server-Sent Events GET that streams each agent's tokens live for the
SKO demo; one ad-hoc POST that builds a synthetic dossier from FE-typed input.
date: 13-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agents import war_room as wr
from app.config import settings
from app.repositories import synthetic
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/war-room", tags=["war-room"])


# ----------------------------------------------------------------------------- IO MODELS

class WarRoomRunIn(BaseModel):
    focus: Optional[str] = Field(default=None, description="Optional FE-supplied focus area.")


class WarRoomAdHocIn(BaseModel):
    company_name: str
    industry: Optional[str] = None
    size: Optional[str] = None
    tech_stack: Optional[str] = None
    notes: Optional[str] = None
    top_competitor: Optional[str] = None
    focus: Optional[str] = None


# ----------------------------------------------------------------------------- HELPERS

def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "ad-hoc"


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


def _dossier_for_meeting(meeting_id: str) -> Dict[str, Any]:
    meeting = synthetic.find_meeting(meeting_id)
    if meeting is None:
        raise HTTPException(status_code=404, detail=f"meeting {meeting_id} not found")
    company = synthetic.find_company(meeting["company_id"])
    if company is None:
        raise HTTPException(status_code=404, detail=f"company {meeting['company_id']} not found")
    return {
        "company": company,
        "meeting": meeting,
        "news": synthetic.news_for(company["id"]),
        "tickets": synthetic.tickets_for(company["id"]),
    }


def _dossier_for_ad_hoc(body: WarRoomAdHocIn) -> Dict[str, Any]:
    name = (body.company_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="company_name is required")
    slug_id = _slug(name)
    meeting_id = f"ad-hoc-war-room-{slug_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    obs_stack = _split_csv(body.tech_stack)
    if body.top_competitor and not any(body.top_competitor.lower() in s.lower() for s in obs_stack):
        obs_stack.append(body.top_competitor.strip())
    company = {
        "id": f"ad-hoc-{slug_id}",
        "name": name,
        "industry": (body.industry or "").strip() or "Unknown",
        "size": (body.size or "").strip() or "Unknown",
        "tech_stack": {"observability": obs_stack, "search": [], "cloud": [], "other": []},
        "description": (body.notes or "").strip() or None,
    }
    meeting = {
        "id": meeting_id,
        "company_id": company["id"],
        "title": f"Deal Strategy War Room - {name}",
        "notes": body.notes,
    }
    return {"company": company, "meeting": meeting, "news": [], "tickets": []}


def _persist(result: Dict[str, Any]) -> None:
    try:
        out_dir = settings.runtime_dir / "war_room"
        out_dir.mkdir(parents=True, exist_ok=True)
        meeting_id = result.get("meeting_id") or "unknown"
        (out_dir / f"{meeting_id}.json").write_text(
            json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except Exception as exc:
        log.warning("war_room.persist_failed", error=str(exc))


# ----------------------------------------------------------------------------- NON-STREAMING

@router.post("/{meeting_id}")
async def run_war_room_for_meeting(meeting_id: str, body: WarRoomRunIn) -> Dict[str, Any]:
    """Run all four specialists + synthesizer and return the merged JSON.

    Forces Haiku via the war_room module so this lands well under the 60s ECS edge timeout.
    """
    dossier = _dossier_for_meeting(meeting_id)
    result = await wr.run_war_room(
        dossier,
        focus=body.focus,
        audit_meta={"meeting_id": meeting_id, "company_id": dossier["company"]["id"]},
    )
    _persist(result)
    return result


@router.post("/ad-hoc")
async def run_war_room_ad_hoc(body: WarRoomAdHocIn) -> Dict[str, Any]:
    """Quick-Research-style ad-hoc war room from FE-typed input. Non-streaming."""
    dossier = _dossier_for_ad_hoc(body)
    result = await wr.run_war_room(
        dossier,
        focus=body.focus,
        audit_meta={"meeting_id": dossier["meeting"]["id"], "mode": "ad_hoc", "company_name": body.company_name},
    )
    result["ad_hoc"] = True
    _persist(result)
    return result


# ----------------------------------------------------------------------------- STREAMING

def _sse_pack(event: str, data: Dict[str, Any]) -> bytes:
    """Encode one Server-Sent Event frame. Each `data:` line is JSON."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode("utf-8")


def _chunk_for_sse(text: str, max_chunks: int = 3) -> List[str]:
    """Split a paragraph into 2-3 readable chunks so the UI feels streamed.

    Splits on sentence boundaries; falls back to whitespace if the text is one long line.
    """
    if not text:
        return [""]
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    parts = [p for p in parts if p]
    if len(parts) <= 1:
        # Single sentence: chunk by ~third widths.
        n = max(1, len(text) // max_chunks)
        parts = [text[i : i + n] for i in range(0, len(text), n)]
    if len(parts) > max_chunks:
        # Re-glue mid-sentences so we never emit more than max_chunks events.
        step = (len(parts) + max_chunks - 1) // max_chunks
        parts = [" ".join(parts[i : i + step]) for i in range(0, len(parts), step)]
    return parts[:max_chunks]


async def _stream_war_room(meeting_id: str, focus: Optional[str], dossier: Dict[str, Any]):
    """Generator: drives the four specialists + synthesizer and emits SSE events.

    Specialists fan out via asyncio.gather; each one drops its events onto a
    shared queue and the generator drains the queue in arrival order. Once all
    four are done we run the synthesizer and emit `synthesis_token` chunks.
    """
    queue: asyncio.Queue = asyncio.Queue()
    audit_meta = {"meeting_id": meeting_id, "company_id": (dossier.get("company") or {}).get("id")}

    results: Dict[str, Any] = {}

    async def _drive(role: str, coro_factory):
        await queue.put(("agent_started", {"role": role}))
        try:
            out = await coro_factory()
            results[role] = out
            text = getattr(out, "summary", None) or json.dumps(out.model_dump(), ensure_ascii=False)
            for chunk in _chunk_for_sse(text):
                await queue.put(("agent_token", {"role": role, "text": chunk}))
                # Tiny yield so chunks arrive as distinct flushes on the wire.
                await asyncio.sleep(0.02)
            await queue.put(("agent_done", {"role": role, "result": out.model_dump()}))
        except Exception as exc:
            log.warning("war_room.agent_failed", role=role, error=str(exc))
            await queue.put(("agent_error", {"role": role, "error": str(exc)}))

    async def _run_all():
        await asyncio.gather(
            _drive("competitive", lambda: wr.run_competitive(dossier, focus, audit_meta)),
            _drive("compliance", lambda: wr.run_compliance(dossier, focus, audit_meta)),
            _drive("cost", lambda: wr.run_cost(dossier, focus, audit_meta)),
            _drive("renewal", lambda: wr.run_renewal(dossier, focus, audit_meta)),
        )
        await queue.put(("__specialists_done__", {}))

    runner = asyncio.create_task(_run_all())

    # First frame: tell the client the run has started.
    yield _sse_pack("started", {"meeting_id": meeting_id, "focus": focus or ""})

    # Drain specialist events.
    while True:
        event, data = await queue.get()
        if event == "__specialists_done__":
            break
        yield _sse_pack(event, data)

    # All four done; run synthesizer and stream its chunks.
    if all(k in results for k in ("competitive", "compliance", "cost", "renewal")):
        yield _sse_pack("synthesis_started", {})
        try:
            synthesis = await wr.run_synthesizer(
                competitive=results["competitive"],
                compliance=results["compliance"],
                cost=results["cost"],
                renewal=results["renewal"],
                focus=focus,
                audit_meta=audit_meta,
            )
            # Stream the bullets one at a time so the UI can type each in turn.
            for i, bullet in enumerate(synthesis.bullets):
                yield _sse_pack("synthesis_token", {"index": i, "text": bullet})
                await asyncio.sleep(0.02)
            yield _sse_pack(
                "synthesis_done",
                {"result": synthesis.model_dump()},
            )

            final = {
                "meeting_id": meeting_id,
                "company_id": (dossier.get("company") or {}).get("id"),
                "company_name": (dossier.get("company") or {}).get("name"),
                "focus": focus,
                "competitive": results["competitive"].model_dump(),
                "compliance": results["compliance"].model_dump(),
                "cost": results["cost"].model_dump(),
                "renewal": results["renewal"].model_dump(),
                "synthesis": synthesis.model_dump(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            _persist(final)
        except Exception as exc:
            log.warning("war_room.synthesis_failed", error=str(exc))
            yield _sse_pack("synthesis_error", {"error": str(exc)})
    else:
        yield _sse_pack("synthesis_skipped", {"reason": "one or more specialists failed"})

    yield _sse_pack("done", {})
    # Ensure the background task is awaited so exceptions surface in the log.
    try:
        await runner
    except Exception:
        pass


@router.get("/{meeting_id}/stream")
async def stream_war_room(meeting_id: str, focus: Optional[str] = None) -> StreamingResponse:
    """Server-Sent Events: live thinking of the four specialists + synthesizer."""
    dossier = _dossier_for_meeting(meeting_id)
    return StreamingResponse(
        _stream_war_room(meeting_id, focus, dossier),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
