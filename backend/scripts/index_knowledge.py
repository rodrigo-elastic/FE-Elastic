"""
filename: index_knowledge.py
description: Build the fec-knowledge Elasticsearch index with semantic_text + ELSER inference, then bulk-ingest the chunked Elastic public docs produced by Agent S3A in runtime/knowledge/*.jsonl.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

ROOT = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = ROOT / "runtime" / "knowledge"
INDEX_NAME = "fec-knowledge"

# Inference endpoint candidates we will try in order. Stack 9.3 ships with
# `.elser-2-elasticsearch` by default; older stacks expose `elser_model_2`
# or the cloud-hosted `.elser-2-elastic` variant.
ELSER_CANDIDATES: Tuple[str, ...] = (
    ".elser-2-elasticsearch",
    ".elser-2-elastic",
    "elser_model_2",
    ".elser_model_2",
)

# Polite chunking for ELSER (heavy inference cost per doc).
BULK_CHUNK_SIZE = 50

# How long we wait for S3A to produce knowledge files when none are present.
S3A_WAIT_RETRIES = 5
S3A_WAIT_SECONDS = 60

# After the bulk indexing completes we wait for ELSER to finish embedding the
# tail end of the queue. Limit total wait to a sane upper bound.
INFERENCE_POLL_SECONDS = 5
INFERENCE_POLL_MAX_SECONDS = 600


def _log(msg: str, **kv: Any) -> None:
    """Tiny structured logger to stderr so stdout stays parseable JSON."""
    extras = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"[index_knowledge] {msg} {extras}".rstrip(), file=sys.stderr, flush=True)


def discover_elser_endpoint(client: Elasticsearch) -> str:
    """Probe `_inference` to find a registered ELSER sparse_embedding endpoint."""
    try:
        res = client.perform_request("GET", "/_inference/_all").body
        endpoints = res.get("endpoints", []) or []
    except Exception as exc:
        _log("inference.list_failed", error=str(exc))
        endpoints = []

    available_ids = {ep.get("inference_id") for ep in endpoints}
    sparse_ids = [
        ep.get("inference_id")
        for ep in endpoints
        if ep.get("task_type") == "sparse_embedding"
    ]
    _log("inference.endpoints_discovered", sparse=",".join(sorted(filter(None, sparse_ids))) or "none")

    # Prefer documented candidates first.
    for candidate in ELSER_CANDIDATES:
        if candidate in available_ids:
            _log("inference.elser_selected", inference_id=candidate)
            return candidate

    # Fall back to the first sparse_embedding endpoint that mentions ELSER.
    for ep in endpoints:
        if ep.get("task_type") != "sparse_embedding":
            continue
        ep_id = ep.get("inference_id") or ""
        model = (ep.get("service_settings") or {}).get("model_id", "") or ""
        if "elser" in ep_id.lower() or "elser" in model.lower():
            _log("inference.elser_selected_by_fallback", inference_id=ep_id)
            return ep_id

    raise RuntimeError(
        "No ELSER inference endpoint found. Tried: "
        + ", ".join(ELSER_CANDIDATES)
        + ". Available sparse endpoints: "
        + (", ".join(sorted(filter(None, sparse_ids))) or "<none>")
    )


def wait_for_chunks() -> List[Path]:
    """Poll runtime/knowledge until S3A has produced at least one .jsonl. Fail loudly after retries."""
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, S3A_WAIT_RETRIES + 1):
        files = sorted(KNOWLEDGE_DIR.glob("*.jsonl"))
        if files:
            _log("chunks.found", attempt=attempt, files=len(files))
            return files
        _log("chunks.waiting_for_s3a", attempt=attempt, sleep_s=S3A_WAIT_SECONDS)
        if attempt < S3A_WAIT_RETRIES:
            time.sleep(S3A_WAIT_SECONDS)
    raise RuntimeError(
        f"runtime/knowledge is still empty after {S3A_WAIT_RETRIES} retries; "
        "Agent S3A has not produced any chunks. Aborting."
    )


def iter_chunks(files: Iterable[Path]) -> Iterable[Dict[str, Any]]:
    """Yield normalized chunk records from every .jsonl file."""
    for path in files:
        with path.open("r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = json.loads(raw)
                except json.JSONDecodeError as exc:
                    _log("chunks.skip_bad_line", file=path.name, line=lineno, error=str(exc))
                    continue
                normalized = _normalize(rec, source_file=path.name)
                if normalized is None:
                    continue
                yield normalized


def _normalize(rec: Dict[str, Any], source_file: str) -> Optional[Dict[str, Any]]:
    """Coerce a raw chunk record into the fec-knowledge document shape."""
    text = rec.get("text") or rec.get("content") or rec.get("body")
    if not text or not str(text).strip():
        return None
    text = str(text).strip()

    url = rec.get("url") or rec.get("source_url") or ""
    title = rec.get("title") or ""

    breadcrumbs = rec.get("breadcrumbs") or rec.get("crumbs") or []
    if isinstance(breadcrumbs, str):
        breadcrumbs = [b.strip() for b in breadcrumbs.split(">") if b.strip()]
    breadcrumbs = [str(b) for b in breadcrumbs if b]

    section_heading = ""
    section = rec.get("section")
    if isinstance(section, dict):
        section_heading = section.get("heading") or section.get("title") or ""
    elif isinstance(section, str):
        section_heading = section
    section_heading = str(rec.get("section_heading") or section_heading or "")

    chunk_obj = rec.get("chunk")
    chunk_index: Optional[int] = None
    if isinstance(chunk_obj, dict):
        chunk_index = chunk_obj.get("index")
    if chunk_index is None:
        chunk_index = rec.get("chunk_index")
    try:
        chunk_index = int(chunk_index) if chunk_index is not None else 0
    except (TypeError, ValueError):
        chunk_index = 0

    timestamp = rec.get("@timestamp") or datetime.now(timezone.utc).isoformat()

    doc_id = rec.get("id") or rec.get("_id")
    if not doc_id:
        # Stable id keyed on url + chunk index so reruns overwrite cleanly.
        doc_id = f"{url}#chunk-{chunk_index}" if url else f"{source_file}:{chunk_index}:{hash(text) & 0xFFFFFFFF}"

    return {
        "_id": doc_id,
        "@timestamp": timestamp,
        "url": url,
        "title": title,
        "breadcrumbs": breadcrumbs,
        "section": {"heading": section_heading},
        "chunk": {"index": chunk_index},
        "text": text,
        "text_semantic": text,
    }


def build_mapping(elser_endpoint: str) -> Dict[str, Any]:
    return {
        "settings": {
            "index": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                # Give ELSER inference some breathing room before timing out search.
                "default_pipeline": None,
            }
        },
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "url": {"type": "keyword"},
                "title": {
                    "type": "text",
                    "fields": {"keyword": {"type": "keyword", "ignore_above": 512}},
                },
                "breadcrumbs": {"type": "keyword"},
                "section": {
                    "properties": {"heading": {"type": "keyword"}}
                },
                "chunk": {
                    "properties": {"index": {"type": "integer"}}
                },
                "text": {"type": "text"},
                "text_semantic": {
                    "type": "semantic_text",
                    "inference_id": elser_endpoint,
                },
            }
        },
    }


def recreate_index(client: Elasticsearch, elser_endpoint: str) -> None:
    if client.indices.exists(index=INDEX_NAME):
        _log("index.delete_existing", index=INDEX_NAME)
        client.indices.delete(index=INDEX_NAME)
    body = build_mapping(elser_endpoint)
    _log("index.create", index=INDEX_NAME, inference_id=elser_endpoint)
    client.indices.create(index=INDEX_NAME, **body)


def bulk_index(client: Elasticsearch, docs: List[Dict[str, Any]]) -> Tuple[int, int]:
    """Bulk-index docs in chunks of BULK_CHUNK_SIZE. Returns (success, errors)."""
    total = len(docs)
    success_total = 0
    error_total = 0

    def actions(batch: List[Dict[str, Any]]):
        for d in batch:
            yield {
                "_op_type": "index",
                "_index": INDEX_NAME,
                "_id": d.pop("_id"),
                "_source": d,
            }

    for start in range(0, total, BULK_CHUNK_SIZE):
        end = min(start + BULK_CHUNK_SIZE, total)
        batch = [dict(d) for d in docs[start:end]]
        is_last = end >= total
        refresh = "wait_for" if is_last else False
        try:
            ok, errors = bulk(
                client,
                actions(batch),
                chunk_size=BULK_CHUNK_SIZE,
                request_timeout=180,
                refresh=refresh,
                raise_on_error=False,
                raise_on_exception=False,
            )
            success_total += ok
            if isinstance(errors, list):
                error_total += len(errors)
                for err in errors[:3]:
                    _log("bulk.error_sample", error=str(err)[:300])
            _log("bulk.batch", start=start, end=end, ok=ok, errors=len(errors) if isinstance(errors, list) else 0)
        except Exception as exc:
            error_total += len(batch)
            _log("bulk.batch_failed", start=start, end=end, error=str(exc))
        # Be polite between batches so ELSER inference can drain.
        if not is_last:
            time.sleep(0.5)
    return success_total, error_total


def wait_for_inference(client: Elasticsearch, expected_min: int) -> int:
    """Poll _count until docs are visible (inference completed). Returns final count."""
    deadline = time.monotonic() + INFERENCE_POLL_MAX_SECONDS
    last_count = 0
    while time.monotonic() < deadline:
        try:
            client.indices.refresh(index=INDEX_NAME)
            res = client.count(index=INDEX_NAME)
            count = res.get("count", 0) if isinstance(res, dict) else res.body.get("count", 0)
        except Exception as exc:
            _log("inference.count_failed", error=str(exc))
            count = 0
        last_count = count
        if count >= expected_min and count > 0:
            _log("inference.ready", count=count)
            return count
        _log("inference.waiting", count=count, expected=expected_min)
        time.sleep(INFERENCE_POLL_SECONDS)
    return last_count


def main() -> int:
    started = time.monotonic()
    sys.path.insert(0, str(ROOT / "backend"))
    from app.integrations.elasticsearch_client import get_client  # type: ignore

    client = get_client()
    if not client.ping():
        print(json.dumps({"error": "elasticsearch unreachable"}), file=sys.stdout)
        return 2

    files = wait_for_chunks()
    elser_endpoint = discover_elser_endpoint(client)
    recreate_index(client, elser_endpoint)

    docs = list(iter_chunks(files))
    if not docs:
        raise RuntimeError("Found .jsonl files but no usable chunk records (all empty or malformed).")
    _log("chunks.loaded", total=len(docs), files=len(files))

    success, errors = bulk_index(client, docs)
    final_count = wait_for_inference(client, expected_min=success)

    elapsed = round(time.monotonic() - started, 2)
    summary = {
        "index": INDEX_NAME,
        "elser_endpoint": elser_endpoint,
        "files": [p.name for p in files],
        "chunks_attempted": len(docs),
        "chunks_indexed": success,
        "errors": errors,
        "final_count": final_count,
        "elapsed_seconds": elapsed,
    }
    print(json.dumps(summary, indent=2))
    return 0 if errors == 0 and final_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
