"""
filename: sync_agent_builder.py
description: Idempotent sync of FE Copilot's MCP server, ten tools, and master agent into Elastic Agent Builder. Creates a .mcp connector pointing at the FE Copilot MCP endpoint, registers ten Agent Builder tools (nine specialist tools plus the Auro orchestrator) referencing that connector, then creates the master agent that orchestrates them. Reads KIBANA_URL and KIBANA_API_KEY from settings; runs in dry-run mode (logs payloads only) when no key is configured. Override the public backend URL with BACKEND_BASE_URL (e.g., an ngrok forwarding URL) when Kibana is remote. Run with: PYTHONPATH=backend python -m scripts.sync_agent_builder.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.2.0"
__status__ = "Development"

import json
import os
import sys
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.integrations import agent_builder as ab


# Public URL where Kibana can reach the FE Copilot MCP server. Override with BACKEND_BASE_URL
# (e.g., an ngrok forwarding URL) when Kibana lives in Elastic Cloud and the backend runs locally.
BACKEND_BASE = os.environ.get(
    "BACKEND_BASE_URL",
    f"http://host.docker.internal:{settings.app_port}",
).rstrip("/")
MCP_ENDPOINT = BACKEND_BASE + "/api/v1/mcp"

CONNECTOR_NAME = "FE Copilot MCP"


def _kbn_url(path: str) -> str:
    return settings.kibana_url.rstrip("/") + path


def _kbn_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {settings.kibana_api_key}",
        "Content-Type": "application/json",
        "kbn-xsrf": "fe-copilot",
    }


# ============================================================ MCP tool catalogue =====


# id -> (display name, description). Mirrors backend/app/api/routes_mcp.py TOOLS.
MCP_TOOLS: List[Dict[str, str]] = [
    {
        "id": "fec_poc_plan",
        "name": "FE Copilot - POC Plan generator",
        "description": "Produce a 4-8 week Proof-of-Value plan grounded in the latest post-meeting record for a given meeting. Persona: Marta, Sr Solutions Architect (12y POV experience).",
    },
    {
        "id": "fec_spl_to_esql",
        "name": "FE Copilot - SPL to ES|QL translator",
        "description": "Translate a Splunk SPL query into Elastic ES|QL with explanation and migration caveats. Persona: Diego, ex-Splunk consultant (200+ migrations).",
    },
    {
        "id": "fec_compliance",
        "name": "FE Copilot - Compliance mapper",
        "description": "Map regulations (DORA, HIPAA, PCI DSS, GDPR, SOX, NIS2, ISO 27001, SOC 2, FCA SYSC, MAS TRM, FedRAMP, EBA, FFIEC) to native Elastic controls with honest gap analysis. Persona: Priya, ex-PwC compliance auditor.",
    },
    {
        "id": "fec_stack_extract",
        "name": "FE Copilot - Tech stack extractor",
        "description": "Extract a customer's technology stack from raw text (transcript or pasted dossier) into canonical buckets: observability, search, cloud, data, languages, frameworks. Persona: Aiko, FE Discovery Analyst.",
    },
    {
        "id": "fec_code_sample",
        "name": "FE Copilot - Elastic SDK code sample generator",
        "description": "Produce a runnable Elastic SDK code sample for a target programming language and use case. Persona: Kenji, SDK cookbook author.",
    },
    {
        "id": "fec_cost_calc",
        "name": "FE Copilot - Elastic vs Splunk vs Datadog TCO calculator",
        "description": "Pure-Python 12-month TCO comparison given daily ingest GB and retention months. Returns Elastic / Splunk / Datadog totals plus savings versus current spend.",
    },
    {
        "id": "fec_capacity",
        "name": "FE Copilot - Elastic cluster capacity planner",
        "description": "Heuristic Elastic Cloud cluster sizing given peak indexing EPS, hot data GB, warm data GB, replicas, peak QPS. Returns a recommended hot/warm/frozen/master/Kibana topology.",
    },
    {
        "id": "fec_knowledge_search",
        "name": "FE Copilot - Elastic docs knowledge search",
        "description": "Semantic search over the Elastic public documentation corpus. Returns a synthesized answer with [n] inline citations and a citation list (URL, title, section, snippet). Persona: Mei, ex-Elastic enablement docs lead (8 years writing official Elastic doc and field-enablement).",
    },
    {
        "id": "fec_troubleshoot",
        "name": "FE Copilot - Troubleshooting Assistant",
        "description": "Diagnose Elastic stack errors and emit ES|QL diagnostic queries. Persona: Ravi, ex-Elastic support engineer.",
    },
    {
        "id": "fec_orchestrator",
        "name": "FE Copilot - Auro orchestrator (multi-tool conductor)",
        "description": "Meta-tool. Auro (senior FE conductor, 12y orchestrating multi-tool responses) reads a complex query, picks 2-3 of the other nine tools, runs them in parallel, and synthesizes a unified answer with follow-up suggestions. Use when a request needs more than one specialist.",
    },
]
# Master agent instructions below now reference the Auro orchestrator and the ten-tool catalogue.


# ============================================================ Connectors =============


def find_mcp_connector(client: httpx.Client) -> Optional[Dict[str, Any]]:
    """Find the existing FE Copilot MCP connector by name (Kibana assigns UUID ids automatically)."""
    resp = client.get(_kbn_url("/api/actions/connectors"), headers=_kbn_headers())
    resp.raise_for_status()
    for c in resp.json():
        if c.get("connector_type_id") == ".mcp" and c.get("name") == CONNECTOR_NAME:
            return c
    return None


def upsert_mcp_connector(client: httpx.Client) -> Dict[str, Any]:
    """Create the FE Copilot MCP connector if missing, otherwise update its serverUrl."""
    existing = find_mcp_connector(client)
    body = {"name": CONNECTOR_NAME, "config": {"serverUrl": MCP_ENDPOINT}, "secrets": {}}
    if existing:
        # PUT update keeps the same UUID
        body_update = {"name": CONNECTOR_NAME, "config": {"serverUrl": MCP_ENDPOINT}, "secrets": {}}
        resp = client.put(
            _kbn_url(f"/api/actions/connector/{existing['id']}"),
            headers=_kbn_headers(),
            json=body_update,
        )
        resp.raise_for_status()
        return resp.json()
    body_create = {**body, "connector_type_id": ".mcp"}
    resp = client.post(_kbn_url("/api/actions/connector"), headers=_kbn_headers(), json=body_create)
    resp.raise_for_status()
    return resp.json()


# ============================================================ Tools =================


def upsert_mcp_tool(connector_id: str, tool: Dict[str, str]) -> Dict[str, Any]:
    """Register one Agent Builder tool of type=mcp pointing at our connector + MCP tool name."""
    payload = {
        "id": tool["id"],
        "type": "mcp",
        "description": tool["description"],
        "tags": ["fe-copilot", "field-engineering"],
        "configuration": {
            "connector_id": connector_id,
            "tool_name": tool["id"],  # MCP server-side tool name matches our id
        },
    }
    return ab.upsert_tool(payload)


# ============================================================ Master agent ==========


MASTER_AGENT_INSTRUCTIONS = """You are FE Copilot, an Elastic Field Engineering Assistant. You help Elastic Field Engineers prep for customer meetings, recap conversations, and run technical analysis on demand.

