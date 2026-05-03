"""
filename: seed_black_friday.py
description: Standalone CLI to (re)seed the Black Friday Outage demo scenario into
the live Elastic Cloud cluster + Kibana. Idempotent: deletes existing indices and
the dashboard saved-object before recreating them.

Usage (from repo root):
    PYTHONPATH=backend .venv/bin/python -m scripts.seed_black_friday

date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import sys


def main() -> int:
    from app.services.scenarios import black_friday

    try:
        result = black_friday.seed()
    except Exception as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
