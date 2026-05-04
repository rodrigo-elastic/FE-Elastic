"""
filename: routes_mcp.py
description: MCP Streamable HTTP server exposing the eleven FE Copilot tools (nine specialists, the Sloane competitive comparison tool, and the Auro orchestrator) to Elastic Agent Builder. Speaks JSON-RPC over a single POST endpoint per the MCP 2025-03-26 spec; each tool delegates to the existing FastAPI tool route.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from typing import Any, Dict

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response

from app.api.routes_tools import (
    CapacityRequest,
    CodeSampleRequest,
    CompareRequest,
    ComplianceRequest,
    CostCalcRequest,
    KnowledgeSearchRequest,
    OrchestratorRequest,
    POCPlanRequest,
    SPLToESQLRequest,
    StackExtractRequest,
    TroubleshootRequest,
    run_capacity,
    run_code_sample,
    run_compare,
    run_compliance_mapping,
    run_cost_calc,
    run_knowledge_search,
    run_orchestrator,
    run_poc_plan,
    run_spl_to_esql,
    run_stack_extract,
    run_troubleshoot,
)
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])

PROTOCOL_VERSION = "2025-03-26"
SERVER_INFO = {"name": "fe-copilot-mcp", "version": "0.1.0"}

TOOLS = [
    {
        "name": "fec_poc_plan",
        "description": "Produce a 4-8 week Proof-of-Value plan grounded in the latest post-meeting record for a given meeting. Persona: Marta, Sr Solutions Architect (12y POV experience).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string", "description": "FE Copilot meeting id (e.g., revolut-mtg-prev-001)"},
                "language": {"type": "string", "default": "English"},
            },
            "required": ["meeting_id"],
        },
    },
    {
        "name": "fec_spl_to_esql",
        "description": "Translate a Splunk SPL query into Elastic ES|QL with explanation and migration caveats. Persona: Diego, ex-Splunk consultant (200+ migrations).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spl": {"type": "string", "description": "The Splunk Search Processing Language query to translate."},
                "language": {"type": "string", "default": "English"},
            },
            "required": ["spl"],
        },
    },
    {
        "name": "fec_compliance",
        "description": "Map regulations (DORA, HIPAA, PCI DSS, GDPR, SOX, NIS2, ISO 27001, SOC 2, FCA SYSC, MAS TRM, FedRAMP, EBA, FFIEC) to native Elastic controls with honest gap analysis. Persona: Priya, ex-PwC compliance auditor (CISA + CISSP).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "regulations": {"type": "array", "items": {"type": "string"}, "description": "List of regulation names."},
                "industry": {"type": "string", "description": "Customer industry context (e.g., 'UK retail bank')."},
                "language": {"type": "string", "default": "English"},
            },
            "required": ["regulations"],
        },
    },
    {
        "name": "fec_stack_extract",
        "description": "Extract a customer's technology stack from raw text (transcript or pasted dossier) into canonical buckets: observability, search, cloud, data, languages, frameworks. Persona: Aiko, FE Discovery Analyst.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Raw source text (transcript or paste)."},
                "language": {"type": "string", "default": "English"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "fec_code_sample",
        "description": "Produce a runnable Elastic SDK code sample for a target programming language and use case. Defaults to ES 8.x semantics and ES|QL where relevant. Persona: Kenji, SDK cookbook author.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "language": {"type": "string", "description": "Programming language (Python, TypeScript, Java, Go, Ruby)."},
                "use_case": {"type": "string", "description": "Specific use case (e.g., bulk index 1000 docs)."},
                "response_language": {"type": "string", "default": "English"},
            },
            "required": ["language", "use_case"],
        },
    },
    {
        "name": "fec_cost_calc",
        "description": "Pure-Python 12-month TCO comparison given daily ingest GB and retention months. Returns Elastic / Splunk / Datadog totals plus savings versus current spend.",
        "inputSchema": {
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
    },
    {
        "name": "fec_capacity",
        "description": "Heuristic Elastic Cloud cluster sizing given peak indexing EPS, hot data GB, warm data GB, replicas, peak QPS. Returns a recommended hot/warm/frozen/master/Kibana topology.",
        "inputSchema": {
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
    },
    {
        "name": "fec_knowledge_search",
        "description": "Semantic search over Elastic public docs. Returns a synthesized answer with citation URLs. Persona: Mei, ex-Elastic enablement docs lead.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "fec_troubleshoot",
        "description": "Diagnose an Elastic stack error and propose 3 ES|QL diagnostic queries plus quick remediations. Persona: Ravi, ex-Elastic support engineer 1000+ tickets.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "error_text": {"type": "string"},
                "context": {"type": "string"},
                "language": {"type": "string", "default": "English"},
            },
            "required": ["error_text"],
        },
    },
    {
        "name": "fec_compare",
        "description": "Structured technical and cost comparison between Elastic and a named competitor (Splunk, Datadog, Sumo Logic, AppDynamics, Chronicle, Cribl, Dynatrace, Exabeam, Grafana, Graylog, Honeycomb, Loki, Microsoft Sentinel, New Relic, QRadar). Returns a 6 to 10 axis technical table, an honest gaps list, a cost section grounded in the FE Copilot calculator, and 4 to 6 customer discovery questions. Persona: Sloane, Senior Competitive Architect (15y competitive intelligence at Elastic).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "competitor": {"type": "string", "description": "Competitor name (case-insensitive, matched against the fec-battlecards index)."},
                "dimensions": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["technical", "cost"]},
                    "description": "Subset of ['technical', 'cost']; defaults to both.",
                },
                "customer_context": {"type": "string", "description": "Optional industry, scale, or current spend context."},
                "ingest_gb_day": {"type": "number", "description": "Optional daily ingest in GB; enables real cost calc."},
                "retention_months": {"type": "integer", "default": 12},
                "language": {"type": "string", "default": "English"},
            },
            "required": ["competitor"],
        },
    },
    {
        "name": "fec_orchestrator",
        "description": "Meta-tool. Auro (senior FE conductor, 12y orchestrating multi-tool responses) reads a complex query, picks 2-3 of the other nine FE Copilot tools, runs them in parallel, and synthesizes a single coherent answer with cross-references and follow-up suggestions. Use when a request needs more than one specialist (e.g., cost + capacity, SPL + cost, compliance + code sample).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The full natural-language Field Engineer question, possibly multi-part."},
                "language": {"type": "string", "default": "English"},
            },
            "required": ["query"],
        },
    },
]


async def _invoke_tool(name: str, args: Dict[str, Any]) -> Any:
    """Dispatch an MCP tool call to the matching FastAPI route function."""
    if name == "fec_poc_plan":
        meeting_id = args.get("meeting_id")
        payload = POCPlanRequest(language=args.get("language", "English"))
        return await run_poc_plan(meeting_id, payload)
    if name == "fec_spl_to_esql":
        return await run_spl_to_esql(SPLToESQLRequest(**args))
    if name == "fec_compliance":
        return await run_compliance_mapping(ComplianceRequest(**args))
    if name == "fec_stack_extract":
        return await run_stack_extract(StackExtractRequest(**args))
    if name == "fec_code_sample":
        return await run_code_sample(CodeSampleRequest(**args))
    if name == "fec_cost_calc":
        return await run_cost_calc(CostCalcRequest(**args))
    if name == "fec_capacity":
        return await run_capacity(CapacityRequest(**args))
    if name == "fec_knowledge_search":
        return await run_knowledge_search(KnowledgeSearchRequest(**args))
    if name == "fec_troubleshoot":
        return await run_troubleshoot(TroubleshootRequest(**args))
    if name == "fec_compare":
        return await run_compare(CompareRequest(**args))
    if name == "fec_orchestrator":
        return await run_orchestrator(OrchestratorRequest(**args))
    raise ValueError(f"unknown tool: {name}")


def _ok(rid: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "result": result}


def _err(rid: Any, code: int, msg: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": code, "message": msg}}


@router.post("")
async def mcp_streamable(req: Request) -> Response:
    """Single POST endpoint per MCP Streamable HTTP transport. Routes JSON-RPC methods to handlers."""
    try:
        body = await req.json()
    except Exception as exc:
        return JSONResponse(_err(None, -32700, f"parse error: {exc}"), status_code=400)

    rid = body.get("id")
    method = body.get("method")
    params = body.get("params") or {}
    log.info("mcp.request", method=method, id=rid)

    if method == "initialize":
        return JSONResponse(_ok(rid, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }))
    if method == "notifications/initialized":
        return Response(status_code=202)
    if method == "ping":
        return JSONResponse(_ok(rid, {}))
    if method == "tools/list":
        return JSONResponse(_ok(rid, {"tools": TOOLS}))
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        try:
            result = await _invoke_tool(name, args)
            text = json.dumps(result, default=str, ensure_ascii=False)
            return JSONResponse(_ok(rid, {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            }))
        except Exception as exc:
            log.warning("mcp.tool_error", name=name, error=str(exc))
            return JSONResponse(_ok(rid, {
                "content": [{"type": "text", "text": f"Error: {exc}"}],
                "isError": True,
            }))

    return JSONResponse(_err(rid, -32601, f"method not found: {method}"))
