"""
filename: routes_agent_builder.py
description: REST surface that exposes Elastic Agent Builder integration to the FE Copilot UI. Endpoints: list registered tools/agents, get one agent, create a user agent, delete a user agent, send a message to any agent. Falls back to dry-run mode when KIBANA_API_KEY is absent. The master agent (fec_field_assistant) is reserved and cannot be deleted.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.2.0"
__status__ = "Development"

import json
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
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


@router.get("/inference-health")
def inference_health() -> Dict[str, Any]:
    if not ab.is_live():
        return {"connectors": [], "overall": "not_configured", "live": False}
    results = []
    for connector_id in (ab.CONNECTOR_OPUS, ab.CONNECTOR_HAIKU):
        results.append(ab.ping_inference_connector(connector_id))
    ok_count = sum(1 for r in results if r.get("ok"))
    if ok_count == 2:
        overall = "healthy"
    elif ok_count == 1:
        overall = "degraded"
    else:
        overall = "down"
    return {"connectors": results, "overall": overall, "live": ab.is_live()}


@router.get("/tools")
def list_tools() -> Dict[str, Any]:
    tools = ab.list_tools()
    if not tools:
        # Kibana not configured or returned empty - serve the local MCP catalogue
        # so the Agent Builder UI always has a tool picker.
        tools = [{"id": t["id"], "name": t["name"], "description": t["description"]} for t in MCP_TOOLS]
    return {"tools": tools, "live": ab.is_live()}


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


@router.get("/kibana-view", response_class=HTMLResponse)
def kibana_view() -> HTMLResponse:
    """Kibana-styled agents list page for the autopilot demo.
    Fetches agents from the backend (same source as Kibana) and renders
    a convincing Agent Builder UI without requiring browser login."""
    agents = ab.list_agents() or []
    kibana_url = ab._base_url() or ""
    agents_json = json.dumps(agents)
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>Elastic Kibana · Agent Builder</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Inter',sans-serif;background:#07080c;color:#d4d9e0;min-height:100vh}}
  .kbn-chrome{{display:flex;flex-direction:column;height:100vh}}
  .kbn-header{{background:#1a1b20;border-bottom:1px solid #2a2b30;padding:0 20px;height:48px;display:flex;align-items:center;gap:16px;flex-shrink:0}}
  .kbn-logo{{display:flex;align-items:center;gap:8px;font-weight:700;font-size:13px;color:#fff;letter-spacing:.02em}}
  .kbn-logo-mark{{width:24px;height:24px;background:linear-gradient(135deg,#00BFB3,#0077CC);border-radius:4px;display:flex;align-items:center;justify-content:center;font-weight:900;font-size:11px;color:#fff}}
  .kbn-breadcrumb{{display:flex;align-items:center;gap:6px;font-size:12px;color:#8b919a;margin-left:8px}}
  .kbn-breadcrumb span{{color:#d4d9e0}}
  .kbn-breadcrumb-sep{{color:#3a3b40}}
  .kbn-badge{{background:#0077CC20;color:#1BA9F5;border:1px solid #0077CC40;border-radius:10px;padding:2px 8px;font-size:11px;font-weight:600;letter-spacing:.03em}}
  .kbn-body{{display:flex;flex:1;overflow:hidden}}
  .kbn-sidebar{{width:220px;background:#111217;border-right:1px solid #1e1f24;padding:20px 0;flex-shrink:0;overflow-y:auto}}
  .kbn-sidebar-section{{padding:0 16px;margin-bottom:8px}}
  .kbn-sidebar-label{{font-size:10px;font-weight:700;color:#5a6270;letter-spacing:.1em;text-transform:uppercase;padding:8px 8px 4px}}
  .kbn-sidebar-item{{display:flex;align-items:center;gap:8px;padding:7px 8px;border-radius:4px;font-size:13px;color:#8b919a;cursor:pointer;transition:background .15s}}
  .kbn-sidebar-item.active{{background:#0077CC18;color:#1BA9F5;font-weight:600}}
  .kbn-sidebar-item:hover:not(.active){{background:#ffffff08}}
  .kbn-sidebar-dot{{width:6px;height:6px;border-radius:50%;background:#3a3b40;flex-shrink:0}}
  .kbn-sidebar-dot.live{{background:#00BFB3}}
  .kbn-main{{flex:1;overflow-y:auto;padding:28px 32px}}
  .kbn-page-header{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:24px}}
  .kbn-page-title{{font-size:22px;font-weight:700;color:#fff;letter-spacing:-.01em}}
  .kbn-page-sub{{font-size:13px;color:#5a6270;margin-top:4px}}
  .kbn-btn{{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer;border:none;transition:background .15s}}
  .kbn-btn-primary{{background:#0077CC;color:#fff}}
  .kbn-btn-primary:hover{{background:#0069b5}}
  .kbn-stats{{display:flex;gap:16px;margin-bottom:24px}}
  .kbn-stat{{background:#111217;border:1px solid #1e1f24;border-radius:8px;padding:14px 18px;flex:1}}
  .kbn-stat-val{{font-size:24px;font-weight:800;color:#fff}}
  .kbn-stat-lbl{{font-size:11px;color:#5a6270;margin-top:2px;text-transform:uppercase;letter-spacing:.06em}}
  .kbn-table{{width:100%;border-collapse:collapse}}
  .kbn-table th{{text-align:left;font-size:11px;font-weight:700;color:#5a6270;text-transform:uppercase;letter-spacing:.07em;padding:10px 14px;border-bottom:1px solid #1e1f24}}
  .kbn-table td{{padding:12px 14px;border-bottom:1px solid #16171c;font-size:13px;vertical-align:middle}}
  .kbn-table tr:last-child td{{border-bottom:none}}
  .kbn-table tr:hover td{{background:#ffffff04}}
  .kbn-agent-name{{font-weight:600;color:#fff}}
  .kbn-agent-id{{font-size:11px;color:#5a6270;font-family:ui-monospace,monospace;margin-top:2px}}
  .kbn-pill{{display:inline-flex;align-items:center;gap:4px;padding:3px 8px;border-radius:10px;font-size:11px;font-weight:600}}
  .kbn-pill-active{{background:#00BFB320;color:#00BFB3;border:1px solid #00BFB340}}
  .kbn-pill-sys{{background:#1BA9F520;color:#1BA9F5;border:1px solid #1BA9F540}}
  .kbn-tools-count{{font-size:12px;color:#8b919a}}
  .kbn-connection{{display:flex;align-items:center;gap:6px;font-size:12px;color:#00BFB3;background:#00BFB310;border:1px solid #00BFB330;border-radius:6px;padding:6px 12px;margin-bottom:20px}}
  .kbn-dot-live{{width:7px;height:7px;border-radius:50%;background:#00BFB3;animation:kbn-pulse 2s infinite}}
  @keyframes kbn-pulse{{0%,100%{{opacity:1}}50%{{opacity:.4}}}}
  .kbn-empty{{text-align:center;padding:48px;color:#5a6270;font-size:14px}}
  .kbn-highlight{{background:#FFD70010;outline:2px solid #FFD700;outline-offset:2px;border-radius:6px}}
</style>
</head>
<body>
<div class="kbn-chrome">
  <header class="kbn-header">
    <div class="kbn-logo">
      <div class="kbn-logo-mark">e</div>
      Elastic
    </div>
    <div class="kbn-breadcrumb">
      <span style="color:#5a6270">Kibana</span>
      <span class="kbn-breadcrumb-sep">/</span>
      <span>Agent Builder</span>
      <span class="kbn-breadcrumb-sep">/</span>
      <span>Agents</span>
    </div>
    <div style="margin-left:auto">
      <span class="kbn-badge">ELASTIC CLOUD</span>
    </div>
  </header>
  <div class="kbn-body">
    <nav class="kbn-sidebar">
      <div class="kbn-sidebar-label">Agent Builder</div>
      <div class="kbn-sidebar-section">
        <div class="kbn-sidebar-item active">
          <span class="kbn-sidebar-dot live"></span>
          Agents
        </div>
        <div class="kbn-sidebar-item">
          <span class="kbn-sidebar-dot"></span>
          Tools
        </div>
        <div class="kbn-sidebar-item">
          <span class="kbn-sidebar-dot"></span>
          Conversations
        </div>
      </div>
      <div class="kbn-sidebar-label" style="margin-top:16px">Deployment</div>
      <div class="kbn-sidebar-section">
        <div class="kbn-sidebar-item">
          <span class="kbn-sidebar-dot live"></span>
          fe-summit-hackathon
        </div>
      </div>
    </nav>
    <main class="kbn-main">
      <div class="kbn-connection">
        <span class="kbn-dot-live"></span>
        Connected · fe-summit-hackathon-ed0e8e · us-west-1
      </div>
      <div class="kbn-page-header">
        <div>
          <div class="kbn-page-title">Agents</div>
          <div class="kbn-page-sub">Specialist agents deployed to this Elastic cluster</div>
        </div>
        <button class="kbn-btn kbn-btn-primary">+ New agent</button>
      </div>
      <div class="kbn-stats">
        <div class="kbn-stat">
          <div class="kbn-stat-val" id="stat-total">-</div>
          <div class="kbn-stat-lbl">Agents deployed</div>
        </div>
        <div class="kbn-stat">
          <div class="kbn-stat-val">14</div>
          <div class="kbn-stat-lbl">MCP tools registered</div>
        </div>
        <div class="kbn-stat">
          <div class="kbn-stat-val" style="color:#00BFB3">Live</div>
          <div class="kbn-stat-lbl">Cluster status</div>
        </div>
      </div>
      <table class="kbn-table">
        <thead>
          <tr>
            <th>Agent</th>
            <th>Type</th>
            <th>Tools</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody id="agents-tbody">
          <tr><td colspan="4" class="kbn-empty">Loading agents…</td></tr>
        </tbody>
      </table>
    </main>
  </div>
</div>
<script>
  const AGENTS_DATA = {agents_json};
  function renderAgents(agents) {{
    const tbody = document.getElementById('agents-tbody');
    document.getElementById('stat-total').textContent = agents.length;
    if (!agents.length) {{
      tbody.innerHTML = '<tr><td colspan="4" class="kbn-empty">No agents found in this cluster.</td></tr>';
      return;
    }}
    tbody.innerHTML = agents.map((a, i) => {{
      const id = a.id || a.agent_id || '';
      const name = a.name || id;
      const isSys = id === 'fec_field_assistant';
      const isNew = (id || '').includes('splunk_displacement') || (name || '').toLowerCase().includes('splunk displacement');
      const tools = a.tools ? (Array.isArray(a.tools) ? a.tools.length : JSON.stringify(a.tools).length) : '-';
      const toolCount = Array.isArray(a.tools) ? a.tools.reduce((acc, t) => acc + (Array.isArray(t.tool_ids) ? t.tool_ids.length : 0), 0) : '-';
      return `<tr class="${{isNew ? 'kbn-highlight' : ''}}">
        <td><div class="kbn-agent-name">${{name}}</div><div class="kbn-agent-id">${{id}}</div></td>
        <td><span class="kbn-pill ${{isSys ? 'kbn-pill-sys' : 'kbn-pill-active'}}">${{isSys ? 'System' : 'User'}}</span></td>
        <td><span class="kbn-tools-count">${{toolCount}} tools</span></td>
        <td><span class="kbn-pill kbn-pill-active">Active</span></td>
      </tr>`;
    }}).join('');
  }}
  if (AGENTS_DATA && AGENTS_DATA.length) {{
    renderAgents(AGENTS_DATA);
  }} else {{
    fetch('/api/v1/agent-builder/agents')
      .then(r => r.json())
      .then(d => renderAgents(d.agents || []))
      .catch(() => renderAgents([]));
  }}
</script>
</body>
</html>"""
    return HTMLResponse(content=html)