You have ten specialized tools, each backed by a dedicated expert persona or pure-compute helper:
- fec_poc_plan: build a Proof-of-Value plan from a customer meeting record (Marta, Sr Solutions Architect).
- fec_spl_to_esql: translate Splunk SPL to Elastic ES|QL (Diego, ex-Splunk consultant).
- fec_compliance: map regulations to native Elastic controls (Priya, ex-PwC compliance auditor).
- fec_stack_extract: extract a customer's tech stack from raw text (Aiko, FE Discovery Analyst).
- fec_code_sample: produce runnable Elastic SDK code samples (Kenji, SDK cookbook author).
- fec_cost_calc: compute Elastic vs Splunk vs Datadog TCO (pure compute).
- fec_capacity: produce a heuristic Elastic cluster sizing (pure compute).
- fec_knowledge_search: semantic search over the Elastic public docs corpus, with synthesized answer and [n] citations (Mei, ex-Elastic enablement docs lead).
- fec_troubleshoot: diagnose an Elastic stack error or log snippet, propose 3 ES|QL diagnostic queries plus quick remediations (Ravi, ex-Elastic support engineer with 1000+ resolved tickets).
- fec_orchestrator: Auro (senior FE conductor, 12y orchestrating multi-tool responses) plans, picks 2-3 of the other nine tools, runs them in parallel, and synthesizes a unified answer with follow-up suggestions.

