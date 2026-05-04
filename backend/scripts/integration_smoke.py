"""
filename: integration_smoke.py
description: Master pre-demo smoke test. Exercises every user-facing FE Copilot surface (backend health + pytest, Elasticsearch indices, Kibana saved objects + Agent Builder + alerting rule, MCP server, Tools REST endpoints, workflow status + webhook, frontend pages, em/en dash audit, git status) and emits a single GO / CAUTION / NO-GO verdict to stdout plus a markdown report. Idempotent and safe to run repeatedly. Reads keys from .env via the same pydantic settings the rest of the app uses.
date: 03-05-2026
"""
from __future__ import annotations

__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

# --------------------------------------------------------------------------- Paths

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
DOCS_DIR = REPO_ROOT / "docs"
FRONTEND_DIR = REPO_ROOT / "frontend"
DATA_DIR = REPO_ROOT / "data"
RUNTIME_DIR = REPO_ROOT / "runtime"
REPORT_PATH = DOCS_DIR / "integration-smoke-report.md"

# Ensure backend/ is importable so we can read settings from .env via pydantic.
sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.config import settings  # type: ignore
except Exception:
    settings = None  # type: ignore[assignment]


# --------------------------------------------------------------------------- Config

DEFAULT_BACKEND_PORT = int(os.environ.get("APP_PORT", "8123"))
BACKEND_BASE = os.environ.get(
    "SMOKE_BACKEND_BASE", f"http://localhost:{DEFAULT_BACKEND_PORT}"
).rstrip("/")
API_BASE = BACKEND_BASE + "/api/v1"

ES_URL = (getattr(settings, "elasticsearch_url", "") if settings else "") or os.environ.get(
    "ELASTICSEARCH_URL", ""
)
ES_API_KEY = (
    getattr(settings, "elasticsearch_api_key", "") if settings else ""
) or os.environ.get("ELASTICSEARCH_API_KEY", "")
KIBANA_URL = (getattr(settings, "kibana_url", "") if settings else "") or os.environ.get(
    "KIBANA_URL", ""
)
KIBANA_API_KEY = (
    getattr(settings, "kibana_api_key", "") if settings else ""
) or os.environ.get("KIBANA_API_KEY", "")

# Step classification (matches user spec).
CRITICAL_STEPS: set = {1, 2, 3, 4, 7}
NON_CRITICAL_STEPS: set = {5, 6, 8, 9}

# Frontend pages to probe.
FRONTEND_PAGES: List[Tuple[str, bool]] = [
    ("/", True),
    ("/index.html", True),
    ("/tools.html", True),
    ("/meeting.html?id=northwind-mtg-prev-001", True),
    ("/agent-builder.html", True),
    ("/demo-data.html", True),
    ("/workflow-demo.html", True),
    ("/fe-brain.html", True),
    ("/battlecards.html", False),
    ("/health.html", False),
    ("/industries.html", False),
    ("/quick-research.html", False),
]

# Demo indices and dashboards (sourced from backend/app/services/scenarios/*.py).
EXPECTED_DEMO_INDICES: List[str] = [
    "demo-blackfriday-checkout",
    "demo-blackfriday-apm",
    "demo-blackfriday-metrics",
    "demo-credstuff-auth",
    "demo-credstuff-sessions",
    "demo-credstuff-iplookup",
    "demo-noisy-traces",
    "demo-noisy-logs",
    "demo-noisy-deployments",
    "demo-gdpr-access-logs",
    "demo-gdpr-retention-violations",
    "demo-gdpr-rtbf-requests",
    "demo-supplychain-build-events",
    "demo-supplychain-runtime-events",
    "demo-supplychain-mitre-alerts",
    # FSI Banking - card-not-present fraud rings (Northwind Pay).
    "demo-fsi-card-transactions",
    "demo-fsi-fraud-alerts",
    "demo-fsi-customer-journey",
    # Healthcare - HIPAA audit readiness (Atlas Health).
    "demo-hc-phi-access-logs",
    "demo-hc-audit-events",
    "demo-hc-rtbf-requests",
    # Government Federal - CDM compliance (Federal Demonstration Agency).
    "demo-gov-asset-inventory",
    "demo-gov-cve-findings",
    "demo-gov-config-drift",
]
EXPECTED_FEC_INDICES: List[str] = [
    "fec-briefs",
    "fec-post-meetings",
    "fec-audit",
    "fec-battlecards",
    "fec-knowledge",
]
EXPECTED_DEMO_DASHBOARDS: List[str] = [
    "demo-black-friday-outage-dashboard",
    "demo-black-friday-outage-customer-dashboard",
    "demo-credential-stuffing-dashboard",
    "demo-credential-stuffing-customer-dashboard",
    "demo-noisy-microservice-dashboard",
    "demo-noisy-microservice-customer-dashboard",
    "demo-gdpr-audit-dashboard",
    "demo-gdpr-audit-customer-dashboard",
    "demo-supply-chain-attack-dashboard",
    "demo-supply-chain-attack-customer-dashboard",
    # FSI Banking fraud (Northwind Pay).
    "demo-fsi-banking-fraud-dashboard",
    "demo-fsi-banking-fraud-customer-dashboard",
    # Healthcare HIPAA audit (Atlas Health).
    "demo-hc-hipaa-audit-dashboard",
    "demo-hc-hipaa-audit-customer-dashboard",
    # Government CDM compliance (Federal Demonstration Agency).
    "demo-gov-cdm-dashboard",
    "demo-gov-cdm-customer-dashboard",
]

