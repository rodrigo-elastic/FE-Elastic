"""
filename: agent_builder.py
description: Thin Kibana Agent Builder client. Wraps the public REST surface (POST /api/agent_builder/tools, /agents, /converse, /skills) with idempotent upsert helpers and a dry-run fallback when KIBANA_API_KEY is not configured. Used to register the seven FE Copilot tools and one master agent in Elastic Agent Builder so they are discoverable from Kibana and invocable via the converse endpoint.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json", "kbn-xsrf": "fe-copilot"}
    key = getattr(settings, "kibana_api_key", "") or ""
    if key:
        h["Authorization"] = f"ApiKey {key}"
    return h


def _base_url() -> str:
    return getattr(settings, "kibana_url", "").rstrip("/") or "http://localhost:5601"


def is_live() -> bool:
    """True when a Kibana API key is configured. Otherwise we run in dry-run mode."""
    return bool(getattr(settings, "kibana_api_key", "") or "")


def _request(method: str, path: str, body: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """One-shot HTTP call. Returns the parsed JSON or a dry-run record when no key is set."""
    url = _base_url() + path
    if not is_live():
        log.info("agent_builder.dry_run", method=method, url=url, body=body)
        return {"dry_run": True, "method": method, "url": url, "body": body}
    # Converse calls invoke Claude through Kibana and may chain multiple tools, so allow up to 3 minutes.
    timeout = 180.0 if "/converse" in path else 30.0
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.request(method, url, headers=_headers(), json=body)
        if resp.status_code >= 400:
            log.warning(
                "agent_builder.http_error",
                method=method,
                url=url,
                status=resp.status_code,
                body=resp.text[:400],
            )
            return {"error": True, "status": resp.status_code, "body": resp.text[:1000]}
        if not resp.content:
            return {"ok": True, "status": resp.status_code}
        return resp.json()
    except Exception as exc:
        log.warning("agent_builder.exception", url=url, reason=str(exc))
        return {"error": True, "exception": str(exc)}


# ============================================================ Tools ===================


def list_tools() -> List[Dict[str, Any]]:
    out = _request("GET", "/api/agent_builder/tools")
    if isinstance(out, dict) and "data" in out:
        return out.get("data") or []
    if isinstance(out, list):
        return out
    return []


def get_tool(tool_id: str) -> Dict[str, Any]:
    return _request("GET", f"/api/agent_builder/tools/{tool_id}")


def upsert_tool(tool: Dict[str, Any]) -> Dict[str, Any]:
    """Create or update an Agent Builder tool. The tool dict must include `id`, `type`, `description`, and `configuration`.

    Kibana 9.3's PUT /api/agent_builder/tools/{id} rejects `id` and `type` in the body
    (those are inferred from the URL and from the existing object). Strip them before PUT.
    POST keeps the full payload for first-time creation.
    """
    tool_id = tool.get("id")
    if not tool_id:
        raise ValueError("tool dict must include `id`")
    existing = get_tool(tool_id) if is_live() else None
    if existing and not existing.get("error") and not existing.get("dry_run"):
        update_body = {k: v for k, v in tool.items() if k not in ("id", "type")}
        return _request("PUT", f"/api/agent_builder/tools/{tool_id}", update_body)
    return _request("POST", "/api/agent_builder/tools", tool)


def execute_tool(tool_id: str, params: Dict[str, Any]) -> Dict[str, Any]:
    return _request("POST", "/api/agent_builder/tools/execute", {"tool_id": tool_id, "params": params})


# ============================================================ Agents ==================


def list_agents() -> List[Dict[str, Any]]:
    out = _request("GET", "/api/agent_builder/agents")
    if isinstance(out, dict) and "data" in out:
        return out.get("data") or []
    if isinstance(out, list):
        return out
    return []


def get_agent(agent_id: str) -> Dict[str, Any]:
    return _request("GET", f"/api/agent_builder/agents/{agent_id}")


def upsert_agent(agent: Dict[str, Any]) -> Dict[str, Any]:
    """PUT /api/agent_builder/agents/{id} rejects `id` (and any other fields not in the
    update schema) in the body, just like the tool endpoint. Strip them before PUT."""
    agent_id = agent.get("id")
    if not agent_id:
        raise ValueError("agent dict must include `id`")
    existing = get_agent(agent_id) if is_live() else None
    if existing and not existing.get("error") and not existing.get("dry_run"):
        update_body = {k: v for k, v in agent.items() if k not in ("id", "type")}
        return _request("PUT", f"/api/agent_builder/agents/{agent_id}", update_body)
    return _request("POST", "/api/agent_builder/agents", agent)


# ============================================================ Skills ==================


def upsert_skill(skill: Dict[str, Any]) -> Dict[str, Any]:
    skill_id = skill.get("id")
    if not skill_id:
        raise ValueError("skill dict must include `id`")
    existing = _request("GET", f"/api/agent_builder/skills/{skill_id}") if is_live() else None
    if existing and not existing.get("error") and not existing.get("dry_run"):
        return _request("PUT", f"/api/agent_builder/skills/{skill_id}", skill)
    return _request("POST", "/api/agent_builder/skills", skill)


# ============================================================ Conversations ===========


def converse(agent_id: str, message: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
    body: Dict[str, Any] = {"agent_id": agent_id, "input": message}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return _request("POST", "/api/agent_builder/converse", body)
