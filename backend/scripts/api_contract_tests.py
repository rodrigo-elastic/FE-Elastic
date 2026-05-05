"""
filename: api_contract_tests.py
description: API contract tests for every backend route under /api/v1/*. Iterates over a deterministic catalog of endpoints (built by hand from app.main include_router calls) and asserts the expected status codes for happy path, missing resource, invalid payload, and method-not-allowed cases. Heavy Claude-backed POSTs and Kibana writes are exercised only with structurally invalid payloads (so the contract is checked without burning credits or mutating cluster state); MCP tools/call paths that need Anthropic credits are explicitly SKIPped with a reason. Prints a per-endpoint table and exits non-zero on any contract violation.
date: 04-05-2026
"""
from __future__ import annotations

__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_BACKEND_PORT = int(os.environ.get("APP_PORT", "8123"))
BASE = os.environ.get("CONTRACT_BASE", f"http://localhost:{DEFAULT_BACKEND_PORT}").rstrip("/")
API = BASE + "/api/v1"

# ---------------------------------------------------------------- types

@dataclass
class CaseResult:
    label: str  # "happy" | "missing" | "invalid" | "wrong-method" | "cors"
    method: str
    path: str
    expected: str  # human description, e.g. "200" or "404 or 422"
    observed: int
    pass_: bool
    note: str = ""


@dataclass
class EndpointResult:
    method: str
    path: str
    cases: List[CaseResult] = field(default_factory=list)


# ---------------------------------------------------------------- helpers

def _get(client: httpx.Client, path: str, **kw) -> httpx.Response:
    return client.get(API + path, **kw)


def _post(client: httpx.Client, path: str, json_body: Any = None, **kw) -> httpx.Response:
    return client.post(API + path, json=json_body, **kw)


def _delete(client: httpx.Client, path: str, **kw) -> httpx.Response:
    return client.delete(API + path, **kw)


def _options(client: httpx.Client, path: str, **kw) -> httpx.Response:
    return client.options(API + path, headers={"Origin": "http://example.test", "Access-Control-Request-Method": "GET"}, **kw)


def _put(client: httpx.Client, path: str, **kw) -> httpx.Response:
    return client.put(API + path, **kw)


def _expect(observed: int, expected_codes: List[int]) -> bool:
    return observed in expected_codes


def _short_note(resp: httpx.Response, limit: int = 140) -> str:
    txt = (resp.text or "").strip().replace("\n", " ")
    return txt[:limit]


# ---------------------------------------------------------------- bootstrap discovery

def _bootstrap_ids(client: httpx.Client) -> Dict[str, str]:
    ids: Dict[str, str] = {
        "meeting_id": "northwind-mtg-prev-001",  # known synthetic fallback
        "event_id": "gcal-evt-005",
        "industry_id": "fsi-banking",
        "battlecard_slug": "splunk",
        "scenario_id": "black-friday-outage",
        "company_id": "northwind-bank",
    }
    # Try to read live values; if backend is up we should refresh defaults.
    try:
        r = _get(client, "/meetings", timeout=10)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                ids["meeting_id"] = data[0]["id"]
                ids["company_id"] = data[0].get("company_id") or ids["company_id"]
    except Exception:
        pass
    try:
        r = _get(client, "/calendar/events", timeout=10)
        if r.status_code == 200:
            items = (r.json() or {}).get("items") or []
            if items:
                ids["event_id"] = items[0]["id"]
    except Exception:
        pass
    try:
        r = _get(client, "/industries", timeout=10)
        if r.status_code == 200:
            items = (r.json() or {}).get("items") or []
            if items:
                ids["industry_id"] = items[0].get("id") or ids["industry_id"]
    except Exception:
        pass
    try:
        r = _get(client, "/battlecards", timeout=10)
        if r.status_code == 200:
            items = (r.json() or {}).get("items") or []
            if items:
                ids["battlecard_slug"] = items[0].get("competitor_slug") or ids["battlecard_slug"]
    except Exception:
        pass
    try:
        r = _get(client, "/demo-data/scenarios", timeout=10)
        if r.status_code == 200:
            items = (r.json() or {}).get("scenarios") or []
            if items:
                ids["scenario_id"] = items[0].get("id") or ids["scenario_id"]
    except Exception:
        pass
    return ids


# ---------------------------------------------------------------- contract test runner

def _record(results: List[CaseResult], label: str, method: str, path: str,
            expected_codes: List[int], observed: int, note: str = "") -> None:
    results.append(
        CaseResult(
            label=label,
            method=method,
            path=path,
            expected=" or ".join(str(c) for c in expected_codes),
            observed=observed,
            pass_=_expect(observed, expected_codes),
            note=note,
        )
    )


def _check_cors(client: httpx.Client, results: List[CaseResult], method: str, path: str) -> None:
    """Assert the CORS preflight response carries the expected ACA-Origin header.

    FastAPI's CORSMiddleware only emits ACAO when the request includes Origin and
    Access-Control-Request-Method. We send both. Backend is configured with
    cors_allow_origins so a 200 with a non-empty ACA-Origin header is the contract.
    """
    try:
        r = _options(client, path, timeout=10)
    except Exception as exc:
        _record(results, "cors", method, path, [200, 204], 0, f"exc {exc}")
        return
    aca = r.headers.get("access-control-allow-origin", "")
    note = f"aca-origin={aca!r}, status={r.status_code}"
    # Some routes (like the static frontend mount) may not preflight; but our
    # /api/v1/* routes go through CORSMiddleware. Accept 200 with ACAO present.
    ok = (r.status_code in (200, 204)) and bool(aca)
    results.append(
        CaseResult(
            label="cors",
            method=method,
            path=path,
            expected="200/204 + ACAO header",
            observed=r.status_code,
            pass_=ok,
            note=note,
        )
    )


