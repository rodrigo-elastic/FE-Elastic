"""
filename: seed_supply_chain_attack.py
description: One-off CLI that runs the Supply Chain Attack (Dependency Confusion)
  demo-data scenario end-to-end:
  1. Deletes existing indices + dashboards for an idempotent re-seed.
  2. Recreates indices with ECS-aligned mappings.
  3. Bulk-ingests build / runtime / MITRE-alert telemetry.
  4. Creates the Kibana data view plus two dashboards:
     - [FE] Supply Chain Attack (Dependency Confusion)  (Field Engineer prep)
     - [Customer] Supply Chain Attack (Dependency Confusion)  (SOC / CISO view)
     Both share the same inline-data Vega panels; only the surrounding
     markdown narrative differs.

Usage from the project root:
    PYTHONPATH=backend .venv/bin/python -m scripts.seed_supply_chain_attack

date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import sys


def main(argv: list[str]) -> int:
    from app.services.scenarios import supply_chain_attack as sca

    try:
        result = sca.seed()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2),
              file=sys.stderr)
        return 1

    out = dict(result)
    if "samples" in out:
        out["samples"] = {
            idx: {k: v for k, v in doc.items()
                   if k in ("@timestamp", "event", "host", "service",
                             "package", "process", "destination", "user",
                             "threat", "rule", "labels", "message")}
            for idx, doc in out["samples"].items()
        }
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
