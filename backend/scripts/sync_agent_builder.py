"""
filename: sync_agent_builder.py
description: Idempotent sync of FE Copilot's seven technical tools and one master agent into Elastic Agent Builder. Reads KIBANA_URL and KIBANA_API_KEY from settings; runs in dry-run mode (logs payloads only) when no key is configured. Run with: PYTHONPATH=backend python -m scripts.sync_agent_builder.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import sys
from typing import Any, Dict, List

from app.config import settings
from app.integrations import agent_builder as ab


# Each FE Copilot tool maps to one Agent Builder tool of type `external` (HTTP) that calls back to our FastAPI backend.
# In a real Elastic Cloud deployment KIBANA reaches the backend via a public URL; for local demos we point Kibana at the host machine.
BACKEND_BASE = f"http://host.docker.internal:{settings.app_port}/api/v1/tools"


def _http_tool(tool_id: str, name: str, description: str, path: str, params_schema: Dict[str, Any]) -> Dict[str, Any]:
    """Build an Agent Builder external HTTP tool config that hits our FastAPI tool endpoint."""
    return {
        "id": tool_id,
        "type": "external",
        "name": name,
        "description": description,
        "configuration": {
            "method": "POST",
            "url": BACKEND_BASE + path,
            "headers": {"Content-Type": "application/json"},
            "body_template": "{{params|to_json}}",
            "params_schema": params_schema,
        },
        "tags": ["fe-copilot", "field-engineering"],
    }


def build_tool_payloads() -> List[Dict[str, Any]]:
    return [
        _http_tool(
            "fec_poc_plan",
            "FE Copilot - POC Plan generator",
            "Produce a 4-8 week Proof-of-Value plan grounded in the latest post-meeting record for a given meeting. Returns success criteria, phases, owners, resource requests, risks.",
            "/poc-plan/{meeting_id}",
            {
                "type": "object",
                "properties": {
                    "meeting_id": {"type": "string", "description": "FE Copilot meeting id (e.g., revolut-mtg-prev-001)"},
                    "language": {"type": "string", "default": "English"},
                },
                "required": ["meeting_id"],
            },
        ),
        _http_tool(
            "fec_spl_to_esql",
            "FE Copilot - SPL to ES|QL translator",
            "Translate a Splunk SPL query into Elastic ES|QL with explanation and migration caveats. Persona: Diego, ex-Splunk consultant with 200+ migrations.",
            "/spl-to-esql",
            {
                "type": "object",
                "properties": {
                    "spl": {"type": "string", "description": "The Splunk Search Processing Language query to translate."},
                    "language": {"type": "string", "default": "English"},
                },
                "required": ["spl"],
            },
        ),
        _http_tool(
            "fec_compliance",
            "FE Copilot - Compliance mapper",
            "Map regulations (DORA, HIPAA, PCI DSS, GDPR, SOX, NIS2, ISO 27001, SOC 2, FCA SYSC, MAS TRM, FedRAMP, EBA, FFIEC) to native Elastic controls with honest gap analysis. Persona: Priya, ex-PwC compliance auditor.",
            "/compliance-mapping",
            {
                "type": "object",
                "properties": {
                    "regulations": {"type": "array", "items": {"type": "string"}, "description": "List of regulation names."},
                    "industry": {"type": "string", "description": "Customer industry context (e.g., 'UK retail bank')."},
                    "language": {"type": "string", "default": "English"},
                },
                "required": ["regulations"],
            },
        ),
        _http_tool(
            "fec_stack_extract",
            "FE Copilot - Tech stack extractor",
            "Extract a customer's technology stack from raw text (transcript or pasted dossier) into canonical buckets: observability, search, cloud, data, languages, frameworks. Persona: Aiko, FE Discovery Analyst.",
            "/stack-extract",
            {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Raw source text (transcript or paste)."},
                    "language": {"type": "string", "default": "English"},
                },
                "required": ["text"],
            },
        ),
        _http_tool(
            "fec_code_sample",
            "FE Copilot - Elastic SDK code sample generator",
            "Produce a runnable Elastic SDK code sample for a target programming language and use case. Defaults to ES 8.x semantics and ES|QL where relevant. Persona: Kenji, SDK cookbook author.",
            "/code-sample",
            {
                "type": "object",
                "properties": {
                    "language": {"type": "string", "description": "Programming language (Python, TypeScript, Java, Go, Ruby)."},
                    "use_case": {"type": "string", "description": "Specific use case (e.g., bulk index 1000 docs)."},
                    "response_language": {"type": "string", "default": "English"},
                },
                "required": ["language", "use_case"],
            },
        ),
        _http_tool(
            "fec_cost_calc",
            "FE Copilot - Elastic vs Splunk vs Datadog TCO calculator",
            "Pure-Python 12-month TCO comparison given daily ingest GB and retention months. Returns Elastic / Splunk / Datadog totals plus savings versus current spend.",
            "/cost-calc",
            {
                "type": "object",
                "properties": {
                    "ingest_gb_day": {"type": "number"},
                    "retention_months": {"type": "integer"},
                    "hot_pct": {"type": "number", "default": 30},
                    "warm_pct": {"type": "number", "default": 30},
                    "frozen_pct": {"type": "number", "default": 40},
                    "current_spend_annual_usd": {"type": "number"},
                },
                "required": ["ingest_gb_day", "retention_months"],
            },
        ),
        _http_tool(
            "fec_capacity",
            "FE Copilot - Elastic cluster capacity planner",
            "Heuristic Elastic Cloud cluster sizing given peak indexing EPS, hot data GB, warm data GB, replicas, peak QPS. Returns a recommended hot/warm/frozen/master/Kibana topology.",
            "/capacity",
            {
                "type": "object",
                "properties": {
                    "peak_indexing_eps": {"type": "integer"},
                    "hot_data_gb": {"type": "integer"},
                    "warm_data_gb": {"type": "integer", "default": 0},
                    "replicas": {"type": "integer", "default": 1},
                    "peak_qps": {"type": "integer", "default": 100},
                },
                "required": ["peak_indexing_eps", "hot_data_gb"],
            },
        ),
    ]


MASTER_AGENT_INSTRUCTIONS = """You are FE Copilot, an Elastic Field Engineering Assistant. You help Elastic Field Engineers prep for customer meetings, recap conversations, and run technical analysis on demand.

