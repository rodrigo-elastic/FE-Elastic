"""
filename: probe_workflows.py
description: End-to-end probe for the FE Copilot Workflow integration. Imports the routes_workflows service functions directly (no HTTP, no FastAPI server restart) and exercises them against the live Kibana cluster: ensure inbox index, upsert webhook connector, upsert alerting rule, then optionally index a demo doc. Run with: PYTHONPATH=backend python -m scripts.probe_workflows [--fire].
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import sys

import httpx

from app.api import routes_workflows as wf
from app.config import settings


def main() -> int:
    print(f"[probe] kibana_url={settings.kibana_url}")
    print(f"[probe] webhook_url={wf._webhook_url()}")
    print(f"[probe] api_key_set={bool(settings.kibana_api_key)}")

    if not settings.kibana_api_key:
        print("[probe] KIBANA_API_KEY not configured; aborting", file=sys.stderr)
        return 1

    # 1. Ensure inbox index
    inbox_status = wf._ensure_inbox_index()
    print(f"[probe] inbox_index={wf.INBOX_INDEX} status={inbox_status}")

    # 2. Upsert connector + rule
    with httpx.Client(timeout=30.0) as client:
        connector = wf._upsert_connector(client)
        print(f"[probe] connector_id={connector['id']} name={connector.get('name')}")
        rule = wf._upsert_rule(client, connector["id"])
        print(f"[probe] rule_id={rule['id']} name={rule.get('name')}")

    # 3. Persist state
    state = {
        "connector_id": connector["id"],
        "connector_name": connector.get("name"),
        "rule_id": rule["id"],
        "rule_name": rule.get("name"),
        "webhook_url": wf._webhook_url(),
        "ngrok_url": wf._backend_base_url(),
    }
    wf._save_state(state)
    print(f"[probe] state saved -> {wf._state_path()}")

    # 4. Verify rule + connector are listed
    with httpx.Client(timeout=15.0) as client:
        r = client.get(wf._kbn_url(f"/api/alerting/rule/{rule['id']}"), headers=wf._kbn_headers())
        print(f"[probe] GET rule status={r.status_code}")
        r = client.get(
            wf._kbn_url(f"/api/actions/connector/{connector['id']}"), headers=wf._kbn_headers()
        )
        print(f"[probe] GET connector status={r.status_code}")

    # 5. Optional: index a demo doc
    if "--fire" in sys.argv:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo

        repo = get_es_repo()
        if not repo.available:
            print("[probe] ES not available; skipping fire", file=sys.stderr)
            return 1
        from datetime import datetime, timezone
        import uuid

        doc_id = f"probe-{uuid.uuid4().hex[:8]}"
        body = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "meeting_id": doc_id,
            "company_name": "Probe Co",
            "industry": "Tech",
            "size": "1000",
            "meeting_title": "Probe meeting",
            "transcript_source": "probe",
            "transcript_text": (
                "Speaker A: This is a probe transcript.\n"
                "Speaker B: We use Splunk and Datadog. Renewals due Q3. We need a TCO and a POV plan.\n"
            ),
            "language": "English",
            "submitted_by": "probe",
            "status": "pending",
        }
        repo._client.index(index=wf.INBOX_INDEX, id=doc_id, body=body, refresh="wait_for")
        print(f"[probe] indexed demo doc id={doc_id}")

    print("[probe] DONE")
    print(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