EXPECTED_FEC_TOOLS: List[str] = [
    "fec_poc_plan",
    "fec_spl_to_esql",
    "fec_compliance",
    "fec_stack_extract",
    "fec_code_sample",
    "fec_cost_calc",
    "fec_capacity",
    "fec_knowledge_search",
    "fec_troubleshoot",
    "fec_compare",
    "fec_orchestrator",
    "fec_proposal",
]

EXPECTED_MASTER_AGENT_ID = "fec_field_assistant"
EXPECTED_MCP_CONNECTOR_NAME = "FE Copilot MCP"
EXPECTED_RULE_NAME = "FE Copilot - Post-Meeting Workflow"


# --------------------------------------------------------------------------- Result data

@dataclass
class StepResult:
    step_id: int
    name: str
    status: str  # PASS | FAIL | SKIP
    duration_ms: int
    notes: str = ""
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRunner:
    step_id: int
    name: str
    critical: bool

    def __enter__(self) -> "StepRunner":
        self._t0 = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Swallowed by run() wrapper; we only use this for timing.
        return None

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._t0) * 1000)


# --------------------------------------------------------------------------- HTTP helpers

def _kbn_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {KIBANA_API_KEY}",
        "Content-Type": "application/json",
        "kbn-xsrf": "fe-copilot",
    }


def _es_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {ES_API_KEY}",
        "Content-Type": "application/json",
    }


def _kbn(path: str) -> str:
    return KIBANA_URL.rstrip("/") + path


def _es(path: str) -> str:
    return ES_URL.rstrip("/") + path


# --------------------------------------------------------------------------- Steps

