"""
filename: seed_gdpr_audit.py
description: One-off CLI that runs the GDPR Audit Timeline demo-data scenario
  end-to-end:
  1. Deletes existing indices + dashboards for an idempotent re-seed.
  2. Recreates indices with ECS-aligned mappings.
  3. Bulk-ingests Aurora Banking access logs, retention violations, and the
     RTBF lifecycle.
  4. Creates the Kibana data view plus two dashboards:
     - [FE] GDPR Audit Timeline    (Field Engineer prep view)
     - [Customer] GDPR Audit Timeline  (DPO + exec audit pack)
     Both share the same inline-data Vega panels; only the surrounding
     markdown narrative differs.

Usage from the project root:
    PYTHONPATH=backend .venv/bin/python -m scripts.seed_gdpr_audit

date: 04-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import sys


def main(argv: list[str]) -> int:
    from app.services.scenarios import gdpr_audit as ga

    try:
        result = ga.seed()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    out = dict(result)
    if "samples" in out:
        out["samples"] = {
            idx: {
                k: v for k, v in doc.items()
                if k in ("@timestamp", "event", "user", "data", "compliance",
                         "rtbf", "case", "labels", "source")
            }
            for idx, doc in out["samples"].items()
        }
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
