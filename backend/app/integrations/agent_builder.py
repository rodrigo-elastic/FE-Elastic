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
import pathlib
import threading
import time
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)

# ============================================================ Local agent store
# Persists user-created agents to disk so they survive restarts and appear in
# list_agents() even when Kibana Agent Builder is not enabled on this deployment.
_LOCAL_STORE_PATH = pathlib.Path(__file__).parent.parent.parent / "data" / "local_agents.json"
_store_lock = threading.Lock()


def _read_local_agents() -> List[Dict[str, Any]]:
    try:
        if _LOCAL_STORE_PATH.exists():
            return json.loads(_LOCAL_STORE_PATH.read_text()) or []
    except Exception:
        pass
    return []


def _write_local_agents(agents: List[Dict[str, Any]]) -> None:
    try:
        _LOCAL_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LOCAL_STORE_PATH.write_text(json.dumps(agents, indent=2))
    except Exception as exc:
        log.warning("agent_builder.local_store_write_failed", error=str(exc))


def _upsert_local_agent(agent: Dict[str, Any]) -> None:
    agent_id = agent.get("id", "")
    with _store_lock:
        agents = _read_local_agents()
        agents = [a for a in agents if a.get("id") != agent_id]
        agents.append(agent)
        _write_local_agents(agents)


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
    if isinstance(out, dict):
        # Kibana 9.x returns {"results": [...]}; older snapshots used {"data": [...]}.
        for key in ("results", "data"):
            if key in out:
                return out.get(key) or []
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
    kibana_agents: List[Dict[str, Any]] = []
    if isinstance(out, dict):
        for key in ("results", "data"):
            if key in out:
                kibana_agents = out.get(key) or []
                break
    elif isinstance(out, list):
        kibana_agents = out

    # Always merge local store so user-created agents appear even when Kibana
    # Agent Builder is disabled or returns an error.
    local = _read_local_agents()
    kibana_ids = {a.get("id") for a in kibana_agents if isinstance(a, dict)}
    merged = kibana_agents + [a for a in local if a.get("id") not in kibana_ids]
    return merged


def get_agent(agent_id: str) -> Dict[str, Any]:
    return _request("GET", f"/api/agent_builder/agents/{agent_id}")


def upsert_agent(agent: Dict[str, Any]) -> Dict[str, Any]:
    """PUT /api/agent_builder/agents/{id} rejects `id` (and any other fields not in the
    update schema) in the body, just like the tool endpoint. Strip them before PUT.
    Always persists to the local store so the agent survives Kibana being unavailable."""
    agent_id = agent.get("id")
    if not agent_id:
        raise ValueError("agent dict must include `id`")

    # Save locally first so it always survives regardless of Kibana status.
    _upsert_local_agent(agent)

    existing = get_agent(agent_id) if is_live() else None
    if existing and not existing.get("error") and not existing.get("dry_run"):
        update_body = {k: v for k, v in agent.items() if k not in ("id", "type")}
        result = _request("PUT", f"/api/agent_builder/agents/{agent_id}", update_body)
    else:
        result = _request("POST", "/api/agent_builder/agents", agent)

    # If Kibana returned an error, return a local-success response so callers
    # don't surface a confusing 502 when the feature simply isn't enabled.
    if isinstance(result, dict) and result.get("error"):
        log.info("agent_builder.kibana_unavailable_using_local", agent_id=agent_id)
        return {"ok": True, "local": True, "agent_id": agent_id, "name": agent.get("name", "")}
    return result


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


# ============================================================ Inference connectors =====
# These IDs match the preconfigured Anthropic connectors in the Elastic cluster.
CONNECTOR_OPUS = "Anthropic-Claude-Opus-4-5"
CONNECTOR_HAIKU = "Anthropic-Claude-Haiku-4-5"

_connector_cache: Dict[str, str] = {}