def step_1_backend(client: httpx.Client) -> StepResult:
    name = "Backend health + pytest 30/30"
    t0 = time.monotonic()
    notes_parts: List[str] = []
    detail: Dict[str, Any] = {}

    # 1a: health endpoint
    try:
        resp = client.get(f"{API_BASE}/health", timeout=10.0)
        ok = resp.status_code == 200 and (resp.json() or {}).get("status") == "ok"
        if not ok:
            return StepResult(
                1, name, "FAIL",
                int((time.monotonic() - t0) * 1000),
                f"health endpoint not ok (status={resp.status_code}, body={resp.text[:120]})",
                {"health_status": resp.status_code},
            )
        notes_parts.append("health=ok")
        detail["health_status"] = 200
    except Exception as exc:
        return StepResult(
            1, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"could not reach {API_BASE}/health: {exc}",
            {},
        )

    # 1b: pytest run
    venv_py = REPO_ROOT / ".venv" / "bin" / "python"
    py_exec = str(venv_py) if venv_py.exists() else sys.executable
    env = os.environ.copy()
    env["PYTHONPATH"] = str(BACKEND_DIR)
    try:
        proc = subprocess.run(
            [py_exec, "-m", "pytest", "backend/tests", "-q", "--no-header"],
            cwd=str(REPO_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        return StepResult(
            1, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            "pytest timed out after 180s",
            detail,
        )

    out = (proc.stdout or "") + (proc.stderr or "")
    detail["pytest_returncode"] = proc.returncode
    # parse summary line "30 passed in 1.23s"
    m = re.search(r"(\d+)\s+passed", out)
    failed = re.search(r"(\d+)\s+failed", out)
    errors = re.search(r"(\d+)\s+error", out)
    passed_n = int(m.group(1)) if m else 0
    failed_n = int(failed.group(1)) if failed else 0
    errors_n = int(errors.group(1)) if errors else 0
    detail["pytest_passed"] = passed_n
    detail["pytest_failed"] = failed_n
    detail["pytest_errors"] = errors_n

    if proc.returncode != 0 or failed_n or errors_n or passed_n < 30:
        return StepResult(
            1, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"pytest reported {passed_n} passed, {failed_n} failed, {errors_n} errors, rc={proc.returncode}",
            detail,
        )

    notes_parts.append(f"pytest={passed_n} passed")
    return StepResult(
        1, name, "PASS",
        int((time.monotonic() - t0) * 1000),
        ", ".join(notes_parts),
        detail,
    )


def step_2_elasticsearch(client: httpx.Client) -> StepResult:
    name = "Elasticsearch indices (fec-* + demo-*) green"
    t0 = time.monotonic()
    if not (ES_URL and ES_API_KEY):
        return StepResult(
            2, name, "SKIP",
            int((time.monotonic() - t0) * 1000),
            "ELASTICSEARCH_URL or ELASTICSEARCH_API_KEY missing",
        )
    detail: Dict[str, Any] = {}
    try:
        r = client.get(
            _es("/_cat/indices/fec-*,demo-*"),
            params={"h": "index,health,docs.count", "format": "json"},
            headers=_es_headers(),
            timeout=20.0,
        )
        r.raise_for_status()
        rows = r.json()
    except Exception as exc:
        return StepResult(
            2, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"ES cat indices failed: {exc}",
        )

    by_index: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        by_index[row["index"]] = {
            "health": row.get("health"),
            "docs": int(row.get("docs.count") or 0),
        }
    detail["index_count"] = len(by_index)

    missing: List[str] = []
    not_green: List[str] = []
    empty_demo: List[str] = []
    knowledge_count = 0

    for idx in EXPECTED_DEMO_INDICES:
        if idx not in by_index:
            missing.append(idx)
            continue
        if by_index[idx]["health"] != "green":
            not_green.append(idx)
        if by_index[idx]["docs"] <= 0:
            empty_demo.append(idx)

    for idx in EXPECTED_FEC_INDICES:
        if idx not in by_index:
            missing.append(idx)
            continue
        if by_index[idx]["health"] != "green":
            not_green.append(idx)

    if "fec-knowledge" in by_index:
        knowledge_count = by_index["fec-knowledge"]["docs"]
    detail["fec_knowledge_docs"] = knowledge_count

    problems: List[str] = []
    if missing:
        problems.append(f"missing={','.join(missing)}")
    if not_green:
        problems.append(f"not-green={','.join(not_green)}")
    if empty_demo:
        problems.append(f"empty-demo={','.join(empty_demo)}")
    if knowledge_count <= 100:
        problems.append(f"fec-knowledge docs={knowledge_count} (<=100)")

    total_expected = len(EXPECTED_DEMO_INDICES) + len(EXPECTED_FEC_INDICES)
    notes = f"{len(by_index)} found / {total_expected} expected, fec-knowledge={knowledge_count} docs"

    if problems:
        return StepResult(
            2, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            notes + " | " + "; ".join(problems),
            detail,
        )
    return StepResult(
        2, name, "PASS",
        int((time.monotonic() - t0) * 1000),
        notes,
        detail,
    )


def step_3_kibana_saved_objects(client: httpx.Client) -> StepResult:
    name = "Kibana saved objects (dashboards + tools + agent + .mcp + rule)"
    t0 = time.monotonic()
    if not (KIBANA_URL and KIBANA_API_KEY):
        return StepResult(
            3, name, "SKIP",
            int((time.monotonic() - t0) * 1000),
            "KIBANA_URL or KIBANA_API_KEY missing",
        )
    problems: List[str] = []
    detail: Dict[str, Any] = {}

    # 3a: demo dashboards (10) + at least one customer-fit dashboard (fec-*).
    try:
        r = client.get(
            _kbn("/api/saved_objects/_find"),
            params={"type": "dashboard", "fields": "title", "per_page": 100},
            headers=_kbn_headers(),
            timeout=20.0,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        return StepResult(
            3, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"dashboards _find failed: {exc}",
            detail,
        )
    dash_ids = {s.get("id") for s in data.get("saved_objects", [])}
    detail["dashboard_total"] = data.get("total", 0)
    missing_dash = [d for d in EXPECTED_DEMO_DASHBOARDS if d not in dash_ids]
    if missing_dash:
        problems.append(f"missing dashboards: {','.join(missing_dash)}")
    customer_fit = [d for d in dash_ids if isinstance(d, str) and d.startswith("fec-")]
    detail["customer_fit_dashboards"] = len(customer_fit)
    if not customer_fit:
        problems.append("no fec-* customer-fit dashboard found")

    # 3b: 9 Agent Builder tools registered.
    try:
        r = client.get(
            _kbn("/api/agent_builder/tools"), headers=_kbn_headers(), timeout=20.0
        )
        r.raise_for_status()
        ab_payload = r.json()
        tools_list = ab_payload.get("results", ab_payload) if isinstance(ab_payload, dict) else ab_payload
        tool_ids = [t.get("id") for t in tools_list] if isinstance(tools_list, list) else []
    except Exception as exc:
        return StepResult(
            3, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"agent_builder/tools failed: {exc}",
            detail,
        )
    missing_tools = [t for t in EXPECTED_FEC_TOOLS if t not in tool_ids]
    detail["agent_builder_tools_total"] = len(tool_ids)
    detail["fec_tools_present"] = len(EXPECTED_FEC_TOOLS) - len(missing_tools)
    if missing_tools:
        problems.append(f"missing tools: {','.join(missing_tools)}")

    # 3c: master agent fec_field_assistant exists.
    try:
        r = client.get(
            _kbn("/api/agent_builder/agents"), headers=_kbn_headers(), timeout=20.0
        )
        r.raise_for_status()
        ag_payload = r.json()
        agents = ag_payload.get("results", ag_payload) if isinstance(ag_payload, dict) else ag_payload
        agent_ids = [a.get("id") for a in agents] if isinstance(agents, list) else []
    except Exception as exc:
        return StepResult(
            3, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"agent_builder/agents failed: {exc}",
            detail,
        )
    detail["agents"] = agent_ids
    if EXPECTED_MASTER_AGENT_ID not in agent_ids:
        problems.append(f"master agent {EXPECTED_MASTER_AGENT_ID} missing")

    # 3d: .mcp connector with serverUrl.
    try:
        r = client.get(_kbn("/api/actions/connectors"), headers=_kbn_headers(), timeout=20.0)
        r.raise_for_status()
        connectors = r.json()
    except Exception as exc:
        return StepResult(
            3, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"connectors fetch failed: {exc}",
            detail,
        )
    mcp_connectors = [
        c for c in connectors
        if c.get("connector_type_id") == ".mcp" and (c.get("config") or {}).get("serverUrl")
    ]
    detail["mcp_connectors"] = len(mcp_connectors)
    if not mcp_connectors:
        problems.append(".mcp connector missing or has no serverUrl")
    else:
        detail["mcp_server_url"] = mcp_connectors[0].get("config", {}).get("serverUrl")

    # 3e: alerting rule for the workflow.
    try:
        r = client.get(
            _kbn("/api/alerting/rules/_find"),
            params={"per_page": 100, "search": EXPECTED_RULE_NAME, "search_fields": "name"},
            headers=_kbn_headers(),
            timeout=20.0,
        )
        r.raise_for_status()
        rules = r.json().get("data", [])
    except Exception as exc:
        return StepResult(
            3, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"alerting rules find failed: {exc}",
            detail,
        )
    matching_rules = [rl for rl in rules if rl.get("name") == EXPECTED_RULE_NAME]
    detail["alerting_rules"] = len(matching_rules)
    if not matching_rules:
        problems.append(f"alerting rule '{EXPECTED_RULE_NAME}' missing")

    notes = (
        f"dashboards={detail.get('dashboard_total', 0)} "
        f"(demo {len(EXPECTED_DEMO_DASHBOARDS) - len(missing_dash)}/{len(EXPECTED_DEMO_DASHBOARDS)}, "
        f"customer-fit={detail['customer_fit_dashboards']}), "
        f"fec-tools={detail['fec_tools_present']}/12, "
        f"agent={'yes' if EXPECTED_MASTER_AGENT_ID in agent_ids else 'no'}, "
        f"mcp={detail['mcp_connectors']}, rule={detail['alerting_rules']}"
    )
    if problems:
        return StepResult(
            3, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            notes + " | " + "; ".join(problems),
            detail,
        )
    return StepResult(3, name, "PASS", int((time.monotonic() - t0) * 1000), notes, detail)


def step_4_mcp_server(client: httpx.Client) -> StepResult:
    name = "MCP server (tools/list = 12, fec_cost_calc tool/call)"
    t0 = time.monotonic()
    detail: Dict[str, Any] = {}
    mcp_url = f"{API_BASE}/mcp"

    try:
        r = client.post(
            mcp_url,
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
            timeout=15.0,
        )
        r.raise_for_status()
        body = r.json()
    except Exception as exc:
        return StepResult(
            4, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"mcp tools/list failed: {exc}",
        )
    tools = ((body.get("result") or {}).get("tools")) or []
    tool_names = [t.get("name") for t in tools]
    detail["tool_count"] = len(tools)
    detail["tools"] = tool_names
    if len(tools) != 12:
        return StepResult(
            4, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"expected 12 MCP tools, got {len(tools)}: {tool_names}",
            detail,
        )
    missing = [t for t in EXPECTED_FEC_TOOLS if t not in tool_names]
    if missing:
        return StepResult(
            4, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"missing MCP tools: {','.join(missing)}",
            detail,
        )

    # Pure-compute call (no Anthropic, no ES) -> fec_cost_calc.
    try:
        r = client.post(
            mcp_url,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "fec_cost_calc",
                    "arguments": {
                        "ingest_gb_day": 50,
                        "retention_months": 12,
                        "current_spend_annual_usd": 1_000_000,
                    },
                },
            },
            timeout=15.0,
        )
        r.raise_for_status()
        body = r.json()
    except Exception as exc:
        return StepResult(
            4, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"fec_cost_calc tools/call HTTP failed: {exc}",
            detail,
        )

    result = body.get("result") or {}
    is_error = result.get("isError")
    contents = result.get("content") or []
    text_payload = ""
    if contents and isinstance(contents, list):
        text_payload = contents[0].get("text", "")
    detail["cost_calc_isError"] = is_error
    if is_error:
        return StepResult(
            4, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"fec_cost_calc returned isError=true: {text_payload[:200]}",
            detail,
        )
    try:
        parsed = json.loads(text_payload) if text_payload else {}
    except Exception:
        parsed = {}
    has_elastic = bool(((parsed.get("elastic") or {}).get("total_annual_usd") is not None))
    has_splunk = bool(((parsed.get("splunk") or {}).get("total_annual_usd") is not None))
    detail["cost_calc_has_elastic"] = has_elastic
    detail["cost_calc_has_splunk"] = has_splunk
    if not (has_elastic and has_splunk):
        return StepResult(
            4, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"fec_cost_calc payload missing elastic/splunk totals; got keys={list(parsed.keys())}",
            detail,
        )

    return StepResult(
        4, name, "PASS",
        int((time.monotonic() - t0) * 1000),
        f"tools/list=12, fec_cost_calc OK (elastic ${parsed['elastic']['total_annual_usd']:,.0f})",
        detail,
    )


def step_5_tools_rest(client: httpx.Client) -> StepResult:
    name = "Tools REST (compute + knowledge-search; OPTIONS for heavy)"
    t0 = time.monotonic()
    detail: Dict[str, Any] = {}
    problems: List[str] = []
    sub: List[str] = []

    # 5a: cost-calc (pure compute).
    try:
        r = client.post(
            f"{API_BASE}/tools/cost-calc",
            json={
                "ingest_gb_day": 50,
                "retention_months": 12,
                "current_spend_annual_usd": 1_000_000,
            },
            timeout=15.0,
        )
        ok = r.status_code == 200 and isinstance((r.json() or {}).get("elastic"), dict)
        sub.append(f"cost-calc={r.status_code}")
        detail["cost_calc_status"] = r.status_code
        if not ok:
            problems.append("cost-calc not ok")
    except Exception as exc:
        problems.append(f"cost-calc exc: {exc}")

    # 5b: capacity (pure compute).
    try:
        r = client.post(
            f"{API_BASE}/tools/capacity",
            json={
                "peak_indexing_eps": 10000,
                "hot_data_gb": 1000,
                "warm_data_gb": 500,
            },
            timeout=15.0,
        )
        ok = r.status_code == 200
        sub.append(f"capacity={r.status_code}")
        detail["capacity_status"] = r.status_code
        if not ok:
            problems.append("capacity not ok")
    except Exception as exc:
        problems.append(f"capacity exc: {exc}")

    # 5c: knowledge-search (light: top_k=2).
    try:
        r = client.post(
            f"{API_BASE}/tools/knowledge-search",
            json={"query": "ELSER", "top_k": 2},
            timeout=120.0,
        )
        ok = r.status_code == 200 and isinstance((r.json() or {}).get("answer"), str)
        sub.append(f"knowledge-search={r.status_code}")
        detail["knowledge_status"] = r.status_code
        if r.status_code == 200:
            payload = r.json() or {}
            detail["knowledge_answer_len"] = len(payload.get("answer") or "")
            detail["knowledge_citations"] = len(payload.get("citations") or [])
        if not ok:
            problems.append("knowledge-search not ok")
    except Exception as exc:
        problems.append(f"knowledge-search exc: {exc}")

    # 5d: heavy Claude tools: existence check via OPTIONS or 4xx-but-not-404 POST.
    heavy_routes = [
        ("/tools/compliance-mapping", {"regulations": ["GDPR"]}),
        ("/tools/code-sample", {"language": "Python", "use_case": "ping"}),
        ("/tools/troubleshoot", {"error_text": "x"}),  # min_length=3 will 422
        ("/tools/stack-extract", {"text": "x"}),  # min_length=20 will 422
        ("/tools/poc-plan/__no_such_meeting__", None),  # 404 expected, route exists
    ]
    heavy_status: Dict[str, int] = {}
    for path, _ in heavy_routes:
        try:
            r = client.options(f"{API_BASE}{path}", timeout=10.0)
            heavy_status[path] = r.status_code
            # OPTIONS returns 200 if path exists in FastAPI (or 405 with allow header).
            if r.status_code == 404:
                problems.append(f"route {path} returns 404 on OPTIONS (missing)")
        except Exception as exc:
            problems.append(f"OPTIONS {path} exc: {exc}")
            heavy_status[path] = -1
    detail["heavy_route_status"] = heavy_status
    sub.append(f"heavy-routes={'/'.join(str(v) for v in heavy_status.values())}")

    notes = ", ".join(sub)
    if problems:
        return StepResult(
            5, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            notes + " | " + "; ".join(problems),
            detail,
        )
    return StepResult(5, name, "PASS", int((time.monotonic() - t0) * 1000), notes, detail)


def step_6_workflow(client: httpx.Client) -> StepResult:
    name = "Workflow status + webhook handler"
    t0 = time.monotonic()
    detail: Dict[str, Any] = {}
    problems: List[str] = []

    try:
        r = client.get(f"{API_BASE}/workflows/status", timeout=15.0)
        r.raise_for_status()
        body = r.json()
    except Exception as exc:
        return StepResult(
            6, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"workflows/status failed: {exc}",
            detail,
        )
    detail["registered"] = body.get("registered")
    detail["rule_status"] = body.get("rule_status")
    detail["connector_status"] = body.get("connector_status")
    if not body.get("registered"):
        problems.append("workflow not registered")
    if body.get("rule_status") not in ("registered", "unknown"):
        problems.append(f"rule_status={body.get('rule_status')}")

    # Synthetic dummy payload that the handler should accept and short-circuit on.
    try:
        r = client.post(
            f"{API_BASE}/workflows/triggered",
            json={
                "alert_id": "smoke-test-no-op",
                "rule_id": "smoke-test-no-op",
                "rule_name": "Smoke Test",
                "_smoke_test": True,
            },
            timeout=30.0,
        )
        ok = r.status_code in (200, 202)
        webhook_body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    except Exception as exc:
        return StepResult(
            6, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"workflows/triggered failed: {exc}",
            detail,
        )
    detail["webhook_status"] = r.status_code
    detail["webhook_processed"] = webhook_body.get("processed_count", 0) if isinstance(webhook_body, dict) else None
    if not ok:
        problems.append(f"webhook returned {r.status_code}")

    notes = (
        f"registered={detail['registered']}, rule={detail['rule_status']}, "
        f"connector={detail['connector_status']}, webhook_status={detail['webhook_status']}"
    )
    if problems:
        return StepResult(
            6, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            notes + " | " + "; ".join(problems),
            detail,
        )
    return StepResult(6, name, "PASS", int((time.monotonic() - t0) * 1000), notes, detail)


def step_7_frontend(client: httpx.Client) -> StepResult:
    name = "Frontend pages reachable"
    t0 = time.monotonic()
    detail: Dict[str, Any] = {}
    problems: List[str] = []
    page_summary: List[str] = []

    for path, required in FRONTEND_PAGES:
        url = f"{BACKEND_BASE}{path}"
        try:
            r = client.get(url, timeout=10.0)
            ok = r.status_code == 200 and len(r.content) >= 256
            detail[path] = {"status": r.status_code, "bytes": len(r.content)}
            page_summary.append(f"{path}={r.status_code}/{len(r.content)}b")
            if not ok and required:
                problems.append(f"{path} status={r.status_code} bytes={len(r.content)}")
            elif not ok and not required:
                # optional: just record.
                pass
        except Exception as exc:
            detail[path] = {"error": str(exc)}
            page_summary.append(f"{path}=ERR")
            if required:
                problems.append(f"{path} exc: {exc}")

    notes = ", ".join(page_summary[:9])
    if problems:
        return StepResult(
            7, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            notes + " | " + "; ".join(problems),
            detail,
        )
    return StepResult(7, name, "PASS", int((time.monotonic() - t0) * 1000), notes, detail)


def step_8_dash_audit() -> StepResult:
    name = "Em/en dash audit (backend + frontend + docs + data)"
    t0 = time.monotonic()
    targets = [BACKEND_DIR, FRONTEND_DIR, DOCS_DIR, DATA_DIR]
    targets = [p for p in targets if p.exists()]
    bad_paths: List[Tuple[str, int]] = []
    text_exts = {
        ".py", ".html", ".js", ".mjs", ".ts", ".tsx", ".jsx",
        ".css", ".md", ".json", ".jsonl", ".yml", ".yaml", ".txt", ".sh", ".cfg", ".ini", ".toml",
    }
    skip_dirs = {
        "__pycache__", "node_modules", ".venv", ".git", "site-packages",
        "screenshots", "gifs",
    }
    skip_filenames = {Path(__file__).name}
    # Use unicode escapes here so this script itself does not show up in its own audit.
    em = "\u2014"  # em dash (unicode-escaped so this script does not self-flag)
    en = "\u2013"  # en dash (unicode-escaped so this script does not self-flag)
    total_files = 0
    for root in targets:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fname in filenames:
                if fname in skip_filenames:
                    continue
                p = Path(dirpath) / fname
                if p.suffix.lower() not in text_exts:
                    continue
                total_files += 1
                try:
                    txt = p.read_text(encoding="utf-8", errors="strict")
                except Exception:
                    continue
                count = txt.count(em) + txt.count(en)
                if count:
                    bad_paths.append((str(p.relative_to(REPO_ROOT)), count))
    detail = {
        "files_scanned": total_files,
        "files_with_dashes": len(bad_paths),
        "examples": bad_paths[:5],
    }
    notes = f"scanned={total_files} files, dash hits={len(bad_paths)}"
    if bad_paths:
        examples = "; ".join(f"{p}({n})" for p, n in bad_paths[:3])
        return StepResult(
            8, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            notes + " | " + examples,
            detail,
        )
    return StepResult(8, name, "PASS", int((time.monotonic() - t0) * 1000), notes, detail)


def step_9_git() -> StepResult:
    name = "Git status (uncommitted <=2; HEAD == origin/main)"
    t0 = time.monotonic()
    detail: Dict[str, Any] = {}
    if not shutil.which("git"):
        return StepResult(
            9, name, "SKIP",
            int((time.monotonic() - t0) * 1000),
            "git not installed",
        )

    def _git(args: List[str]) -> Tuple[int, str]:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=15,
        )
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    rc, out = _git(["status", "--porcelain"])
    if rc != 0:
        return StepResult(
            9, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            f"git status rc={rc}: {out[:120]}",
            detail,
        )
    lines = [ln for ln in out.splitlines() if ln.strip()]
    detail["uncommitted_lines"] = len(lines)
    detail["uncommitted_sample"] = lines[:5]

    # Modified-only count (M, AM, etc.) excluding untracked (??).
    mod_lines = [ln for ln in lines if not ln.startswith("??")]
    detail["modified_lines"] = len(mod_lines)

    rc1, head = _git(["rev-parse", "HEAD"])
    rc2, origin = _git(["rev-parse", "origin/main"])
    detail["head"] = head.strip()[:12]
    detail["origin_main"] = origin.strip()[:12]
    pushed = rc1 == 0 and rc2 == 0 and head.strip() == origin.strip()
    detail["pushed_to_origin_main"] = pushed

    problems: List[str] = []
    if len(mod_lines) > 2:
        problems.append(f"{len(mod_lines)} modified files (>2)")
    if not pushed:
        problems.append("HEAD != origin/main")

    notes = (
        f"uncommitted={len(lines)} (modified={len(mod_lines)}, untracked={len(lines) - len(mod_lines)}), "
        f"HEAD={detail['head']}, origin/main={detail['origin_main']}"
    )
    if problems:
        return StepResult(
            9, name, "FAIL",
            int((time.monotonic() - t0) * 1000),
            notes + " | " + "; ".join(problems),
            detail,
        )
    return StepResult(9, name, "PASS", int((time.monotonic() - t0) * 1000), notes, detail)


