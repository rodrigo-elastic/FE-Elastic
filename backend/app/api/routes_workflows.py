"""
filename: routes_workflows.py
description: FE Copilot Workflow integration. Wires the Kibana-side automation that fires when a new transcript document lands in the Elasticsearch index `fec-transcript-inbox`. The workflow is implemented as a Kibana Alerting Rule (.es-query type) with a .webhook connector that calls back into this backend, which then invokes the post-meeting agent (Salesforce + Slack writes happen inside the agent). End-to-end: doc -> alerting rule -> webhook -> post-meeting agent -> SFDC + Slack mocks.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.agents.post_meeting import PostMeetingAgent
from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/workflows", tags=["workflows"])

# ============================================================ Constants =============

INBOX_INDEX = "fec-transcript-inbox"
CONNECTOR_NAME = "FE Copilot Workflow Webhook"
RULE_NAME = "FE Copilot - Post-Meeting Workflow"
RULE_TAGS = ["fe-copilot", "workflow", "post-meeting"]

DEFAULT_NGROK_URL = "https://headlamp-squatting-usable.ngrok-free.dev"

INBOX_MAPPING: Dict[str, Any] = {
    "mappings": {
        "properties": {
            "@timestamp": {"type": "date"},
            "meeting_id": {"type": "keyword"},
            "company_name": {"type": "keyword"},
            "company_id": {"type": "keyword"},
            "industry": {"type": "keyword"},
            "size": {"type": "keyword"},
            "meeting_title": {"type": "text"},
            "transcript_source": {"type": "keyword"},
            "transcript_text": {"type": "text"},
            "language": {"type": "keyword"},
            "submitted_by": {"type": "keyword"},
            "status": {"type": "keyword"},
        }
    }
}

_post_meeting_agent = PostMeetingAgent()


# ============================================================ Helpers ===============


def _backend_base_url() -> str:
    return os.environ.get("BACKEND_BASE_URL", DEFAULT_NGROK_URL).rstrip("/")


def _webhook_url() -> str:
    return _backend_base_url() + "/api/v1/workflows/triggered"


def _kbn_url(path: str) -> str:
    return settings.kibana_url.rstrip("/") + path


def _kbn_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {settings.kibana_api_key}",
        "Content-Type": "application/json",
        "kbn-xsrf": "fe-copilot",
    }


def _state_path() -> "os.PathLike":
    return settings.runtime_dir / "workflow_state.json"


def _fires_path() -> "os.PathLike":
    return settings.runtime_dir / "workflow_fires.jsonl"


def _load_state() -> Dict[str, Any]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    _state_path().write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _append_fire(record: Dict[str, Any]) -> None:
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    with open(_fires_path(), "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _read_recent_fires(limit: int = 5) -> List[Dict[str, Any]]:
    path = _fires_path()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return []
    out: List[Dict[str, Any]] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            continue
        if len(out) >= limit:
            break
    return out


# ============================================================ Kibana operations =====


def _find_connector(client: httpx.Client) -> Optional[Dict[str, Any]]:
    resp = client.get(_kbn_url("/api/actions/connectors"), headers=_kbn_headers())
    resp.raise_for_status()
    for c in resp.json():
        if c.get("connector_type_id") == ".webhook" and c.get("name") == CONNECTOR_NAME:
            return c
    return None


def _create_connector(client: httpx.Client) -> Dict[str, Any]:
    body = {
        "name": CONNECTOR_NAME,
        "connector_type_id": ".webhook",
        "config": {
            "url": _webhook_url(),
            "method": "post",
            "hasAuth": False,
            "headers": {"Content-Type": "application/json"},
        },
        "secrets": {},
    }
    resp = client.post(_kbn_url("/api/actions/connector"), headers=_kbn_headers(), json=body)
    resp.raise_for_status()
    return resp.json()


def _update_connector(client: httpx.Client, connector_id: str) -> Dict[str, Any]:
    body = {
        "name": CONNECTOR_NAME,
        "config": {
            "url": _webhook_url(),
            "method": "post",
            "hasAuth": False,
            "headers": {"Content-Type": "application/json"},
        },
        "secrets": {},
    }
    resp = client.put(
        _kbn_url(f"/api/actions/connector/{connector_id}"),
        headers=_kbn_headers(),
        json=body,
    )
    resp.raise_for_status()
    return resp.json()


def _upsert_connector(client: httpx.Client) -> Dict[str, Any]:
    existing = _find_connector(client)
    if existing:
        return _update_connector(client, existing["id"])
    return _create_connector(client)


def _find_rule(client: httpx.Client) -> Optional[Dict[str, Any]]:
    """Find our rule by name + tags."""
    resp = client.get(
        _kbn_url("/api/alerting/rules/_find"),
        headers=_kbn_headers(),
        params={"per_page": 100, "search": RULE_NAME, "search_fields": "name"},
    )
    resp.raise_for_status()
    for r in resp.json().get("data", []):
        if r.get("name") == RULE_NAME:
            return r
    return None


def _build_rule_body(connector_id: str) -> Dict[str, Any]:
    # The webhook body uses Mustache templates resolved by Kibana at fire time.
    # We pass enough context for the backend to look up the matched docs and run the agent.
    webhook_body = {
        "alert_id": "{{alert.id}}",
        "rule_id": "{{rule.id}}",
        "rule_name": "{{rule.name}}",
        "date": "{{date}}",
        "index": INBOX_INDEX,
        "hits": "{{context.hits}}",
        "value": "{{context.value}}",
        "conditions": "{{context.conditions}}",
    }
    return {
        "name": RULE_NAME,
        "rule_type_id": ".es-query",
        "consumer": "alerts",
        "schedule": {"interval": "1m"},
        "tags": RULE_TAGS,
        "params": {
            "searchType": "esQuery",
            "esQuery": json.dumps({"query": {"match_all": {}}}),
            "index": [INBOX_INDEX],
            "timeField": "@timestamp",
            "timeWindowSize": 1,
            "timeWindowUnit": "m",
            "threshold": [0],
            "thresholdComparator": ">",
            "size": 10,
            "aggType": "count",
            "groupBy": "all",
            "excludeHitsFromPreviousRun": True,
        },
        "actions": [
            {
                "group": "query matched",
                "id": connector_id,
                "params": {"body": json.dumps(webhook_body)},
                "frequency": {
                    "summary": False,
                    "notify_when": "onActiveAlert",
                    "throttle": None,
                },
            }
        ],
    }


def _create_rule(client: httpx.Client, connector_id: str) -> Dict[str, Any]:
    body = _build_rule_body(connector_id)
    resp = client.post(_kbn_url("/api/alerting/rule"), headers=_kbn_headers(), json=body)
    resp.raise_for_status()
    return resp.json()


def _update_rule(client: httpx.Client, rule_id: str, connector_id: str) -> Dict[str, Any]:
    """The PUT /api/alerting/rule/{id} endpoint accepts only a subset of fields."""
    body = _build_rule_body(connector_id)
    update_body = {
        "name": body["name"],
        "tags": body["tags"],
        "schedule": body["schedule"],
        "params": body["params"],
        "actions": body["actions"],
    }
    resp = client.put(
        _kbn_url(f"/api/alerting/rule/{rule_id}"),
        headers=_kbn_headers(),
        json=update_body,
    )
    resp.raise_for_status()
    return resp.json()


def _upsert_rule(client: httpx.Client, connector_id: str) -> Dict[str, Any]:
    existing = _find_rule(client)
    if existing:
        return _update_rule(client, existing["id"], connector_id)
    return _create_rule(client, connector_id)


def _ensure_inbox_index() -> str:
    """Create the fec-transcript-inbox index with the proper mapping if missing."""
    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo

        repo = get_es_repo()
        if not repo.available:
            return "es-unavailable"
        client = repo._client  # noqa: SLF001
        if client.indices.exists(index=INBOX_INDEX):
            return "exists"
        client.indices.create(index=INBOX_INDEX, body=INBOX_MAPPING)
        return "created"
    except Exception as exc:
        log.warning("workflows.inbox_create_failed", error=str(exc))
        return f"error: {exc}"


# ============================================================ Endpoints =============


@router.get("/status")
def workflow_status() -> Dict[str, Any]:
    """Return current registration state of the workflow (rule + connector ids, inbox status)."""
    state = _load_state()
    rule_id = state.get("rule_id")
    connector_id = state.get("connector_id")

    rule_status = "unknown"
    connector_status = "unknown"
    if settings.kibana_api_key:
        try:
            with httpx.Client(timeout=15.0) as client:
                if rule_id:
                    r = client.get(_kbn_url(f"/api/alerting/rule/{rule_id}"), headers=_kbn_headers())
                    rule_status = "registered" if r.status_code == 200 else f"missing ({r.status_code})"
                else:
                    rule_status = "not-registered"
                if connector_id:
                    r = client.get(
                        _kbn_url(f"/api/actions/connector/{connector_id}"), headers=_kbn_headers()
                    )
                    connector_status = "registered" if r.status_code == 200 else f"missing ({r.status_code})"
                else:
                    connector_status = "not-registered"
        except Exception as exc:
            rule_status = f"probe-error: {exc}"

    inbox_exists = False
    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo

        repo = get_es_repo()
        if repo.available:
            inbox_exists = bool(repo._client.indices.exists(index=INBOX_INDEX))  # noqa: SLF001
    except Exception:
        inbox_exists = False

    return {
        "ok": True,
        "registered": bool(rule_id and connector_id),
        "rule_id": rule_id,
        "connector_id": connector_id,
        "rule_status": rule_status,
        "connector_status": connector_status,
        "inbox_index": INBOX_INDEX,
        "inbox_exists": inbox_exists,
        "webhook_url": _webhook_url(),
        "ngrok_url": _backend_base_url(),
        "recent_fires": _read_recent_fires(5),
    }


@router.post("/sync")
def workflow_sync() -> Dict[str, Any]:
    """Idempotently create the inbox index, the .webhook connector, and the alerting rule."""
    if not settings.kibana_api_key:
        raise HTTPException(status_code=409, detail="KIBANA_API_KEY not configured")

    inbox_status = _ensure_inbox_index()

    try:
        with httpx.Client(timeout=30.0) as client:
            connector = _upsert_connector(client)
            rule = _upsert_rule(client, connector["id"])
    except httpx.HTTPStatusError as exc:
        log.warning("workflows.sync.http_error", status=exc.response.status_code, body=exc.response.text[:400])
        raise HTTPException(
            status_code=502, detail=f"Kibana {exc.response.status_code}: {exc.response.text[:400]}"
        )
    except Exception as exc:
        log.warning("workflows.sync.exception", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Kibana request failed: {exc}")

    state = {
        "connector_id": connector["id"],
        "connector_name": connector.get("name"),
        "rule_id": rule["id"],
        "rule_name": rule.get("name"),
        "webhook_url": _webhook_url(),
        "ngrok_url": _backend_base_url(),
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }
    _save_state(state)
    log.info("workflows.synced", rule_id=rule["id"], connector_id=connector["id"], inbox=inbox_status)
    return {
        "ok": True,
        "rule_id": rule["id"],
        "connector_id": connector["id"],
        "ngrok_url": _backend_base_url(),
        "webhook_url": _webhook_url(),
        "inbox_index": INBOX_INDEX,
        "inbox_status": inbox_status,
    }


@router.delete("/sync")
def workflow_teardown() -> Dict[str, Any]:
    """Tear down the rule + connector. Optionally drops the inbox index too."""
    if not settings.kibana_api_key:
        raise HTTPException(status_code=409, detail="KIBANA_API_KEY not configured")

    state = _load_state()
    rule_id = state.get("rule_id")
    connector_id = state.get("connector_id")

    deleted: Dict[str, Any] = {"rule": None, "connector": None, "index": None}
    try:
        with httpx.Client(timeout=30.0) as client:
            if rule_id:
                r = client.delete(_kbn_url(f"/api/alerting/rule/{rule_id}"), headers=_kbn_headers())
                deleted["rule"] = r.status_code
            if connector_id:
                r = client.delete(
                    _kbn_url(f"/api/actions/connector/{connector_id}"), headers=_kbn_headers()
                )
                deleted["connector"] = r.status_code
    except Exception as exc:
        log.warning("workflows.teardown.exception", error=str(exc))

    # Drop the inbox index too.
    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo

        repo = get_es_repo()
        if repo.available and repo._client.indices.exists(index=INBOX_INDEX):  # noqa: SLF001
            repo._client.indices.delete(index=INBOX_INDEX)  # noqa: SLF001
            deleted["index"] = "deleted"
        else:
            deleted["index"] = "missing"
    except Exception as exc:
        deleted["index"] = f"error: {exc}"

    if _state_path().exists():
        try:
            _state_path().unlink()
        except Exception:
            pass

    return {"ok": True, "deleted": deleted}


@router.post("/triggered")
async def workflow_triggered(request: Request) -> Dict[str, Any]:
    """Webhook target. Called by the Kibana alerting rule when transcripts land in the inbox.

    Looks up the most recent unprocessed inbox doc, runs the post-meeting agent on it,
    persists the Salesforce + Slack writes via the existing post-meeting flow.
    """
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    received_at = datetime.now(timezone.utc).isoformat()
    log.info("workflows.triggered", payload_keys=list(payload.keys()) if isinstance(payload, dict) else "n/a")

    # Find unprocessed transcript docs in the inbox; pick the most recent.
    docs: List[Dict[str, Any]] = []
    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo

        repo = get_es_repo()
        if repo.available and repo._client.indices.exists(index=INBOX_INDEX):  # noqa: SLF001
            search_body = {
                "size": 5,
                "sort": [{"@timestamp": {"order": "desc"}}],
                "query": {
                    "bool": {
                        "must_not": [{"term": {"status": "processed"}}],
                    }
                },
            }
            resp = repo._client.search(index=INBOX_INDEX, body=search_body)  # noqa: SLF001
            for hit in resp.get("hits", {}).get("hits", []):
                docs.append({"_id": hit["_id"], **hit.get("_source", {})})
    except Exception as exc:
        log.warning("workflows.triggered.search_failed", error=str(exc))

    fire_record: Dict[str, Any] = {
        "received_at": received_at,
        "alert_id": payload.get("alert_id") if isinstance(payload, dict) else None,
        "rule_id": payload.get("rule_id") if isinstance(payload, dict) else None,
        "rule_name": payload.get("rule_name") if isinstance(payload, dict) else None,
        "matched_docs": len(docs),
        "doc_ids": [d.get("_id") for d in docs],
    }

    if not docs:
        fire_record["processed"] = False
        fire_record["reason"] = "no-unprocessed-docs"
        _append_fire(fire_record)
        return {"ok": True, "processed_count": 0, "post_meeting_result": None, "reason": "no-unprocessed-docs"}

    # Process the most recent doc.
    target = docs[0]
    transcript_text = target.get("transcript_text") or ""
    if not transcript_text or len(transcript_text) < 20:
        fire_record["processed"] = False
        fire_record["reason"] = "transcript-too-short"
        _append_fire(fire_record)
        return {"ok": True, "processed_count": 0, "post_meeting_result": None, "reason": "transcript-too-short"}

    # Parse turns from the transcript text. Reuse the post-meeting ad_hoc path.
    from app.services import vtt_parser

    turns = vtt_parser.parse_vtt(transcript_text)
    if not turns:
        fire_record["processed"] = False
        fire_record["reason"] = "transcript-parse-failed"
        _append_fire(fire_record)
        return {"ok": True, "processed_count": 0, "post_meeting_result": None, "reason": "transcript-parse-failed"}

    try:
        post_result = await _post_meeting_agent.run_ad_hoc(
            {
                "company_name": target.get("company_name") or "Inbox Customer",
                "meeting_title": target.get("meeting_title") or "",
                "industry": target.get("industry") or "",
                "size": target.get("size") or "",
                "transcript_source": target.get("transcript_source") or "workflow-inbox",
                "turns": turns,
                "language": target.get("language") or "English",
            }
        )
    except Exception as exc:
        log.warning("workflows.triggered.post_meeting_failed", error=str(exc))
        fire_record["processed"] = False
        fire_record["reason"] = f"post-meeting-error: {exc}"
        _append_fire(fire_record)
        raise HTTPException(status_code=502, detail=f"post-meeting agent failed: {exc}")

    # Mark the inbox doc as processed.
    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo

        repo = get_es_repo()
        if repo.available:
            repo._client.update(  # noqa: SLF001
                index=INBOX_INDEX,
                id=target["_id"],
                body={
                    "doc": {
                        "status": "processed",
                        "processed_at": datetime.now(timezone.utc).isoformat(),
                        "post_meeting_id": post_result.get("meeting_id"),
                    }
                },
            )
    except Exception as exc:
        log.warning("workflows.triggered.mark_processed_failed", error=str(exc))

    fire_record["processed"] = True
    fire_record["post_meeting_id"] = post_result.get("meeting_id")
    fire_record["company_name"] = post_result.get("company_name")
    fire_record["action_items"] = len(post_result.get("action_items", []))
    fire_record["sfdc_tasks"] = len(post_result.get("salesforce_task_ids", []))
    _append_fire(fire_record)

    return {
        "ok": True,
        "processed_count": 1,
        "post_meeting_result": {
            "meeting_id": post_result.get("meeting_id"),
            "company_name": post_result.get("company_name"),
            "summary": post_result.get("summary"),
            "action_items_count": len(post_result.get("action_items", [])),
            "sfdc_task_ids": post_result.get("salesforce_task_ids", []),
            "salesforce_account": post_result.get("salesforce_account"),
        },
    }


@router.post("/demo-fire")
async def workflow_demo_fire() -> Dict[str, Any]:
    """Index a synthetic transcript document into fec-transcript-inbox to fire the workflow."""
    inbox_status = _ensure_inbox_index()

    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo

        repo = get_es_repo()
        if not repo.available:
            raise HTTPException(status_code=502, detail="Elasticsearch is not reachable")
        client = repo._client  # noqa: SLF001
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"ES client error: {exc}")

    doc_id = f"demo-{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc).isoformat()
    transcript_text = (
        "Marta Solis: Thanks for taking the call. Tell me about the observability stack today.\n"
        "Customer (Jordan Reyes): We run Splunk Enterprise on-prem plus Datadog for APM. Logs cost us about 1.4 million dollars a year.\n"
        "Marta Solis: What is the trigger for looking at Elastic now?\n"
        "Customer (Jordan Reyes): Renewals are due in Q3. The CFO told us to cut log spend by at least 30 percent. We also need DORA reporting by January.\n"
        "Marta Solis: Got it. If we showed Elastic Cloud at roughly 60 percent of your current cost with frozen tier and ECS-aligned audit, would that be enough to move forward?\n"
        "Customer (Jordan Reyes): Yes. I would need a four week proof of value with our security data. The success criterion is detection parity on our top ten Splunk searches and a TCO model the CFO can defend.\n"
        "Marta Solis: We can scope that. I will send a POV plan and a draft TCO by end of week.\n"
        "Customer (Jordan Reyes): Perfect. Loop in our security architect Priya Banerjee on the next call.\n"
    )
    body = {
        "@timestamp": now,
        "meeting_id": doc_id,
        "company_name": "Northwind Bank (workflow demo)",
        "company_id": f"workflow-{doc_id}",
        "industry": "Financial Services",
        "size": "5000+",
        "meeting_title": "Discovery - Splunk migration & DORA",
        "transcript_source": "workflow-demo",
        "transcript_text": transcript_text,
        "language": "English",
        "submitted_by": "demo-fire",
        "status": "pending",
    }
    try:
        client.index(index=INBOX_INDEX, id=doc_id, body=body, refresh="wait_for")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"index failed: {exc}")

    log.info("workflows.demo_fired", doc_id=doc_id, inbox_status=inbox_status)
    return {
        "ok": True,
        "doc_id": doc_id,
        "index": INBOX_INDEX,
        "inbox_status": inbox_status,
        "indexed_at": now,
        "note": "Kibana alerting rule polls every 60s; the webhook should fire within ~1 minute.",
    }


@router.get("/recent-fires")
def workflow_recent_fires(limit: int = 10) -> Dict[str, Any]:
    """Return the recent webhook fires log (for the UI)."""
    return {"ok": True, "fires": _read_recent_fires(max(1, min(50, limit)))}