def discover_connectors() -> Dict[str, str]:
    """Discover Anthropic inference connectors registered in Kibana.

    Calls GET /api/actions/connectors, filters for connectors whose
    actionTypeId is '.inference' or whose name contains 'Anthropic' or
    'Claude' (case-insensitive), then resolves haiku and opus IDs by
    matching 'haiku' or 'opus' in the connector name.

    Falls back to the hardcoded CONNECTOR_HAIKU / CONNECTOR_OPUS constants
    when a matching connector is not found. Caches the result in
    _connector_cache so the API is only called once per process.

    Returns:
        {"opus": <connector_id>, "haiku": <connector_id>}
    """
    global _connector_cache
    if _connector_cache:
        return _connector_cache

    haiku_id: str = CONNECTOR_HAIKU
    opus_id: str = CONNECTOR_OPUS

    try:
        result = _request("GET", "/api/actions/connectors")
        connectors: List[Dict[str, Any]] = result if isinstance(result, list) else []

        anthropic_connectors = [
            c for c in connectors
            if c.get("actionTypeId") == ".inference"
            or "anthropic" in c.get("name", "").lower()
            or "claude" in c.get("name", "").lower()
        ]

        for c in anthropic_connectors:
            name_lower = c.get("name", "").lower()
            cid = c.get("id", "")
            if "haiku" in name_lower and cid:
                haiku_id = cid
            elif "opus" in name_lower and cid:
                opus_id = cid
    except Exception as exc:
        log.warning("discover_connectors: could not fetch connectors, using hardcoded fallbacks: %s", exc)

    _connector_cache = {"opus": opus_id, "haiku": haiku_id}
    log.debug("discover_connectors: opus=%s haiku=%s", opus_id, haiku_id)
    return _connector_cache


def get_connector_for(model: str) -> str:
    """Return the Kibana connector ID appropriate for *model*.

    Uses discover_connectors() (cached after the first call) so the correct
    ID is always returned even when the Kibana connector names differ from the
    hardcoded fallback constants.

    Args:
        model: A model identifier string (e.g. "claude-haiku-4-5").

    Returns:
        The haiku connector ID when 'haiku' appears in *model* (case-insensitive),
        otherwise the opus connector ID.
    """
    connectors = discover_connectors()
    if "haiku" in model.lower():
        return connectors["haiku"]
    return connectors["opus"]


def call_inference_connector(
    connector_id: str,
    messages: List[Dict[str, Any]],
    *,
    system: Optional[str] = None,
    max_tokens: int = 8192,
) -> Dict[str, Any]:
    """Execute an Elastic inference connector (.inference type) via Kibana Actions API.

    Sends messages in OpenAI-compatible format through Kibana so the call is tracked
    in Elastic's usage metrics rather than going directly to Anthropic.
    Returns the Kibana response dict or {"error": True, ...} on failure.
    """
    all_messages: List[Dict[str, Any]] = []
    if system:
        all_messages.append({"role": "system", "content": system})
    all_messages.extend(messages)

    body = {
        "params": {
            "subAction": "unified_completion",
            "subActionParams": {
                "body": {
                    "messages": all_messages,
                    "max_tokens": max_tokens,
                }
            },
        }
    }
    return _request("POST", f"/api/actions/connector/{connector_id}/_execute", body)


def ping_inference_connector(connector_id: str) -> Dict[str, Any]:
    start = time.perf_counter()
    try:
        result = call_inference_connector(connector_id, [{"role": "user", "content": "Say OK"}], max_tokens=20)
        end = time.perf_counter()
        latency_ms = round((end - start) * 1000)
        if result.get("error"):
            return {"ok": False, "connector_id": connector_id, "latency_ms": latency_ms, "error": str(result.get("error"))}
        model = result.get("data", {}).get("model", "")
        return {"ok": True, "connector_id": connector_id, "latency_ms": latency_ms, "model": model}
    except Exception as exc:
        end = time.perf_counter()
        latency_ms = round((end - start) * 1000)
        return {"ok": False, "connector_id": connector_id, "latency_ms": latency_ms, "error": str(exc)}