# --------------------------------------------------------------------------- Reporting

def _emit_line(result: StepResult) -> None:
    tag = f"[{result.status}]"
    line = f"{tag} step {result.step_id}: {result.name} ({result.duration_ms} ms)"
    if result.notes:
        line += f"  --  {result.notes}"
    print(line, flush=True)


def _verdict(results: List[StepResult]) -> Tuple[str, int, int, int]:
    passed = sum(1 for r in results if r.status == "PASS")
    failed = sum(1 for r in results if r.status == "FAIL")
    skipped = sum(1 for r in results if r.status == "SKIP")
    critical_failures = [r for r in results if r.status == "FAIL" and r.step_id in CRITICAL_STEPS]
    non_critical_failures = [r for r in results if r.status == "FAIL" and r.step_id in NON_CRITICAL_STEPS]
    if critical_failures:
        verdict = "NO-GO"
    elif len(non_critical_failures) >= 1 and len(non_critical_failures) <= 2:
        verdict = "CAUTION"
    elif non_critical_failures:
        verdict = "NO-GO"
    else:
        verdict = "GO"
    return verdict, passed, failed, skipped


def _write_report(
    results: List[StepResult],
    verdict: str,
    passed: int,
    failed: int,
    skipped: int,
    runtime_s: float,
) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: List[str] = []
    lines.append("# FE Copilot Integration Smoke Report")
    lines.append("")
    lines.append(f"- Generated: {now}")
    lines.append(f"- Backend base: {BACKEND_BASE}")
    lines.append(f"- Elasticsearch: {ES_URL or '(none)'}")
    lines.append(f"- Kibana: {KIBANA_URL or '(none)'}")
    lines.append(f"- Total runtime: {runtime_s:.2f} s")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"**{verdict}**  --  passed={passed}, failed={failed}, skipped={skipped}")
    lines.append("")
    lines.append("Critical steps (1, 2, 3, 4, 7) must all pass.")
    lines.append("Non-critical steps (5, 6, 8, 9) may fail up to 2 times for CAUTION.")
    lines.append("")
    lines.append("## Step Results")
    lines.append("")
    lines.append("| # | Step | Status | Critical | Duration (ms) | Notes |")
    lines.append("| ---: | --- | --- | --- | ---: | --- |")
    for r in sorted(results, key=lambda r: r.step_id):
        crit = "yes" if r.step_id in CRITICAL_STEPS else "no"
        notes = (r.notes or "").replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {r.step_id} | {r.name} | {r.status} | {crit} | {r.duration_ms} | {notes} |"
        )
    lines.append("")
    lines.append("## Aggregate")
    lines.append("")
    lines.append(f"- passed: {passed}")
    lines.append(f"- failed: {failed}")
    lines.append(f"- skipped: {skipped}")
    lines.append(f"- total steps: {len(results)}")
    lines.append("")
    lines.append("## Raw Detail")
    lines.append("")
    lines.append("```json")
    payload = {
        r.step_id: {
            "name": r.name,
            "status": r.status,
            "duration_ms": r.duration_ms,
            "notes": r.notes,
            "detail": r.detail,
        }
        for r in sorted(results, key=lambda r: r.step_id)
    }
    lines.append(json.dumps(payload, indent=2, default=str, ensure_ascii=False))
    lines.append("```")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- Main

