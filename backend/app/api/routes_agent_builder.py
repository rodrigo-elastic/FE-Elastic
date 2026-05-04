"""
filename: routes_agent_builder.py
description: REST surface that exposes Elastic Agent Builder integration to the FE Copilot UI. Endpoints: list registered tools/agents, get one agent, create a user agent, delete a user agent, send a message to any agent. Falls back to dry-run mode when KIBANA_API_KEY is absent. The master agent (fec_field_assistant) is reserved and cannot be deleted.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.2.0"
__status__ = "Development"

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.integrations import agent_builder as ab
from app.utils.logging import get_logger
from scripts.sync_agent_builder import MCP_TOOLS, build_agent_payload

log = get_logger(__name__)

router = APIRouter(prefix="/agent-builder", tags=["agent-builder"])


USER_AGENT_PREFIX = "fec_user_"
RESERVED_PREFIX = "fec_master_"
RESERVED_IDS = {"fec_field_assistant"}
SLUG_RE = re.compile(r"^[a-z0-9_]{3,40}$")
AGENT_ID_RE = re.compile(r"^[a-z0-9_-]{3,80}$")


class ConverseRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(None, max_length=120)
    agent_id: Optional[str] = Field("fec_field_assistant", max_length=120)


class CreateAgentRequest(BaseModel):
    name: str = Field(..., min_length=3, max_length=80)
    slug: str = Field(..., min_length=3, max_length=40)
    description: str = Field(..., min_length=10, max_length=400)
    system_prompt: str = Field(..., min_length=50, max_length=8000)
    tool_ids: List[str] = Field(..., min_length=1, max_length=12)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        if v != v.strip():
            raise ValueError("name must not have leading or trailing whitespace")
        return v

    @field_validator("slug")
    @classmethod
    def _validate_slug(cls, v: str) -> str:
        # Accept either with or without the user prefix; strip it for the raw slug check.
        bare = v[len(USER_AGENT_PREFIX):] if v.startswith(USER_AGENT_PREFIX) else v
        if not SLUG_RE.match(bare):
            raise ValueError("slug must match ^[a-z0-9_]{3,40}$ (lowercase, digits, underscore)")
        if bare in RESERVED_IDS or bare.startswith(RESERVED_PREFIX) or bare == "field_assistant":
            raise ValueError("slug is reserved")
        return bare


@router.get("/status")
def status() -> Dict[str, Any]:
    """Report whether Agent Builder is configured and reachable."""
    return {
        "live": ab.is_live(),
        "kibana_url": ab._base_url(),
        "configured_tools": [t["id"] for t in MCP_TOOLS],
        "configured_agent": build_agent_payload()["id"],
    }


@router.get("/tools")
def list_tools() -> Dict[str, Any]:
    return {"tools": ab.list_tools(), "live": ab.is_live()}


@router.get("/agents")
def list_agents() -> Dict[str, Any]:
    return {"agents": ab.list_agents(), "live": ab.is_live()}


@router.get("/agents/{agent_id}")
def get_agent(agent_id: str) -> Dict[str, Any]:
    if not AGENT_ID_RE.match(agent_id):
        raise HTTPException(status_code=422, detail="agent_id must match ^[a-z0-9_-]{3,80}$")
    if not ab.is_live():
        raise HTTPException(status_code=409, detail="Agent Builder not live: set KIBANA_API_KEY.")
    result = ab.get_agent(agent_id)
    if isinstance(result, dict) and result.get("error"):
        status_code = 404 if result.get("status") == 404 else 502
        detail = result.get("body") or result.get("exception") or "Agent Builder request failed"
        raise HTTPException(status_code=status_code, detail=str(detail)[:500])
    return result


@router.post("/agents")
def create_agent(req: CreateAgentRequest) -> Dict[str, Any]:
    if not ab.is_live():
        raise HTTPException(status_code=409, detail="Agent Builder not live: set KIBANA_API_KEY.")

    # Validate tool_ids against the registered Agent Builder tool catalogue.
    registered = ab.list_tools() or []
    registered_ids = {t.get("id") for t in registered if isinstance(t, dict) and t.get("id")}
    if not registered_ids:
        # Fallback: trust the local MCP_TOOLS catalogue if Kibana lookup is empty (rare race).
        registered_ids = {t["id"] for t in MCP_TOOLS}
    unknown = [tid for tid in req.tool_ids if tid not in registered_ids]
    if unknown:
        raise HTTPException(
            status_code=422,
            detail=f"unknown tool_ids: {','.join(unknown)}; valid: {','.join(sorted(registered_ids))}",
        )

    # Deduplicate while preserving caller order.
    seen: set = set()
    tool_ids: List[str] = []
    for tid in req.tool_ids:
        if tid in seen:
            continue
        seen.add(tid)
        tool_ids.append(tid)

    agent_id = USER_AGENT_PREFIX + req.slug
    payload: Dict[str, Any] = {
        "id": agent_id,
        "name": req.name,
        "description": req.description,
        "configuration": {
            "instructions": req.system_prompt,
            "tools": [{"tool_ids": tool_ids}],
        },
    }
    result = ab.upsert_agent(payload)
    if isinstance(result, dict) and result.get("error"):
        detail = result.get("body") or result.get("exception") or "Agent Builder upsert failed"
        raise HTTPException(status_code=502, detail=str(detail)[:500])

    kibana_url = (ab._base_url() or "").rstrip("/")
    return {
        "agent_id": agent_id,
        "name": req.name,
        "tool_count": len(tool_ids),
        "tool_ids": tool_ids,
        "kibana_url": f"{kibana_url}/app/agent_builder" if kibana_url else None,
    }


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: str) -> Dict[str, Any]:
    if not AGENT_ID_RE.match(agent_id):
        raise HTTPException(status_code=422, detail="agent_id must match ^[a-z0-9_-]{3,80}$")
    if not agent_id.startswith(USER_AGENT_PREFIX):
        raise HTTPException(
            status_code=403,
            detail=f"only user agents (id prefixed with '{USER_AGENT_PREFIX}') can be deleted",
        )
    if not ab.is_live():
        raise HTTPException(status_code=409, detail="Agent Builder not live: set KIBANA_API_KEY.")
    result = ab._request("DELETE", f"/api/agent_builder/agents/{agent_id}")
    if isinstance(result, dict) and result.get("error"):
        status_code = 404 if result.get("status") == 404 else 502
        detail = result.get("body") or result.get("exception") or "Agent Builder delete failed"
        raise HTTPException(status_code=status_code, detail=str(detail)[:500])
    return {"deleted": True, "agent_id": agent_id}


@router.post("/converse")
def converse(payload: ConverseRequest) -> Dict[str, Any]:
    if not ab.is_live():
        raise HTTPException(
            status_code=409,
            detail="Agent Builder not live: set KIBANA_API_KEY (and ensure stack version supports /api/agent_builder/*).",
        )
    target = payload.agent_id or "fec_field_assistant"
    if not AGENT_ID_RE.match(target):
        raise HTTPException(status_code=422, detail="agent_id must match ^[a-z0-9_-]{3,80}$")
    # Verify the agent actually exists in Kibana before paying the converse round-trip cost.
    agents = ab.list_agents() or []
    known_ids = {a.get("id") for a in agents if isinstance(a, dict) and a.get("id")}
    if known_ids and target not in known_ids:
        raise HTTPException(status_code=404, detail=f"agent '{target}' not found in Kibana")
    result = ab.converse(target, payload.message, payload.conversation_id)
    if isinstance(result, dict) and result.get("error"):
        # Surface upstream Kibana errors as 502 so the UI shows a real message instead of "(no response)".
        detail = result.get("body") or result.get("exception") or "Agent Builder request failed"
        raise HTTPException(status_code=502, detail=str(detail)[:500])
    return result