# Heavy LLM tools we won't exercise on happy path; instead we send a structurally
# invalid payload and expect 422. They are also OPTIONS-checked.
HEAVY_TOOLS = {
    "/tools/poc-plan/{meeting_id}",
    "/tools/spl-to-esql",
    "/tools/compliance-mapping",
    "/tools/stack-extract",
    "/tools/code-sample",
    "/tools/troubleshoot",
    "/tools/compare",
    "/tools/orchestrator",
    "/tools/proposal",
    "/tools/knowledge-search",
    "/agents/pre-meeting/ad-hoc",
    "/agents/pre-meeting/{meeting_id}",
    "/agents/post-meeting/from-transcript",
    "/agents/post-meeting/{meeting_id}",
    "/agents/live-meeting/{meeting_id}/turn/{turn_index}",
}


def run_contract_tests(client: httpx.Client) -> Tuple[List[EndpointResult], int, int]:
    ids = _bootstrap_ids(client)
    bad_id = "__no_such_id_for_contract_check__"
    endpoints: List[EndpointResult] = []
    skip_count = 0
    violation_count = 0

    # ---------- routes_health ----------
    for method, path, expected_codes in [
        ("GET", "/health", [200]),
        ("GET", "/version", [200]),
        ("GET", "/info", [200]),
        ("GET", "/health/full", [200]),
    ]:
        ep = EndpointResult(method, path)
        r = _get(client, path, timeout=10)
        _record(ep.cases, "happy", method, path, expected_codes, r.status_code, _short_note(r))
        # wrong method (POST on a GET endpoint)
        wm = client.post(API + path, timeout=10)
        _record(ep.cases, "wrong-method", "POST", path, [405], wm.status_code)
        _check_cors(client, ep.cases, method, path)
        endpoints.append(ep)

    # POST /elasticsearch/reconnect : returns 200 either way (graceful).
    ep = EndpointResult("POST", "/elasticsearch/reconnect")
    r = _post(client, "/elasticsearch/reconnect", json_body={}, timeout=15)
    _record(ep.cases, "happy", "POST", "/elasticsearch/reconnect", [200], r.status_code, _short_note(r))
    wm = _get(client, "/elasticsearch/reconnect", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/elasticsearch/reconnect", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/elasticsearch/reconnect")
    endpoints.append(ep)

    # POST /kibana/setup : ok on GET = 405. happy = 200 even when Kibana not configured.
    ep = EndpointResult("POST", "/kibana/setup")
    r = _post(client, "/kibana/setup", json_body={}, timeout=20)
    _record(ep.cases, "happy", "POST", "/kibana/setup", [200, 502, 409], r.status_code, _short_note(r))
    wm = _get(client, "/kibana/setup", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/kibana/setup", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/kibana/setup")
    endpoints.append(ep)

    # ---------- routes_meetings ----------
    ep = EndpointResult("GET", "/meetings")
    r = _get(client, "/meetings", timeout=10)
    _record(ep.cases, "happy", "GET", "/meetings", [200], r.status_code, _short_note(r))
    wm = client.post(API + "/meetings", timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/meetings", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/meetings")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/meetings/upcoming")
    r = _get(client, "/meetings/upcoming", timeout=10)
    _record(ep.cases, "happy", "GET", "/meetings/upcoming", [200], r.status_code, _short_note(r))
    wm = client.post(API + "/meetings/upcoming", timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/meetings/upcoming", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/meetings/upcoming")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/meetings/{meeting_id}")
    r = _get(client, f"/meetings/{ids['meeting_id']}", timeout=10)
    _record(ep.cases, "happy", "GET", "/meetings/{meeting_id}", [200], r.status_code, _short_note(r))
    r2 = _get(client, f"/meetings/{bad_id}", timeout=10)
    _record(ep.cases, "missing", "GET", "/meetings/{meeting_id}", [404], r2.status_code)
    _check_cors(client, ep.cases, "GET", "/meetings/{meeting_id}")
    endpoints.append(ep)

    # ---------- routes_agents (heavy: invalid only) ----------
    ep = EndpointResult("POST", "/agents/pre-meeting/ad-hoc")
    r1 = _post(client, "/agents/pre-meeting/ad-hoc", json_body={}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/agents/pre-meeting/ad-hoc", [422], r1.status_code, "empty body")
    r2 = _post(client, "/agents/pre-meeting/ad-hoc", json_body={"company_name": ""}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/agents/pre-meeting/ad-hoc", [422], r2.status_code, "empty company_name")
    wm = _get(client, "/agents/pre-meeting/ad-hoc", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/agents/pre-meeting/ad-hoc", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/agents/pre-meeting/ad-hoc")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/agents/pre-meeting/{meeting_id}")
    # Heavy LLM call - skip happy. Instead probe missing meeting (cheap path, 404 raised before LLM).
    r = _post(client, f"/agents/pre-meeting/{bad_id}", json_body=None, timeout=15)
    _record(ep.cases, "missing", "POST", "/agents/pre-meeting/{meeting_id}", [404], r.status_code, _short_note(r))
    skip_count += 1  # happy path skipped (Anthropic credits)
    wm = _get(client, f"/agents/pre-meeting/{bad_id}", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/agents/pre-meeting/{meeting_id}", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/agents/pre-meeting/{meeting_id}")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/agents/post-meeting/from-transcript")
    r1 = _post(client, "/agents/post-meeting/from-transcript", json_body={}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/agents/post-meeting/from-transcript", [422], r1.status_code, "empty body")
    r2 = _post(client, "/agents/post-meeting/from-transcript",
               json_body={"company_name": "X", "transcript_text": "x"}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/agents/post-meeting/from-transcript", [422], r2.status_code, "transcript too short")
    wm = _get(client, "/agents/post-meeting/from-transcript", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/agents/post-meeting/from-transcript", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/agents/post-meeting/from-transcript")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/agents/post-meeting/{meeting_id}")
    r = _post(client, f"/agents/post-meeting/{bad_id}", json_body=None, timeout=15)
    _record(ep.cases, "missing", "POST", "/agents/post-meeting/{meeting_id}", [404], r.status_code, _short_note(r))
    skip_count += 1
    wm = _get(client, f"/agents/post-meeting/{bad_id}", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/agents/post-meeting/{meeting_id}", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/agents/post-meeting/{meeting_id}")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/agents/live-meeting/{meeting_id}/turn/{turn_index}")
    r = _post(client, f"/agents/live-meeting/{bad_id}/turn/0", json_body=None, timeout=15)
    _record(ep.cases, "missing", "POST", "/agents/live-meeting/{meeting_id}/turn/{turn_index}",
            [404], r.status_code, _short_note(r))
    r_invalid = _post(client, f"/agents/live-meeting/{ids['meeting_id']}/turn/notanumber",
                      json_body=None, timeout=10)
    _record(ep.cases, "invalid", "POST", "/agents/live-meeting/{meeting_id}/turn/{turn_index}",
            [422], r_invalid.status_code, "non-int turn_index")
    skip_count += 1
    wm = _get(client, f"/agents/live-meeting/{bad_id}/turn/0", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/agents/live-meeting/{meeting_id}/turn/{turn_index}",
            [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/agents/live-meeting/{meeting_id}/turn/{turn_index}")
    endpoints.append(ep)

    # ---------- routes_briefs ----------
    ep = EndpointResult("GET", "/briefs")
    r = _get(client, "/briefs", timeout=10)
    _record(ep.cases, "happy", "GET", "/briefs", [200], r.status_code, _short_note(r))
    wm = _post(client, "/briefs", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/briefs", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/briefs")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/briefs/reindex")
    r = _post(client, "/briefs/reindex", json_body={}, timeout=30)
    _record(ep.cases, "happy", "POST", "/briefs/reindex", [200, 503], r.status_code, _short_note(r))
    wm = _get(client, "/briefs/reindex", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/briefs/reindex", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/briefs/reindex")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/briefs/{meeting_id}")
    # /briefs/{meeting_id} returns 200 with {exists: false} when missing - not 404.
    r = _get(client, f"/briefs/{ids['meeting_id']}", timeout=10)
    _record(ep.cases, "happy", "GET", "/briefs/{meeting_id}", [200], r.status_code, _short_note(r))
    r2 = _get(client, f"/briefs/{bad_id}", timeout=10)
    _record(ep.cases, "missing", "GET", "/briefs/{meeting_id}",
            [200, 404], r2.status_code, "by design returns 200 + exists:false")
    _check_cors(client, ep.cases, "GET", "/briefs/{meeting_id}")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/briefs/{meeting_id}/artifact")
    r = _get(client, f"/briefs/{bad_id}/artifact", timeout=10)
    _record(ep.cases, "missing", "GET", "/briefs/{meeting_id}/artifact", [404], r.status_code, _short_note(r))
    _check_cors(client, ep.cases, "GET", "/briefs/{meeting_id}/artifact")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/briefs/{meeting_id}/post")
    r = _get(client, f"/briefs/{ids['meeting_id']}/post", timeout=10)
    _record(ep.cases, "happy", "GET", "/briefs/{meeting_id}/post", [200], r.status_code, _short_note(r))
    r2 = _get(client, f"/briefs/{bad_id}/post", timeout=10)
    _record(ep.cases, "missing", "GET", "/briefs/{meeting_id}/post",
            [200, 404], r2.status_code, "by design returns 200 + exists:false")
    _check_cors(client, ep.cases, "GET", "/briefs/{meeting_id}/post")
    endpoints.append(ep)

    # ---------- routes_audit ----------
    ep = EndpointResult("GET", "/audit")
    r = _get(client, "/audit", timeout=10)
    _record(ep.cases, "happy", "GET", "/audit", [200], r.status_code, _short_note(r))
    wm = _post(client, "/audit", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/audit", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/audit")
    endpoints.append(ep)

    # ---------- routes_battlecards ----------
    ep = EndpointResult("GET", "/battlecards")
    r = _get(client, "/battlecards", timeout=10)
    _record(ep.cases, "happy", "GET", "/battlecards", [200], r.status_code, _short_note(r))
    wm = _delete(client, "/battlecards", timeout=10)
    _record(ep.cases, "wrong-method", "DELETE", "/battlecards", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/battlecards")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/battlecards/by-competitor/{name}")
    r = _get(client, f"/battlecards/by-competitor/{ids['battlecard_slug']}", timeout=10)
    _record(ep.cases, "happy", "GET", "/battlecards/by-competitor/{name}", [200], r.status_code, _short_note(r))
    r2 = _get(client, f"/battlecards/by-competitor/{bad_id}", timeout=10)
    _record(ep.cases, "missing", "GET", "/battlecards/by-competitor/{name}", [404], r2.status_code)
    _check_cors(client, ep.cases, "GET", "/battlecards/by-competitor/{name}")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/battlecards/reseed")
    r = _post(client, "/battlecards/reseed", json_body={}, timeout=30)
    _record(ep.cases, "happy", "POST", "/battlecards/reseed", [200], r.status_code, _short_note(r))
    wm = _get(client, "/battlecards/reseed", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/battlecards/reseed", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/battlecards/reseed")
    endpoints.append(ep)

    # ---------- routes_salesforce ----------
    ep = EndpointResult("GET", "/salesforce/tasks")
    r = _get(client, "/salesforce/tasks", timeout=10)
    _record(ep.cases, "happy", "GET", "/salesforce/tasks", [200], r.status_code, _short_note(r))
    wm = _post(client, "/salesforce/tasks", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/salesforce/tasks", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/salesforce/tasks")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/salesforce/account/{company_id}")
    r = _get(client, f"/salesforce/account/{ids['company_id']}", timeout=10)
    _record(ep.cases, "happy", "GET", "/salesforce/account/{company_id}", [200], r.status_code, _short_note(r))
    # Note: by design returns 200 with empty company - not 404. Document and accept either.
    r2 = _get(client, f"/salesforce/account/{bad_id}", timeout=10)
    _record(ep.cases, "missing", "GET", "/salesforce/account/{company_id}",
            [200, 404], r2.status_code, "by design returns 200 with empty company info")
    _check_cors(client, ep.cases, "GET", "/salesforce/account/{company_id}")
    endpoints.append(ep)

    # ---------- routes_calendar ----------
    ep = EndpointResult("GET", "/calendar/events")
    r = _get(client, "/calendar/events", timeout=10)
    _record(ep.cases, "happy", "GET", "/calendar/events", [200], r.status_code, _short_note(r))
    wm = _post(client, "/calendar/events", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/calendar/events", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/calendar/events")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/calendar/events/{event_id}")
    r = _get(client, f"/calendar/events/{ids['event_id']}", timeout=10)
    _record(ep.cases, "happy", "GET", "/calendar/events/{event_id}", [200], r.status_code, _short_note(r))
    r2 = _get(client, f"/calendar/events/{bad_id}", timeout=10)
    _record(ep.cases, "missing", "GET", "/calendar/events/{event_id}", [404], r2.status_code)
    _check_cors(client, ep.cases, "GET", "/calendar/events/{event_id}")
    endpoints.append(ep)

    # ---------- routes_tools ----------
    # Heavy LLM tools: only invalid (empty body) and wrong-method probes.
    heavy_post_tools = [
        ("/tools/poc-plan/{meeting_id}", f"/tools/poc-plan/{bad_id}", {}, "missing meeting"),
        ("/tools/spl-to-esql", "/tools/spl-to-esql", {}, "empty body"),
        ("/tools/compliance-mapping", "/tools/compliance-mapping", {}, "empty body"),
        ("/tools/stack-extract", "/tools/stack-extract", {"text": "x"}, "text too short"),
        ("/tools/code-sample", "/tools/code-sample", {}, "empty body"),
        ("/tools/troubleshoot", "/tools/troubleshoot", {"error_text": "x"}, "error_text too short"),
        ("/tools/compare", "/tools/compare", {}, "empty body"),
        ("/tools/orchestrator", "/tools/orchestrator", {}, "empty body"),
        ("/tools/proposal", "/tools/proposal", {}, "empty body"),
    ]
    for canonical, real_path, body, desc in heavy_post_tools:
        ep = EndpointResult("POST", canonical)
        r = _post(client, real_path, json_body=body, timeout=15)
        # poc-plan with bad meeting id → 404 (cheap pre-LLM check). Others → 422.
        expected = [404] if "poc-plan" in canonical else [422]
        label = "missing" if "poc-plan" in canonical else "invalid"
        _record(ep.cases, label, "POST", canonical, expected, r.status_code, _short_note(r) + " | " + desc)
        wm = _get(client, real_path, timeout=10)
        _record(ep.cases, "wrong-method", "GET", canonical, [405], wm.status_code)
        _check_cors(client, ep.cases, "POST", canonical)
        skip_count += 1  # happy path skipped (Anthropic credits)
        endpoints.append(ep)

    # cost-calc (pure compute - safe to invoke happy path)
    ep = EndpointResult("POST", "/tools/cost-calc")
    r = _post(client, "/tools/cost-calc",
              json_body={"ingest_gb_day": 50, "retention_months": 12,
                         "current_spend_annual_usd": 1_000_000}, timeout=15)
    _record(ep.cases, "happy", "POST", "/tools/cost-calc", [200], r.status_code, _short_note(r))
    r2 = _post(client, "/tools/cost-calc", json_body={}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/tools/cost-calc", [422], r2.status_code, "empty body")
    r3 = _post(client, "/tools/cost-calc",
               json_body={"ingest_gb_day": -5, "retention_months": 12}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/tools/cost-calc", [422], r3.status_code, "negative ingest")
    wm = _get(client, "/tools/cost-calc", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/tools/cost-calc", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/tools/cost-calc")
    endpoints.append(ep)

    # capacity (pure compute)
    ep = EndpointResult("POST", "/tools/capacity")
    r = _post(client, "/tools/capacity",
              json_body={"peak_indexing_eps": 10000, "hot_data_gb": 1000, "warm_data_gb": 500},
              timeout=15)
    _record(ep.cases, "happy", "POST", "/tools/capacity", [200], r.status_code, _short_note(r))
    r2 = _post(client, "/tools/capacity", json_body={}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/tools/capacity", [422], r2.status_code, "empty body")
    wm = _get(client, "/tools/capacity", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/tools/capacity", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/tools/capacity")
    endpoints.append(ep)

    # knowledge-search (real call, but light)
    ep = EndpointResult("POST", "/tools/knowledge-search")
    r = _post(client, "/tools/knowledge-search",
              json_body={"query": "ELSER", "top_k": 2}, timeout=120)
    _record(ep.cases, "happy", "POST", "/tools/knowledge-search", [200], r.status_code, _short_note(r))
    r2 = _post(client, "/tools/knowledge-search", json_body={}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/tools/knowledge-search", [422], r2.status_code, "empty body")
    r3 = _post(client, "/tools/knowledge-search", json_body={"query": "x"}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/tools/knowledge-search", [422], r3.status_code, "query too short")
    wm = _get(client, "/tools/knowledge-search", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/tools/knowledge-search", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/tools/knowledge-search")
    endpoints.append(ep)

    # knowledge-search/health (GET)
    ep = EndpointResult("GET", "/tools/knowledge-search/health")
    r = _get(client, "/tools/knowledge-search/health", timeout=15)
    _record(ep.cases, "happy", "GET", "/tools/knowledge-search/health", [200], r.status_code, _short_note(r))
    wm = _post(client, "/tools/knowledge-search/health", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/tools/knowledge-search/health", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/tools/knowledge-search/health")
    endpoints.append(ep)

    # ---------- routes_agent_builder ----------
    ep = EndpointResult("GET", "/agent-builder/status")
    r = _get(client, "/agent-builder/status", timeout=10)
    _record(ep.cases, "happy", "GET", "/agent-builder/status", [200], r.status_code, _short_note(r))
    wm = _post(client, "/agent-builder/status", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/agent-builder/status", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/agent-builder/status")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/agent-builder/tools")
    r = _get(client, "/agent-builder/tools", timeout=15)
    _record(ep.cases, "happy", "GET", "/agent-builder/tools", [200], r.status_code, _short_note(r))
    wm = _post(client, "/agent-builder/tools", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/agent-builder/tools", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/agent-builder/tools")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/agent-builder/agents")
    r = _get(client, "/agent-builder/agents", timeout=15)
    _record(ep.cases, "happy", "GET", "/agent-builder/agents", [200], r.status_code, _short_note(r))
    wm = _post(client, "/agent-builder/agents", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/agent-builder/agents", [405, 422], wm.status_code,
            "POST exists with required body so an empty body is 422; either is acceptable")
    _check_cors(client, ep.cases, "GET", "/agent-builder/agents")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/agent-builder/agents/{agent_id}")
    # Bad id format → 422. Live mode required for actual lookup.
    r_bad_format = _get(client, "/agent-builder/agents/!!", timeout=10)
    _record(ep.cases, "invalid", "GET", "/agent-builder/agents/{agent_id}",
            [422], r_bad_format.status_code, "bad id format")
    r_missing = _get(client, f"/agent-builder/agents/{bad_id}", timeout=15)
    # Either 404 (agent missing in live mode) or 409 (Agent Builder offline).
    _record(ep.cases, "missing", "GET", "/agent-builder/agents/{agent_id}",
            [404, 409], r_missing.status_code, _short_note(r_missing))
    _check_cors(client, ep.cases, "GET", "/agent-builder/agents/{agent_id}")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/agent-builder/agents")
    r1 = _post(client, "/agent-builder/agents", json_body={}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/agent-builder/agents", [422], r1.status_code, "empty body")
    r2 = _post(client, "/agent-builder/agents",
               json_body={"name": "X", "slug": "no", "description": "Too short", "system_prompt": "s",
                          "tool_ids": []}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/agent-builder/agents", [422], r2.status_code, "fields too short")
    wm = _put(client, "/agent-builder/agents", timeout=10)
    _record(ep.cases, "wrong-method", "PUT", "/agent-builder/agents", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/agent-builder/agents")
    endpoints.append(ep)

    ep = EndpointResult("DELETE", "/agent-builder/agents/{agent_id}")
    # Bad id format → 422. Master agent → 403. Random user agent → 404 or 409.
    r_fmt = _delete(client, "/agent-builder/agents/!!", timeout=10)
    _record(ep.cases, "invalid", "DELETE", "/agent-builder/agents/{agent_id}",
            [422], r_fmt.status_code, "bad id format")
    r_master = _delete(client, "/agent-builder/agents/fec_field_assistant", timeout=10)
    _record(ep.cases, "wrong-method", "DELETE", "/agent-builder/agents/fec_field_assistant",
            [403], r_master.status_code, "master is reserved")
    r_missing = _delete(client, f"/agent-builder/agents/fec_user_{bad_id}", timeout=15)
    _record(ep.cases, "missing", "DELETE", "/agent-builder/agents/{agent_id}",
            [404, 409], r_missing.status_code, _short_note(r_missing))
    _check_cors(client, ep.cases, "DELETE", "/agent-builder/agents/{agent_id}")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/agent-builder/converse")
    r1 = _post(client, "/agent-builder/converse", json_body={}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/agent-builder/converse", [422], r1.status_code, "empty body")
    r2 = _post(client, "/agent-builder/converse",
               json_body={"message": ""}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/agent-builder/converse", [422], r2.status_code, "empty message")
    wm = _get(client, "/agent-builder/converse", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/agent-builder/converse", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/agent-builder/converse")
    endpoints.append(ep)

    # ---------- routes_mcp ----------
    ep = EndpointResult("POST", "/mcp")
    r = _post(client, "/mcp",
              json_body={"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, timeout=15)
    _record(ep.cases, "happy", "POST", "/mcp", [200], r.status_code, _short_note(r))
    r_bad = client.post(API + "/mcp", content="not-json",
                        headers={"Content-Type": "application/json"}, timeout=10)
    _record(ep.cases, "invalid", "POST", "/mcp", [400], r_bad.status_code, "non-JSON body")
    wm = _get(client, "/mcp", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/mcp", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/mcp")
    skip_count += 1  # tools/call SKIPPED to avoid Anthropic credit usage on heavy tools
    endpoints.append(ep)

    # ---------- routes_kibana ----------
    ep = EndpointResult("POST", "/kibana/dashboard/{meeting_id}")
    r = _post(client, f"/kibana/dashboard/{bad_id}", json_body={}, timeout=15)
    # 404 (meeting missing) or 409 (KIBANA_API_KEY missing) or 502 (Kibana unreachable).
    _record(ep.cases, "missing", "POST", "/kibana/dashboard/{meeting_id}",
            [404, 409, 502], r.status_code, _short_note(r))
    wm = _get(client, f"/kibana/dashboard/{bad_id}", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/kibana/dashboard/{meeting_id}", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/kibana/dashboard/{meeting_id}")
    endpoints.append(ep)

    # ---------- routes_demo_data ----------
    ep = EndpointResult("GET", "/demo-data/scenarios")
    r = _get(client, "/demo-data/scenarios", timeout=10)
    _record(ep.cases, "happy", "GET", "/demo-data/scenarios", [200], r.status_code, _short_note(r))
    wm = _post(client, "/demo-data/scenarios", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/demo-data/scenarios", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/demo-data/scenarios")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/demo-data/{scenario_id}/seed")
    # Avoid happy path (would re-seed Elastic). Probe missing scenario instead - cheap.
    r = _post(client, f"/demo-data/{bad_id}/seed", json_body={}, timeout=15)
    _record(ep.cases, "missing", "POST", "/demo-data/{scenario_id}/seed",
            [404], r.status_code, _short_note(r))
    wm = _get(client, f"/demo-data/{ids['scenario_id']}/seed", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/demo-data/{scenario_id}/seed", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/demo-data/{scenario_id}/seed")
    endpoints.append(ep)

    # ---------- routes_workflows ----------
    ep = EndpointResult("GET", "/workflows/status")
    r = _get(client, "/workflows/status", timeout=15)
    _record(ep.cases, "happy", "GET", "/workflows/status", [200], r.status_code, _short_note(r))
    wm = client.put(API + "/workflows/status", timeout=10)
    _record(ep.cases, "wrong-method", "PUT", "/workflows/status", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/workflows/status")
    endpoints.append(ep)

    # /workflows/sync POST is destructive (creates Kibana objects) - probe with GET to assert wrong-method 405.
    ep = EndpointResult("POST", "/workflows/sync")
    wm_get = _get(client, "/workflows/sync", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/workflows/sync", [405], wm_get.status_code)
    _check_cors(client, ep.cases, "POST", "/workflows/sync")
    skip_count += 1  # happy POST skipped (would mutate Kibana)
    endpoints.append(ep)

    ep = EndpointResult("DELETE", "/workflows/sync")
    # Avoid actual delete; just check wrong method on a GET is 405.
    wm = _get(client, "/workflows/sync", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/workflows/sync", [405], wm.status_code)
    _check_cors(client, ep.cases, "DELETE", "/workflows/sync")
    skip_count += 1
    endpoints.append(ep)

    ep = EndpointResult("POST", "/workflows/triggered")
    r = _post(client, "/workflows/triggered",
              json_body={"alert_id": "smoke-test", "rule_id": "smoke-test",
                         "rule_name": "Smoke Test", "_smoke_test": True}, timeout=30)
    _record(ep.cases, "happy", "POST", "/workflows/triggered",
            [200, 202], r.status_code, _short_note(r))
    wm = _get(client, "/workflows/triggered", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/workflows/triggered", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/workflows/triggered")
    endpoints.append(ep)

    # demo-fire requires Elasticsearch; skip happy.
    ep = EndpointResult("POST", "/workflows/demo-fire")
    wm = _get(client, "/workflows/demo-fire", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/workflows/demo-fire", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/workflows/demo-fire")
    skip_count += 1
    endpoints.append(ep)

    ep = EndpointResult("GET", "/workflows/recent-fires")
    r = _get(client, "/workflows/recent-fires", timeout=10)
    _record(ep.cases, "happy", "GET", "/workflows/recent-fires", [200], r.status_code, _short_note(r))
    wm = _post(client, "/workflows/recent-fires", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/workflows/recent-fires", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/workflows/recent-fires")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/workflows/post-meeting-action-orphan")
    r = _post(client, "/workflows/post-meeting-action-orphan",
              json_body={"alert_id": "smoke", "rule_id": "smoke", "rule_name": "Smoke"}, timeout=30)
    _record(ep.cases, "happy", "POST", "/workflows/post-meeting-action-orphan",
            [200], r.status_code, _short_note(r))
    wm = _get(client, "/workflows/post-meeting-action-orphan", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/workflows/post-meeting-action-orphan", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/workflows/post-meeting-action-orphan")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/workflows/orphan-demo-fire")
    wm = _get(client, "/workflows/orphan-demo-fire", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/workflows/orphan-demo-fire", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/workflows/orphan-demo-fire")
    skip_count += 1  # mutates ES
    endpoints.append(ep)

    ep = EndpointResult("POST", "/workflows/renewal-at-risk")
    r = _post(client, "/workflows/renewal-at-risk",
              json_body={"account_id": "smoke", "signals": []}, timeout=30)
    _record(ep.cases, "happy", "POST", "/workflows/renewal-at-risk",
            [200], r.status_code, _short_note(r))
    wm = _get(client, "/workflows/renewal-at-risk", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/workflows/renewal-at-risk", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/workflows/renewal-at-risk")
    endpoints.append(ep)

    ep = EndpointResult("POST", "/workflows/renewal-demo-fire")
    wm = _get(client, "/workflows/renewal-demo-fire", timeout=10)
    _record(ep.cases, "wrong-method", "GET", "/workflows/renewal-demo-fire", [405], wm.status_code)
    _check_cors(client, ep.cases, "POST", "/workflows/renewal-demo-fire")
    skip_count += 1  # mutates ES
    endpoints.append(ep)

    ep = EndpointResult("GET", "/workflows/sfdc-auto-tasks")
    r = _get(client, "/workflows/sfdc-auto-tasks", timeout=10)
    _record(ep.cases, "happy", "GET", "/workflows/sfdc-auto-tasks", [200], r.status_code, _short_note(r))
    wm = _post(client, "/workflows/sfdc-auto-tasks", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/workflows/sfdc-auto-tasks", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/workflows/sfdc-auto-tasks")
    endpoints.append(ep)

    # ---------- routes_industries ----------
    ep = EndpointResult("GET", "/industries")
    r = _get(client, "/industries", timeout=10)
    _record(ep.cases, "happy", "GET", "/industries", [200], r.status_code, _short_note(r))
    wm = _post(client, "/industries", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/industries", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/industries")
    endpoints.append(ep)

    ep = EndpointResult("GET", "/industries/{industry_id}")
    r = _get(client, f"/industries/{ids['industry_id']}", timeout=10)
    _record(ep.cases, "happy", "GET", "/industries/{industry_id}", [200], r.status_code, _short_note(r))
    r2 = _get(client, f"/industries/{bad_id}", timeout=10)
    _record(ep.cases, "missing", "GET", "/industries/{industry_id}", [404], r2.status_code)
    _check_cors(client, ep.cases, "GET", "/industries/{industry_id}")
    endpoints.append(ep)

    # ---------- routes_stats ----------
    ep = EndpointResult("GET", "/stats/savings")
    r = _get(client, "/stats/savings", timeout=10)
    _record(ep.cases, "happy", "GET", "/stats/savings", [200], r.status_code, _short_note(r))
    wm = _post(client, "/stats/savings", json_body={}, timeout=10)
    _record(ep.cases, "wrong-method", "POST", "/stats/savings", [405], wm.status_code)
    _check_cors(client, ep.cases, "GET", "/stats/savings")
    endpoints.append(ep)

    # tally violations
    for e in endpoints:
        for c in e.cases:
            if not c.pass_:
                violation_count += 1
    return endpoints, skip_count, violation_count


# ---------------------------------------------------------------- main + reporting

REPORT_PATH = REPO_ROOT / "docs" / "qa-w25b-api-contracts.md"


def _emit_table(endpoints: List[EndpointResult]) -> None:
    print("")
    print(f"{'#':>3}  {'METHOD':<7} {'PATH':<55} {'CASE':<14} {'EXPECTED':<25} {'OBSERVED':>8}  STATUS")
    print("-" * 130)
    idx = 0
    for ep in endpoints:
        for c in ep.cases:
            idx += 1
            mark = "PASS" if c.pass_ else "FAIL"
            print(f"{idx:>3}  {c.method:<7} {c.path[:55]:<55} {c.label:<14} "
                  f"{c.expected[:25]:<25} {c.observed:>8}  [{mark}]")


def _write_markdown(endpoints: List[EndpointResult], skip_count: int, violations: int,
                    runtime_s: float) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows: List[str] = []
    rows.append("# FE Copilot API Contract Tests (w25b)")
    rows.append("")
    rows.append(f"- Backend base: {BASE}")
    rows.append(f"- Endpoints exercised: {len(endpoints)}")
    rows.append(f"- Cases run: {sum(len(e.cases) for e in endpoints)}")
    rows.append(f"- Heavy endpoints SKIPPED (Anthropic credits / mutating cluster state): {skip_count}")
    rows.append(f"- Contract violations: {violations}")
    rows.append(f"- Runtime: {runtime_s:.2f} s")
    rows.append("")
    rows.append("## Per-endpoint case results")
    rows.append("")
    rows.append("| # | Method | Path | Case | Expected | Observed | Pass | Note |")
    rows.append("| ---: | --- | --- | --- | --- | ---: | --- | --- |")
    idx = 0
    for ep in endpoints:
        for c in ep.cases:
            idx += 1
            note = (c.note or "").replace("|", "\\|").replace("\n", " ")[:160]
            rows.append(
                f"| {idx} | {c.method} | `{c.path}` | {c.label} | {c.expected} | {c.observed} | "
                f"{'PASS' if c.pass_ else 'FAIL'} | {note} |"
            )
    rows.append("")
    rows.append("## Contract violations found")
    rows.append("")
    fails = [
        (ep, c) for ep in endpoints for c in ep.cases if not c.pass_
    ]
    if not fails:
        rows.append("None. All cases passed.")
    else:
        rows.append(f"Total: {len(fails)}.")
        rows.append("")
        for ep, c in fails:
            rows.append(
                f"- `{c.method} {c.path}` ({c.label}): expected {c.expected}, observed {c.observed}. "
                f"Note: {c.note}"
            )
    rows.append("")
    rows.append("## Notes on intentional deviations")
    rows.append("")
    rows.append(
        "- `GET /briefs/{meeting_id}` and `GET /briefs/{meeting_id}/post` return 200 with "
        "`{exists: false}` when missing. Documented behaviour: keeps the dashboard from filling "
        "the browser console with expected misses for unrun briefs."
    )
    rows.append(
        "- `GET /salesforce/account/{company_id}` returns 200 with empty company info on missing ids. "
        "Salesforce mock is read-through and never 404s."
    )
    rows.append(
        "- Heavy LLM endpoints (`/agents/*`, `/tools/poc-plan`, `/tools/spl-to-esql`, "
        "`/tools/compliance-mapping`, `/tools/stack-extract`, `/tools/code-sample`, "
        "`/tools/troubleshoot`, `/tools/compare`, `/tools/orchestrator`, `/tools/proposal`) are "
        "exercised with structurally invalid payloads only, plus an OPTIONS preflight, plus a "
        "missing-resource probe where applicable. Happy paths are SKIPPED to avoid Anthropic credit "
        "usage."
    )
    rows.append(
        "- MCP `tools/call` is also SKIPPED because every tool call routes back through one of the "
        "heavy LLM endpoints above."
    )
    rows.append(
        "- `/workflows/sync` (POST + DELETE), `/workflows/demo-fire`, `/workflows/orphan-demo-fire`, "
        "`/workflows/renewal-demo-fire` are SKIPPED on happy path because they mutate the live "
        "Kibana cluster. Only wrong-method and CORS checks run."
    )
    rows.append("")
    rows.append("## Fixes applied during this pass")
    rows.append("")
    rows.append(
        "1. **Static frontend mount was eating 405s.** `backend/app/main.py` now installs an "
        "HTTP middleware that intercepts paths under `/api/v1/` and returns 405 with a proper "
        "`Allow` header when an API route matches the path with a different method. Without "
        "this, requests like `GET /api/v1/elasticsearch/reconnect` (POST-only) fell through to "
        "the `/` static mount and surfaced as 404, hiding the method-mismatch from "
        "API consumers."
    )
    rows.append(
        "2. **`/briefs/{meeting_id}` swallowed reserved keywords.** A `GET /briefs/reindex` "
        "matched the path parameter and returned 200 with `exists:false`, masking the fact "
        "that `/briefs/reindex` is POST-only. `routes_briefs.py` now reserves the `reindex` "
        "keyword in `get_brief` and raises `HTTPException(405)` with `Allow: POST` so the "
        "contract is honoured."
    )
    rows.append(
        "3. **CORS preflight stayed correct.** The new method-mismatch middleware skips OPTIONS "
        "explicitly so FastAPI's CORSMiddleware can answer preflight with the expected "
        "`Access-Control-Allow-*` headers."
    )
    rows.append("")
    REPORT_PATH.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> int:
    started = time.monotonic()
    print(f"FE Copilot API contract tests -- backend={BASE}", flush=True)
    with httpx.Client(verify=True, follow_redirects=False) as client:
        # Ensure backend is reachable.
        try:
            r = _get(client, "/health", timeout=5)
            if r.status_code != 200:
                print(f"backend health probe failed: status={r.status_code}", flush=True)
                return 2
        except Exception as exc:
            print(f"backend unreachable at {BASE}: {exc}", flush=True)
            return 2
        endpoints, skips, violations = run_contract_tests(client)
    runtime = time.monotonic() - started
    _emit_table(endpoints)
    print("")
    print(
        f"summary: endpoints={len(endpoints)} cases={sum(len(e.cases) for e in endpoints)} "
        f"skips={skips} violations={violations} runtime={runtime:.2f}s",
        flush=True,
    )
    _write_markdown(endpoints, skips, violations, runtime)
    print(f"report: {REPORT_PATH}", flush=True)
    return 0 if violations == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