def main() -> int:
    print(f"FE Copilot integration smoke -- backend={BACKEND_BASE}", flush=True)
    started = time.monotonic()

    runners: List[Tuple[int, str, bool, Any]] = [
        (1, "backend", True, step_1_backend),
        (2, "elasticsearch", True, step_2_elasticsearch),
        (3, "kibana_saved_objects", True, step_3_kibana_saved_objects),
        (4, "mcp_server", True, step_4_mcp_server),
        (5, "tools_rest", False, step_5_tools_rest),
        (6, "workflow", False, step_6_workflow),
        (7, "frontend_pages", True, step_7_frontend),
        (8, "dash_audit", False, step_8_dash_audit),
        (9, "git_status", False, step_9_git),
    ]
    results: List[StepResult] = []

    with httpx.Client(verify=True, follow_redirects=True) as client:
        for step_id, _slug, _crit, fn in runners:
            try:
                if fn in (step_8_dash_audit, step_9_git):
                    res = fn()
                else:
                    res = fn(client)
            except Exception as exc:
                res = StepResult(
                    step_id,
                    f"step {step_id} (uncaught)",
                    "FAIL",
                    0,
                    f"uncaught exception: {exc}",
                )
            results.append(res)
            _emit_line(res)

    runtime_s = time.monotonic() - started
    verdict, passed, failed, skipped = _verdict(results)

    print("", flush=True)
    print(
        f"VERDICT: {verdict}  --  passed={passed}, failed={failed}, skipped={skipped}, runtime={runtime_s:.2f}s",
        flush=True,
    )
    print(f"REPORT: {REPORT_PATH}", flush=True)

    _write_report(results, verdict, passed, failed, skipped, runtime_s)

    if verdict == "NO-GO":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
