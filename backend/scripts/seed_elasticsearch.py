"""
filename: seed_elasticsearch.py
description: Idempotently loads synthetic JSON fixtures into Elasticsearch indices using the mappings in data/seed/es_mappings.json.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DIR = ROOT / "data" / "synthetic"
MAPPINGS_PATH = ROOT / "data" / "seed" / "es_mappings.json"

INDICES = ("companies", "news", "meetings", "transcripts", "tickets")


def main() -> None:
    from app.integrations.elasticsearch_client import get_client
    from app.utils.logging import get_logger

    log = get_logger("seed_elasticsearch")
    client = get_client()

    if not client.ping():
        print("ERROR: Elasticsearch not reachable. Start docker-compose first.", file=sys.stderr)
        sys.exit(1)

    mappings = json.loads(MAPPINGS_PATH.read_text(encoding="utf-8"))
    counts = {}

    for name in INDICES:
        if client.indices.exists(index=name):
            client.indices.delete(index=name)
        client.indices.create(index=name, body=mappings.get(name, {}))
        path = SYNTHETIC_DIR / f"{name}.json"
        if not path.exists():
            log.warning("seed.skip", index=name, reason="missing fixture")
            continue
        docs = json.loads(path.read_text(encoding="utf-8"))
        for doc in docs:
            doc_id = doc.get("id") or doc.get("meeting_id") or None
            client.index(index=name, document=doc, id=doc_id)
        client.indices.refresh(index=name)
        counts[name] = len(docs)
        log.info("seed.indexed", index=name, count=len(docs))

    print(json.dumps({"indexed": counts}, indent=2))


if __name__ == "__main__":
    main()
