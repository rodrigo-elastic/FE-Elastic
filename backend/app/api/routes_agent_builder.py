"""
filename: routes_agent_builder.py
description: REST surface that exposes Elastic Agent Builder integration to the FE Copilot UI. Endpoints: list registered tools/agents, trigger a sync, send a message to the master agent. Falls back to dry-run mode when KIBANA_API_KEY is absent.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.integrations import agent_builder as ab
from app.utils.logging import get_logger
from scripts.sync_agent_builder import MCP_TOOLS, build_agent_payload

log = get_logger(__name__)

router = APIRouter(prefix="/agent-builder", tags=["agent-builder"])


class ConverseRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    conversation_id: Optional[str] = Field(None, max_length=120)
    agent_id: Optional[str] = Field("fec_field_assistant", max_length=120)


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


@router.post("/converse")
def converse(payload: ConverseRequest) -> Dict[str, Any]:
    if not ab.is_live():
        raise HTTPException(
            status_code=409,
            detail="Agent Builder not live: set KIBANA_API_KEY (and ensure stack version supports /api/agent_builder/*).",
        )
    result = ab.converse(payload.agent_id, payload.message, payload.conversation_id)
    if isinstance(result, dict) and result.get("error"):
        # Surface upstream Kibana errors as 502 so the UI shows a real message instead of "(no response)".
        detail = result.get("body") or result.get("exception") or "Agent Builder request failed"
        raise HTTPException(status_code=502, detail=str(detail)[:500])
    return result
