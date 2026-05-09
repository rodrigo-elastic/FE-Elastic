"""
filename: routes_health.py
description: Health and version endpoints. /health is a tiny liveness probe; /info exposes per-agent model assignment plus the ES and Kibana status. /health/full is the rich, judge-facing system health endpoint that powers the /health.html stats page (build SHA, MCP tool count, FE Brain chunks, registered Kibana workflow rules, demo data scenarios, battlecards, Elastic cluster, Kibana Agent Builder pointers).
date: 04-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter

from app.config import settings
from app.integrations import kibana_client
from app.repositories.elasticsearch_repo import get_repo as get_es_repo

router = APIRouter(tags=["health"])

# Resolve the repo root once. Same trick used by main.py: parents[2] = backend/, parents[3] = repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
_BATTLECARDS_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed" / "battlecards.json"
_KNOWLEDGE_INDEX = "fec-knowledge"
_AGENT_BUILDER_AGENT_ID = "fec_field_assistant"
_MCP_CONNECTOR_NAME = "FE Copilot MCP"


# ============================================================ Helpers ===============


def _git_short_sha() -> str:
    """Best-effort git short SHA. Returns the env override or 'dev' on any failure."""
    override = os.environ.get("FEC_BUILD_SHA")
    if override:
        return override.strip()[:12]
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=str(_REPO_ROOT),
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode("utf-8").strip() or "dev"
    except Exception:
        return "dev"


def _git_commit_iso() -> str:
    """Best-effort git commit ISO timestamp. Returns the env override or app-start time on failure."""
    override = os.environ.get("FEC_BUILD_TIMESTAMP")
    if override:
        return override.strip()
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%cI"],
            cwd=str(_REPO_ROOT),
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode("utf-8").strip()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _mcp_tool_ids() -> List[str]:
    """Pull the registered MCP tool ids straight from routes_mcp.TOOLS so the count is never stale."""
    try:
        from app.api.routes_mcp import TOOLS as MCP_TOOLS

        return [t.get("name", "") for t in MCP_TOOLS if t.get("name")]
    except Exception:
        return []


def _scenario_count() -> int:
    """Pull the number of registered demo-data scenarios from routes_demo_data.SCENARIOS."""
    try:
        from app.api.routes_demo_data import SCENARIOS

        return len(SCENARIOS)
    except Exception:
        return 0


def _scenario_dashboard_count() -> int:
    """Each scenario ships an FE dashboard plus a paired customer dashboard, so default to 2x."""
    try:
        return _scenario_count() * 2
    except Exception:
        return 0


def _battlecards_seed_count() -> int:
    """Authoritative count from the on-disk seed file. Falls back to ES count if disk is missing."""
    if _BATTLECARDS_SEED_PATH.exists():
        try:
            data = json.loads(_BATTLECARDS_SEED_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return len(data)
        except Exception:
            pass
    try:
        es = get_es_repo()
        if es.available:
            res = es._client.count(index="fec-battlecards")  # noqa: SLF001
            if isinstance(res, dict):
                return int(res.get("count", 0))
            return int(getattr(res, "body", {}).get("count", 0))
    except Exception:
        pass
    return 0


def _fe_brain_chunks(es) -> int:
    """Run a `_count` against the fec-knowledge index. Returns 0 on any failure."""
    if not es.available:
        return 0
    try:
        res = es._client.count(index=_KNOWLEDGE_INDEX)  # noqa: SLF001
        if isinstance(res, dict):
            return int(res.get("count", 0))
        return int(getattr(res, "body", {}).get("count", 0))
    except Exception:
        return 0


def _fe_brain_last_seed(es) -> str:
    """Find the most recent @timestamp / indexed_at on a fec-knowledge doc; falls back to runtime/knowledge mtime."""
    if es.available:
        for sort_field in ("indexed_at", "@timestamp", "ingested_at"):
            try:
                res = es._client.search(  # noqa: SLF001
                    index=_KNOWLEDGE_INDEX,
                    size=1,
                    sort=[{sort_field: {"order": "desc"}}],
                    _source=[sort_field],
                )
                hits = (res.get("hits") or {}).get("hits") if isinstance(res, dict) else None
                if hits:
                    val = (hits[0].get("_source") or {}).get(sort_field)
                    if val:
                        return str(val)
            except Exception:
                continue
    knowledge_dir = settings.runtime_dir / "knowledge"
    if knowledge_dir.exists():
        try:
            files = list(knowledge_dir.glob("*.jsonl"))
            if files:
                newest = max(files, key=lambda p: p.stat().st_mtime)
                return datetime.fromtimestamp(newest.stat().st_mtime, tz=timezone.utc).isoformat()
        except Exception:
            pass
    return ""


def _cluster_info(es) -> Dict[str, Any]:
    """Run a single root call against ES to pull cluster name + version. Returns {} on failure."""
    info: Dict[str, Any] = {}
    if not es.available:
        return info
    try:
        res = es._client.info()  # noqa: SLF001
        body = res if isinstance(res, dict) else getattr(res, "body", {})
        info["cluster"] = body.get("cluster_name") or ""
        version_block = body.get("version") or {}
        info["version"] = version_block.get("number") or ""
    except Exception:
        return {}
    return info


def _ping_ms(es) -> int:
    """Round-trip a `ping` to Elasticsearch and return the elapsed milliseconds (or -1 on failure)."""
    if not es.available:
        return -1
    try:
        start = time.perf_counter()
        es._client.ping()  # noqa: SLF001
        return int((time.perf_counter() - start) * 1000)
    except Exception:
        return -1


def _workflow_status() -> Dict[str, str]:
    """Read the workflow registration state file written by routes_workflows. No live Kibana probe."""
    state_path = settings.runtime_dir / "workflow_state.json"
    rule_post = "missing"
    rule_orphan = "missing"
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            if state.get("rule_id"):
                rule_post = "registered"
            if state.get("orphan_rule_id"):
                rule_orphan = "registered"
        except Exception:
            pass
    return {"rule_post_meeting": rule_post, "rule_orphan_actions": rule_orphan}


# ============================================================ Endpoints =============


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "fe-copilot"}


@router.get("/version")
async def version() -> dict:
    return {"version": __version__, "service": "fe-copilot"}


@router.get("/info")
async def info() -> dict:
    """Exposes per-agent model assignment, mock-mode flag, and ES connection status."""
    key = settings.anthropic_api_key.strip()
    mock_mode = key in ("", "sk-ant-replace-me")
    es = get_es_repo()
    prod = settings.app_env == "production"
    es_block: Dict[str, Any] = {"available": es.available}
    kib_block: Dict[str, Any] = {"available": kibana_client.ping()}
    if not prod:
        es_block["url"] = settings.elasticsearch_url
        kib_block["url"] = settings.kibana_url
        kib_block["discover"] = {
            "briefs": kibana_client.discover_url("fec-briefs"),
            "post_meetings": kibana_client.discover_url("fec-post-meetings"),
            "audit": kibana_client.discover_url("fec-audit"),
            "battlecards": kibana_client.discover_url("fec-battlecards"),
        }
    return {
        "service": "fe-copilot",
        "version": __version__,
        "mock_mode": mock_mode,
        "models": {
            "default": settings.model_default,
            "pre_meeting": settings.model_for("pre_meeting"),
            "post_meeting": settings.model_for("post_meeting"),
            "live_meeting": settings.model_for("live_meeting"),
        },
        "elasticsearch": es_block,
        "kibana": kib_block,
    }


@router.get("/status")
async def status() -> Dict[str, Any]:
    """Compact dashboard status pill - lighter than /health/full.

    Returns a summary of service availability, key counts, LLM mode, and
    whether the Kibana Agent Builder integration is live. Each sub-check is
    isolated so individual failures never cause a 500.
    """
    # --- Elasticsearch ---
    try:
        es = get_es_repo()
        es_up = es.available
    except Exception:
        es_up = False

    # --- Kibana ---
    try:
        kib_up = kibana_client.ping()
    except Exception:
        kib_up = False

    # --- LLM mode ---
    try:
        from app.integrations.claude_client import ElasticInferenceService, get_service
        svc = get_service()
        if getattr(svc, "mock_mode", False):
            llm_mode = "mock"
        elif isinstance(svc, ElasticInferenceService):
            llm_mode = "elastic"
        else:
            llm_mode = "direct"
    except Exception:
        llm_mode = "mock"

    # --- Brief count ---
    try:
        briefs_dir = settings.runtime_dir / "briefs"
        briefs_count = len(list(briefs_dir.glob("*.json"))) if briefs_dir.exists() else 0
    except Exception:
        briefs_count = 0

    # --- Workflows fired ---
    try:
        wf_path = settings.runtime_dir / "workflow_fires.jsonl"
        if wf_path.exists():
            workflows_fired = len([ln for ln in wf_path.read_text(encoding="utf-8").splitlines() if ln.strip()])
        else:
            workflows_fired = 0
    except Exception:
        workflows_fired = 0

    # --- SFDC tasks ---
    try:
        from app.integrations.salesforce_mock import list_tasks  # noqa: PLC0415

        sfdc_tasks = len(list_tasks(limit=9999))
    except Exception:
        sfdc_tasks = 0

    # --- Agent Builder live ---
    try:
        from app.integrations.agent_builder import is_live  # noqa: PLC0415

        agent_builder_live = is_live()
    except Exception:
        agent_builder_live = False

    return {
        "ok": es_up and kib_up,
        "services": {
            "elasticsearch": "up" if es_up else "down",
            "kibana": "up" if kib_up else "down",
            "llm": llm_mode,
        },
        "counts": {
            "briefs": briefs_count,
            "workflows_fired": workflows_fired,
            "sfdc_tasks": sfdc_tasks,
        },
        "agent_builder_live": agent_builder_live,
        "as_of": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/full")
async def health_full() -> Dict[str, Any]:
    """One-stop system health endpoint for the /health.html stats page.

    Returns build, MCP tool count, FE Brain chunk count, workflow registration,
    demo data scenario count, battlecard count, Elastic cluster info, and
    Kibana Agent Builder pointers. Degrades to status=yellow with a warnings
    list when Elasticsearch is unreachable; never throws.
    """
    warnings: List[str] = []
    es = get_es_repo()
    es_available = es.available
    if not es_available:
        warnings.append("elasticsearch_unavailable")

    mcp_ids = _mcp_tool_ids()
    if not mcp_ids:
        warnings.append("mcp_tools_unloaded")

    chunks = _fe_brain_chunks(es)
    if es_available and chunks == 0:
        warnings.append("fe_brain_empty")

    cluster = _cluster_info(es)
    ping_ms = _ping_ms(es)

    workflows = _workflow_status()
    if workflows.get("rule_post_meeting") != "registered":
        warnings.append("workflow_post_meeting_missing")
    if workflows.get("rule_orphan_actions") != "registered":
        warnings.append("workflow_orphan_actions_missing")

    scenarios = _scenario_count()
    dashboards = _scenario_dashboard_count()
    battlecards = _battlecards_seed_count()

    status = "green" if not warnings else ("yellow" if es_available else "yellow")
    if not es_available and not mcp_ids:
        status = "red"

    return {
        "status": status,
        "warnings": warnings,
        "build": {
            "sha": _git_short_sha(),
            "timestamp": _git_commit_iso(),
        },
        "mcp_tools": {
            "count": len(mcp_ids),
            "list": mcp_ids,
        },
        "fe_brain": {
            "chunks": chunks,
            "last_seed": _fe_brain_last_seed(es),
            "index": _KNOWLEDGE_INDEX,
        },
        "workflows": workflows,
        "demo_data": {
            "scenarios": scenarios,
            "dashboards": dashboards,
        },
        "battlecards": {
            "count": battlecards,
        },
        "elastic": {
            "cluster": cluster.get("cluster", ""),
            "version": cluster.get("version", ""),
            "ping_ms": ping_ms,
            "available": es_available,
            **({} if settings.app_env == "production" else {"url": settings.elasticsearch_url}),
        },
        "kibana": {
            "agent_builder_agent": _AGENT_BUILDER_AGENT_ID,
            "mcp_connector": _MCP_CONNECTOR_NAME,
            **({} if settings.app_env == "production" else {"url": settings.kibana_url}),
        },
        "service": "fe-copilot",
        "version": __version__,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/elasticsearch/reconnect")
async def elasticsearch_reconnect() -> dict:
    es = get_es_repo()
    es.reconnect()
    if es.available:
        es.ensure_indices()
    return {"available": es.available}


@router.post("/kibana/setup")
async def kibana_setup() -> dict:
    """Idempotently create the four FE Copilot data views in Kibana so Discover is one click away."""
    return kibana_client.setup_data_views()