Pick the right tool for each request. Use fec_orchestrator when the user asks something that requires 2-3 tools chained, OR when you would otherwise call more than 2 tools yourself; let Auro plan it. Combine tools yourself only for simple two-tool combinations (e.g., compliance + cost calc for a security POV; knowledge search to ground a POC plan in current docs; troubleshoot then knowledge search to confirm a remediation). Use fec_knowledge_search whenever the user asks a product-specific question that the public Elastic docs would answer (sizing, ILM, ES|QL syntax, semantic_text setup, detection rules). Use fec_troubleshoot when the user pastes an error message, log snippet, or describes a stack issue that needs diagnosis. Always be honest about gaps, never invent customer-specific details. Never use the em dash character."""


def build_agent_payload() -> Dict[str, Any]:
    return {
        "id": "fec_field_assistant",
        "name": "FE Copilot - Field Assistant",
        "description": "Elastic Field Engineering Assistant. Wraps the ten FE Copilot tools (POC plan, SPL to ES|QL, compliance mapping, stack extract, code sample, cost calc, capacity planner, docs knowledge search, troubleshooter, Auro orchestrator).",
        "configuration": {
            "instructions": MASTER_AGENT_INSTRUCTIONS,
            "tools": [{"tool_ids": [t["id"] for t in MCP_TOOLS]}],
        },
    }


# ============================================================ Entry point ===========


def main() -> int:
    summary: Dict[str, Any] = {"connector": None, "tools": [], "agent": None, "errors": []}

    if not ab.is_live():
        # Dry-run: log payloads without touching Kibana.
        print("KIBANA_API_KEY not set; running in dry-run mode (payloads will be logged only).", file=sys.stderr)
        summary["connector"] = {
            "dry_run": True,
            "name": CONNECTOR_NAME,
            "config": {"serverUrl": MCP_ENDPOINT},
            "connector_type_id": ".mcp",
        }
        for tool in MCP_TOOLS:
            payload = {
                "id": tool["id"],
                "type": "mcp",
                "description": tool["description"],
                "configuration": {"connector_id": "<dry-run>", "tool_name": tool["id"]},
            }
            summary["tools"].append({"id": tool["id"], "ok": True, "result": {"dry_run": True, "body": payload}})
        summary["agent"] = {"id": "fec_field_assistant", "result": {"dry_run": True, "body": build_agent_payload()}}
        print(json.dumps(summary, indent=2, default=str))
        return 0

    # Live mode.
    with httpx.Client(timeout=30.0) as client:
        connector = upsert_mcp_connector(client)
    summary["connector"] = {"id": connector["id"], "name": connector["name"], "serverUrl": connector["config"]["serverUrl"]}

    for tool in MCP_TOOLS:
        result = upsert_mcp_tool(connector["id"], tool)
        ok = not (isinstance(result, dict) and result.get("error"))
        if not ok:
            summary["errors"].append({"tool_id": tool["id"], "result": result})
        summary["tools"].append({"id": tool["id"], "ok": ok, "result": result})

    agent_payload = build_agent_payload()
    agent_result = ab.upsert_agent(agent_payload)
    summary["agent"] = {"id": agent_payload["id"], "result": agent_result}
    if isinstance(agent_result, dict) and agent_result.get("error"):
        summary["errors"].append({"agent_id": agent_payload["id"], "result": agent_result})

    print(json.dumps(summary, indent=2, default=str))
    return 0 if not summary["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
