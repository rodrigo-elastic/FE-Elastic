"""
filename: seed_noisy_microservice.py
description: One-off CLI to seed the "Noisy Microservice (One Bad Apple)" demo scenario
into Elasticsearch + Kibana. Reads connection details from .env via app.config.

Usage (from project root):
    PYTHONPATH=backend .venv/bin/python -m scripts.seed_noisy_microservice

Optional teardown (deletes indices + dashboard saved-object):
    PYTHONPATH=backend .venv/bin/python -m scripts.seed_noisy_microservice teardown
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import sys


def _seed() -> int:
    from app.services.scenarios import noisy_microservice as scenario
    result = scenario.seed()
    print(json.dumps(result, indent=2, default=str))
    if result.get("dashboard_error"):
        print(f"WARNING: dashboard creation failed: {result['dashboard_error']}", file=sys.stderr)
    return 0


def _teardown() -> int:
    import httpx
    from app.config import settings
    from app.integrations.elasticsearch_client import get_client
    from app.services.scenarios import noisy_microservice as scenario

    es = get_client()
    out = {"deleted_indices": [], "deleted_dashboard": False}
    for idx in scenario.INDICES.values():
        es.indices.delete(index=idx, ignore_unavailable=True)
        out["deleted_indices"].append(idx)

    if settings.kibana_api_key:
        url = settings.kibana_url.rstrip("/") + f"/api/saved_objects/dashboard/{scenario.DASHBOARD_ID}"
        headers = {
            "Authorization": f"ApiKey {settings.kibana_api_key}",
            "kbn-xsrf": "fe-copilot",
        }
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.delete(url, headers=headers)
            out["deleted_dashboard"] = resp.status_code in (200, 404)
            out["status"] = resp.status_code
        except Exception as exc:
            out["dashboard_error"] = str(exc)
    print(json.dumps(out, indent=2, default=str))
    return 0


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("teardown", "delete", "destroy"):
        return _teardown()
    return _seed()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