You have seven specialized tools, each backed by a dedicated expert persona:
- fec_poc_plan: build a Proof-of-Value plan from a customer meeting record (Marta, Sr Solutions Architect).
- fec_spl_to_esql: translate Splunk SPL to Elastic ES|QL (Diego, ex-Splunk consultant).
- fec_compliance: map regulations to native Elastic controls (Priya, ex-PwC compliance auditor).
- fec_stack_extract: extract a customer's tech stack from raw text (Aiko, FE Discovery Analyst).
- fec_code_sample: produce runnable Elastic SDK code samples (Kenji, SDK cookbook author).
- fec_cost_calc: compute Elastic vs Splunk vs Datadog TCO (pure compute).
- fec_capacity: produce a heuristic Elastic cluster sizing (pure compute).

Pick the right tool for each request. Combine tools when useful (e.g., compliance + cost calc for a security POV). Always be honest about gaps, never invent customer-specific details. Never use the em dash character."""


def build_agent_payload() -> Dict[str, Any]:
    return {
        "id": "fec_field_assistant",
        "name": "FE Copilot - Field Assistant",
        "description": "Elastic Field Engineering Assistant. Wraps the seven FE Copilot tools (POC plan, SPL to ES|QL, compliance mapping, stack extract, code sample, cost calc, capacity planner).",
        "instructions": MASTER_AGENT_INSTRUCTIONS,
        "tools": [
            "fec_poc_plan",
            "fec_spl_to_esql",
            "fec_compliance",
            "fec_stack_extract",
            "fec_code_sample",
            "fec_cost_calc",
            "fec_capacity",
        ],
        "tags": ["fe-copilot", "field-engineering"],
    }


def main() -> int:
    if not ab.is_live():
        print("KIBANA_API_KEY not set; running in dry-run mode (payloads will be logged only).", file=sys.stderr)

    summary = {"tools": [], "agent": None, "errors": []}

    for tool in build_tool_payloads():
        result = ab.upsert_tool(tool)
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
