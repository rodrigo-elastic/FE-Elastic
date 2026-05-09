"""
filename: routes_workflow_settings.py
description: Workflow settings CRUD + two-way Kibana integration. Stores preferences (data sources, notification channels) on disk and in ES. Proxies Kibana rule enable/disable calls for the two-way sync.
date: 08-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/workflow-settings", tags=["workflow-settings"])

# ============================================================ Constants =============

SETTINGS_INDEX = "fec-workflow-settings"
SETTINGS_DOC_ID = "main"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "data_sources": {
        "es_briefs": True,
        "es_post_meetings": True,
        "es_audit": True,
        "es_transcript_inbox": True,
        "salesforce": True,
        "google_calendar": True,
        "sec_filings": True,
    },
    "notification_channels": {
        "slack": True,
        "email": False,
        "pre_meeting_brief": True,
        "post_meeting_brief": True,
        "orphan_action_alert": True,
        "meeting_summary": True,
    },
    "slack_channel": "#fe-copilot-briefs",
    "email_address": "",
    "rule_channels": {},
}


# ============================================================ Pydantic models =======


class WorkflowSettingsBody(BaseModel):
    data_sources: Optional[Dict[str, bool]] = None
    notification_channels: Optional[Dict[str, bool]] = None
    rule_channels: Optional[Dict[str, Dict[str, bool]]] = None
    slack_channel: Optional[str] = None
    email_address: Optional[str] = None


class NewRuleBody(BaseModel):
    template: str
    name: Optional[str] = None
    schedule: str = "1m"
    index: Optional[str] = None
    webhook_path: Optional[str] = None


# ============================================================ Storage helpers =======


def _settings_path() -> "Any":
    return settings.runtime_dir / "workflow_settings.json"


def _load_settings() -> Dict[str, Any]:
    path = _settings_path()
    data: Dict[str, Any] = {
        "data_sources": dict(DEFAULT_SETTINGS["data_sources"]),
        "notification_channels": dict(DEFAULT_SETTINGS["notification_channels"]),
        "slack_channel": DEFAULT_SETTINGS["slack_channel"],
        "email_address": DEFAULT_SETTINGS["email_address"],
        "rule_channels": {},
    }

    if path.exists():
        try:
            disk = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(disk.get("data_sources"), dict):
                data["data_sources"].update(disk["data_sources"])
            if isinstance(disk.get("notification_channels"), dict):
                data["notification_channels"].update(disk["notification_channels"])
            if isinstance(disk.get("rule_channels"), dict):
                data["rule_channels"].update(disk["rule_channels"])
            if "slack_channel" in disk:
                data["slack_channel"] = disk["slack_channel"]
            if "email_address" in disk:
                data["email_address"] = disk["email_address"]
            if "updated_at" in disk:
                data["updated_at"] = disk["updated_at"]
        except Exception as exc:
            log.warning("workflow_settings.load_disk_failed", error=str(exc))

    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo

        repo = get_es_repo()
        if repo.available:
            try:
                hit = repo._client.get(index=SETTINGS_INDEX, id=SETTINGS_DOC_ID)  # noqa: SLF001
                src = hit.get("_source", {})
                if isinstance(src.get("data_sources"), dict):
                    data["data_sources"].update(src["data_sources"])
                if isinstance(src.get("notification_channels"), dict):
                    data["notification_channels"].update(src["notification_channels"])
                if isinstance(src.get("rule_channels"), dict):
                    data["rule_channels"].update(src["rule_channels"])
                if "slack_channel" in src:
                    data["slack_channel"] = src["slack_channel"]
                if "email_address" in src:
                    data["email_address"] = src["email_address"]
                if "updated_at" in src:
                    data["updated_at"] = src["updated_at"]
            except Exception:
                pass
    except Exception as exc:
        log.warning("workflow_settings.load_es_failed", error=str(exc))

    return data


def _save_settings(data: Dict[str, Any]) -> None:
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    _settings_path().write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo

        repo = get_es_repo()
        if repo.available:
            repo._client.index(  # noqa: SLF001
                index=SETTINGS_INDEX,
                id=SETTINGS_DOC_ID,
                document=data,
            )
    except Exception as exc:
        log.warning("workflow_settings.save_es_failed", error=str(exc))


# ============================================================ Kibana helpers ========


def _kbn_url(path: str) -> str:
    return settings.kibana_url.rstrip("/") + path


def _kbn_headers() -> Dict[str, str]:
    return {
        "Authorization": f"ApiKey {settings.kibana_api_key}",
        "Content-Type": "application/json",
        "kbn-xsrf": "fe-copilot",
    }


# ============================================================ Endpoints =============


@router.get("")
def get_workflow_settings() -> Dict[str, Any]:
    """Return current workflow settings, merged from disk and ES."""
    return _load_settings()


@router.put("")
def put_workflow_settings(body: WorkflowSettingsBody) -> Dict[str, Any]:
    """Save workflow settings to disk and ES. Returns the saved settings."""
    current = _load_settings()

    if body.data_sources is not None:
        current["data_sources"].update(body.data_sources)
    if body.notification_channels is not None:
        current["notification_channels"].update(body.notification_channels)
    if body.rule_channels is not None:
        existing_rc = current.get("rule_channels", {})
        existing_rc.update(body.rule_channels)
        current["rule_channels"] = existing_rc
    if body.slack_channel is not None:
        current["slack_channel"] = body.slack_channel.strip()
    if body.email_address is not None:
        current["email_address"] = body.email_address.strip()

    current["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_settings(current)
    log.info("workflow_settings.saved", updated_at=current["updated_at"])

    # When email is toggled or the address changes, wire/unwire the Kibana email-webhook connector.
    email_enabled = current.get("notification_channels", {}).get("email", False)
    email_address = current.get("email_address", "").strip()
    email_changed = body.notification_channels is not None or body.email_address is not None
    if email_changed and settings.kibana_api_key and email_address:
        try:
            with httpx.Client(timeout=20.0) as client:
                email_c = _find_kibana_email_connector(client)
                if email_c:
                    sync_result = _sync_kibana_email_to_rules(
                        client, email_c["id"], email_address, email_enabled
                    )
                    sync_result["connector_name"] = email_c.get("name")
                    # Surface first error as a string so the frontend can display it.
                    if not sync_result.get("ok") and sync_result.get("errors"):
                        sync_result["error"] = sync_result["errors"][0].get("error", "rule update failed")
                else:
                    sync_result = {
                        "ok": False,
                        "error": "No .email connector found - elastic-cloud-email not available in this deployment.",
                    }
                current["_email_sync"] = sync_result
        except Exception as exc:
            log.warning("workflow_settings.email_sync_error", error=str(exc)[:200])
            current["_email_sync"] = {"ok": False, "error": str(exc)[:200]}

    return current


@router.post("/sync-email")
def sync_email_now() -> Dict[str, Any]:
    """Trigger an immediate email-action sync across all fe-copilot Kibana rules.

    Discovers the Kibana .email connector (elastic-cloud-email on Elastic Cloud),
    then applies the saved email address to every fe-copilot alerting rule.
    Call this after enabling email in settings or when rules are out of sync.
    """
    if not settings.kibana_api_key:
        raise HTTPException(status_code=409, detail="KIBANA_API_KEY not configured")

    current = _load_settings()
    email_address = current.get("email_address", "").strip()
    email_enabled = current.get("notification_channels", {}).get("email", False)

    if not email_address:
        raise HTTPException(status_code=400, detail="No email address saved in settings. Set it first.")

    try:
        with httpx.Client(timeout=20.0) as client:
            email_c = _find_kibana_email_connector(client)
            if not email_c:
                raise HTTPException(
                    status_code=502,
                    detail="No .email connector found in Kibana. The elastic-cloud-email connector should be available on Elastic Cloud.",
                )
            # Always add (enabled=True) when the user explicitly hits Sync.
            result = _sync_kibana_email_to_rules(client, email_c["id"], email_address, enabled=True)
            result["connector_name"] = email_c.get("name")
            result["email_address"] = email_address
            if not result.get("ok") and result.get("errors"):
                first_err = result["errors"][0].get("error", "unknown error")
                raise HTTPException(status_code=502, detail=first_err)
            return result
    except HTTPException:
        raise
    except Exception as exc:
        log.warning("workflow_settings.sync_email_failed", error=str(exc)[:200])
        raise HTTPException(status_code=502, detail=str(exc)[:400])


@router.get("/kibana-status")
def get_kibana_status() -> Dict[str, Any]:
    """Return live Kibana connectors and alerting rules tagged 'fe-copilot'."""
    if not settings.kibana_api_key:
        return {
            "ok": True,
            "kibana_configured": False,
            "connectors": [],
            "rules": [],
            "kibana_url": settings.kibana_url,
        }

    try:
        with httpx.Client(timeout=15.0) as client:
            connectors_resp = client.get(
                _kbn_url("/api/actions/connectors"),
                headers=_kbn_headers(),
            )
            connectors_resp.raise_for_status()
            connectors = connectors_resp.json()

            rules_resp = client.get(
                _kbn_url("/api/alerting/rules/_find"),
                headers=_kbn_headers(),
                params={"per_page": 100},
            )
            rules_resp.raise_for_status()
            all_rules = rules_resp.json().get("data", [])

        fe_copilot_rules = [r for r in all_rules if "fe-copilot" in (r.get("tags") or [])]

        return {
            "ok": True,
            "kibana_configured": True,
            "connectors": connectors,
            "rules": fe_copilot_rules,
            "kibana_url": settings.kibana_url,
        }
    except httpx.HTTPError as exc:
        log.warning("workflow_settings.kibana_status_failed", error=str(exc))
        return {
            "ok": False,
            "error": str(exc),
            "kibana_configured": True,
            "connectors": [],
            "rules": [],
        }


@router.post("/kibana-rule/{rule_id}/enable")
def enable_kibana_rule(rule_id: str) -> Dict[str, Any]:
    """Enable a Kibana alerting rule by id."""
    if not settings.kibana_api_key:
        raise HTTPException(status_code=409, detail="KIBANA_API_KEY not configured")

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                _kbn_url(f"/api/alerting/rule/{rule_id}/_enable"),
                headers=_kbn_headers(),
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log.warning("workflow_settings.rule_enable_failed", rule_id=rule_id, status=exc.response.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"Kibana {exc.response.status_code}: {exc.response.text[:400]}",
        )
    except httpx.HTTPError as exc:
        log.warning("workflow_settings.rule_enable_failed", rule_id=rule_id, error=str(exc))
        raise HTTPException(status_code=502, detail=f"Kibana request failed: {exc}")

    log.info("workflow_settings.rule_enabled", rule_id=rule_id)
    return {"ok": True, "rule_id": rule_id, "action": "enabled"}


@router.post("/kibana-rule/{rule_id}/disable")
def disable_kibana_rule(rule_id: str) -> Dict[str, Any]:
    """Disable a Kibana alerting rule by id."""
    if not settings.kibana_api_key:
        raise HTTPException(status_code=409, detail="KIBANA_API_KEY not configured")

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                _kbn_url(f"/api/alerting/rule/{rule_id}/_disable"),
                headers=_kbn_headers(),
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log.warning("workflow_settings.rule_disable_failed", rule_id=rule_id, status=exc.response.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"Kibana {exc.response.status_code}: {exc.response.text[:400]}",
        )
    except httpx.HTTPError as exc:
        log.warning("workflow_settings.rule_disable_failed", rule_id=rule_id, error=str(exc))
        raise HTTPException(status_code=502, detail=f"Kibana request failed: {exc}")

    log.info("workflow_settings.rule_disabled", rule_id=rule_id)
    return {"ok": True, "rule_id": rule_id, "action": "disabled"}


RULE_TEMPLATES: Dict[str, Any] = {
    "post_meeting": {
        "label": "Post-meeting auto-process",
        "desc": "Runs the Post-Meeting agent when a transcript lands in the inbox.",
        "default_name": "FE Copilot - Post-Meeting Workflow",
        "index": "fec-transcript-inbox",
        "time_field": "@timestamp",
        "webhook_path": "/api/v1/workflows/triggered",
        "tags": ["fe-copilot", "workflow", "post-meeting"],
    },
    "orphan_action": {
        "label": "Orphan action items",
        "desc": "Creates Salesforce tasks for high-impact actions with no assigned owner.",
        "default_name": "FE Copilot - Orphan Action Item Workflow",
        "index": "fec-post-meetings",
        "time_field": "generated_at",
        "webhook_path": "/api/v1/workflows/post-meeting-action-orphan",
        "tags": ["fe-copilot", "workflow", "orphan-action"],
    },
    "renewal_risk": {
        "label": "Renewal at risk",
        "desc": "Detects risk signals on an account and generates a retention play.",
        "default_name": "FE Copilot - Renewal at Risk",
        "index": "fec-post-meetings",
        "time_field": "generated_at",
        "webhook_path": "/api/v1/workflows/renewal-at-risk",
        "tags": ["fe-copilot", "workflow", "renewal"],
    },
    "pre_meeting": {
        "label": "Pre-meeting brief",
        "desc": "Sends a continuity brief to Slack 30 minutes before an upcoming meeting.",
        "default_name": "FE Copilot - Pre-Meeting Brief Scheduler",
        "index": "fec-calendar-events",
        "time_field": "@timestamp",
        "webhook_path": "/api/v1/agents/pre-meeting/scheduler/check-now",
        "tags": ["fe-copilot", "workflow", "pre-meeting"],
    },
    "custom": {
        "label": "Custom",
        "desc": "Watch any Elasticsearch index and call a custom webhook endpoint.",
        "default_name": "FE Copilot - Custom Rule",
        "index": "",
        "time_field": "@timestamp",
        "webhook_path": "",
        "tags": ["fe-copilot", "workflow", "custom"],
    },
}


def _find_or_create_connector(client: httpx.Client, webhook_path: str) -> str:
    """Return an existing .webhook connector id whose URL ends with webhook_path, or create one."""
    backend_base = settings.kibana_url.rstrip("/").replace(":5601", "").replace("kb.", "")
    full_url = f"{_backend_base_url()}{webhook_path}"

    resp = client.get(_kbn_url("/api/actions/connectors"), headers=_kbn_headers())
    resp.raise_for_status()
    for c in resp.json():
        if c.get("connector_type_id") == ".webhook":
            existing_url = (c.get("config") or {}).get("url", "")
            if existing_url.endswith(webhook_path):
                return c["id"]

    connector_name = f"FE Copilot - {webhook_path.split('/')[-1].replace('-', ' ').title()}"
    body = {
        "name": connector_name,
        "connector_type_id": ".webhook",
        "config": {
            "url": full_url,
            "method": "post",
            "hasAuth": False,
            "headers": {"Content-Type": "application/json"},
        },
        "secrets": {},
    }
    r = client.post(_kbn_url("/api/actions/connector"), headers=_kbn_headers(), json=body)
    r.raise_for_status()
    return r.json()["id"]


def _backend_base_url() -> str:
    import os
    return os.environ.get("BACKEND_BASE_URL", "https://fe-c85291a2a8b144188ee6be1078e79a95.ecs.us-east-1.on.aws").rstrip("/")


@router.get("/rule-templates")
def get_rule_templates() -> Dict[str, Any]:
    """Return the available rule templates for the Add Rule form."""
    return {
        "templates": [
            {"id": k, "label": v["label"], "desc": v["desc"], "default_name": v["default_name"], "index": v["index"]}
            for k, v in RULE_TEMPLATES.items()
        ]
    }


@router.post("/rules")
def create_rule(body: NewRuleBody) -> Dict[str, Any]:
    """Create a new Kibana alerting rule from a template."""
    if not settings.kibana_api_key:
        raise HTTPException(status_code=409, detail="KIBANA_API_KEY not configured")

    tmpl = RULE_TEMPLATES.get(body.template)
    if not tmpl:
        raise HTTPException(status_code=400, detail=f"Unknown template: {body.template}. Valid: {list(RULE_TEMPLATES)}")

    rule_name = (body.name or "").strip() or tmpl["default_name"]
    index = (body.index or "").strip() or tmpl["index"]
    webhook_path = (body.webhook_path or "").strip() or tmpl["webhook_path"]

    if not index:
        raise HTTPException(status_code=400, detail="index is required for custom rules")
    if not webhook_path:
        raise HTTPException(status_code=400, detail="webhook_path is required for custom rules")

    webhook_body = {
        "alert_id": "{{alert.id}}",
        "rule_id": "{{rule.id}}",
        "rule_name": "{{rule.name}}",
        "date": "{{date}}",
        "index": index,
        "hits": "{{context.hits}}",
    }
    rule_payload: Dict[str, Any] = {
        "name": rule_name,
        "rule_type_id": ".es-query",
        "consumer": "alerts",
        "schedule": {"interval": body.schedule},
        "tags": tmpl.get("tags", ["fe-copilot", "workflow"]),
        "params": {
            "searchType": "esQuery",
            "esQuery": json.dumps({"query": {"match_all": {}}}),
            "index": [index],
            "timeField": tmpl.get("time_field", "@timestamp"),
            "timeWindowSize": 1,
            "timeWindowUnit": "m",
            "threshold": [0],
            "thresholdComparator": ">",
            "size": 10,
            "aggType": "count",
            "groupBy": "all",
            "excludeHitsFromPreviousRun": True,
        },
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            connector_id = _find_or_create_connector(client, webhook_path)
            rule_payload["actions"] = [
                {
                    "group": "query matched",
                    "id": connector_id,
                    "params": {"body": json.dumps(webhook_body)},
                    "frequency": {"summary": False, "notify_when": "onActiveAlert", "throttle": None},
                }
            ]
            resp = client.post(_kbn_url("/api/alerting/rule"), headers=_kbn_headers(), json=rule_payload)
            resp.raise_for_status()
            rule = resp.json()
    except httpx.HTTPStatusError as exc:
        log.warning("workflow_settings.create_rule_failed", status=exc.response.status_code, body=exc.response.text[:400])
        raise HTTPException(status_code=502, detail=f"Kibana {exc.response.status_code}: {exc.response.text[:400]}")
    except Exception as exc:
        log.warning("workflow_settings.create_rule_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=f"Rule creation failed: {exc}")

    log.info("workflow_settings.rule_created", rule_id=rule["id"], name=rule_name, template=body.template)
    return {"ok": True, "rule": rule}


@router.delete("/rules/{rule_id}")
def delete_rule(rule_id: str) -> Dict[str, Any]:
    """Delete a Kibana alerting rule by id."""
    if not settings.kibana_api_key:
        raise HTTPException(status_code=409, detail="KIBANA_API_KEY not configured")

    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.delete(_kbn_url(f"/api/alerting/rule/{rule_id}"), headers=_kbn_headers())
            if resp.status_code not in (200, 204):
                resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=502, detail=f"Kibana {exc.response.status_code}: {exc.response.text[:300]}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Delete failed: {exc}")

    log.info("workflow_settings.rule_deleted", rule_id=rule_id)
    return {"ok": True, "rule_id": rule_id, "action": "deleted"}


def _find_kibana_email_connector(client: httpx.Client) -> Optional[Dict[str, Any]]:
    """Return the first .email connector registered in Kibana (including preconfigured ones).

    On Elastic Cloud, the built-in 'elastic-cloud-email' connector is always available.
    No SMTP configuration or App Password needed - Kibana manages email delivery.
    """
    resp = client.get(_kbn_url("/api/actions/connectors"), headers=_kbn_headers())
    resp.raise_for_status()
    for c in resp.json():
        if c.get("connector_type_id") == ".email":
            log.info("workflow_settings.email_connector_found", connector_id=c["id"], name=c.get("name"))
            return c
    return None


def _build_put_actions(existing_actions: List[Dict[str, Any]], email_connector_id: str, email_address: str, enabled: bool) -> List[Dict[str, Any]]:
    """Build the actions list for a rule PUT, preserving connector_type_id on all existing actions.

    The Kibana PUT /api/alerting/rule/{id} endpoint requires connector_type_id on
    every action in the body, even though GET responses include it. Strip the email
    action first so toggling or changing the address is idempotent.
    """
    # Keep all non-email actions, preserving their connector_type_id from the GET response.
    kept = [
        {
            "id": a["id"],
            "connector_type_id": a.get("connector_type_id", ""),
            "group": a.get("group", "query matched"),
            "params": a.get("params", {}),
            "frequency": a.get("frequency", {"summary": False, "notify_when": "onActiveAlert", "throttle": None}),
        }
        for a in existing_actions
        if a.get("id") != email_connector_id
    ]
    if enabled:
        kept.append({
            "id": email_connector_id,
            "connector_type_id": ".email",
            "group": "query matched",
            "params": {
                "to": [email_address],
                "subject": "FE Copilot: {{rule.name}}",
                "message": (
                    "Rule **{{rule.name}}** fired.\n\n"
                    "- Hits: {{context.value}}\n"
                    "- Conditions: {{context.conditions}}\n"
                    "- Time: {{context.date}}"
                ),
            },
            "frequency": {"summary": False, "notify_when": "onActionGroupChange", "throttle": None},
        })
    return kept


def _sync_kibana_email_to_rules(
    client: httpx.Client,
    connector_id: str,
    email_address: str,
    enabled: bool,
) -> Dict[str, Any]:
    """Wire/unwire the Kibana .email connector on every fe-copilot alerting rule.

    Uses the Kibana Alerting Rules API (GET _find + PUT rule/{id}).
    The email connector is the Elastic Cloud built-in 'elastic-cloud-email' -
    no SMTP credentials or App Password needed.
    """
    try:
        rules_resp = client.get(
            _kbn_url("/api/alerting/rules/_find"),
            headers=_kbn_headers(),
            params={"per_page": 100},
        )
        rules_resp.raise_for_status()
        rules = [r for r in rules_resp.json().get("data", []) if "fe-copilot" in (r.get("tags") or [])]
    except Exception as exc:
        return {"ok": False, "error": f"Could not fetch rules: {exc}"}

    updated = []
    errors = []
    for rule in rules:
        rule_id = rule.get("id")
        if not rule_id:
            continue

        actions = _build_put_actions(rule.get("actions") or [], connector_id, email_address, enabled)
        put_body: Dict[str, Any] = {
            "name": rule.get("name", ""),
            "tags": rule.get("tags") or [],
            "schedule": rule.get("schedule") or {"interval": "1m"},
            "params": rule.get("params") or {},
            "actions": actions,
        }
        # Only include notify_when when the rule already uses it (not null).
        # When actions carry their own frequency, including notify_when causes a 400.
        if rule.get("notify_when"):
            put_body["notify_when"] = rule["notify_when"]
        if rule.get("throttle"):
            put_body["throttle"] = rule["throttle"]

        try:
            r = client.put(
                _kbn_url(f"/api/alerting/rule/{rule_id}"),
                headers=_kbn_headers(),
                json=put_body,
            )
            if not r.is_success:
                raise RuntimeError(f"Kibana {r.status_code}: {r.text[:300]}")
            updated.append(rule.get("name", rule_id))
            log.info("workflow_settings.email_synced", rule=rule.get("name"), enabled=enabled)
        except Exception as exc:
            err = str(exc)[:300]
            log.warning("workflow_settings.email_sync_failed", rule=rule.get("name"), error=err)
            errors.append({"rule": rule.get("name"), "error": err})

    ok = len(errors) == 0
    return {
        "ok": ok,
        "rules_updated": len(updated),
        "rules": updated,
        "connector_id": connector_id,
        "mode": "email",
        **({"errors": errors} if errors else {}),
    }


def _sync_watcher_email_watches(
    client: httpx.Client,
    email_address: str,
    enabled: bool,
) -> Dict[str, Any]:
    """Create or delete ES Watcher watches with native email actions.

    Uses Kibana's /api/watcher/watch proxy so the watches appear under
    Stack Management > Watcher with the email action in the standard format:
      "actions": { "send_email": { "email": { "to": [...], ... } } }

    Whether email is actually delivered depends on xpack.notification.email
    being configured on the Elasticsearch cluster. The watches are created
    regardless so they are visible in Kibana.
    """
    results: Dict[str, str] = {}
    for watch_id, cfg in _WATCHER_WATCHES.items():
        if not enabled:
            try:
                r = client.delete(_kbn_url(f"/api/watcher/watch/{watch_id}"), headers=_kbn_headers())
                results[watch_id] = "deleted" if r.status_code in (200, 204) else f"skip-{r.status_code}"
            except Exception as exc:
                results[watch_id] = f"delete_error: {str(exc)[:80]}"
            continue

        watch_def: Dict[str, Any] = {
            "watch": {
                "metadata": {"name": watch_id},
                "trigger": {"schedule": {"interval": "1m"}},
                "input": {
                    "search": {
                        "request": {
                            "indices": [cfg["index"]],
                            "body": {
                                "query": {
                                    "range": {cfg["time_field"]: {"gte": "now-1m"}}
                                }
                            },
                        }
                    }
                },
                "condition": {
                    "compare": {"ctx.payload.hits.total.value": {"gt": 0}}
                },
                "actions": {
                    "send_email": {
                        "email": {
                            "to": [email_address],
                            "subject": cfg["subject"],
                            "body": cfg["body"],
                        }
                    }
                },
            }
        }
        try:
            r = client.put(
                _kbn_url(f"/api/watcher/watch/{watch_id}"),
                headers=_kbn_headers(),
                json=watch_def,
            )
            r.raise_for_status()
            results[watch_id] = "synced"
            log.info("workflow_settings.watcher_synced", watch_id=watch_id, to=email_address)
        except Exception as exc:
            log.warning("workflow_settings.watcher_failed", watch_id=watch_id, error=str(exc)[:200])
            results[watch_id] = f"error: {str(exc)[:80]}"

    ok = all(v in ("synced", "deleted") for v in results.values())
    return {"ok": ok, "watches": results}


@router.get("/channels-status")
def get_channels_status() -> Dict[str, Any]:
    """Return the health/configuration status of each notification channel."""
    if settings.slack_webhook_url:
        slack_status: Dict[str, Any] = {"enabled": True, "mode": "live"}
    else:
        slack_status = {"enabled": False, "mode": "dry-run"}

    # Check Kibana for any .email connector (includes Elastic Cloud built-in).
    email_status: Dict[str, Any] = {"enabled": False}
    if settings.kibana_api_key:
        try:
            with httpx.Client(timeout=10.0) as client:
                ec = _find_kibana_email_connector(client)
            if ec:
                email_status = {
                    "enabled": True,
                    "mode": "email",
                    "connector_id": ec.get("id"),
                    "connector_name": ec.get("name"),
                }
        except Exception:
            pass

    if not email_status.get("enabled"):
        if getattr(settings, "notify_email", "") and getattr(settings, "smtp_user", ""):
            email_status = {"enabled": True, "mode": "smtp", "address": settings.notify_email}
        else:
            email_status = {"enabled": False, "needs_setup": True}

    return {"slack": slack_status, "email": email_status}
