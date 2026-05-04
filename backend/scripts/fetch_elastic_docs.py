"""
filename: fetch_elastic_docs.py
description: Polite CLI fetcher for Elastic public docs. Reads
data/seed/knowledge_seed_urls.txt, downloads each page, chunks the HTML using
app.services.knowledge_corpus, and writes JSON Lines to runtime/knowledge/.
Idempotent: existing per-URL files are skipped unless --refresh is passed.
date: 03-05-2026
"""
from __future__ import annotations

__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple
from urllib.parse import urlparse

import httpx

# Resolve repo paths. The CLI invocation per the sprint runbook is:
#   PYTHONPATH=backend .venv/bin/python -m scripts.fetch_elastic_docs
# So __file__ = backend/scripts/fetch_elastic_docs.py and parents[2] = repo root.
HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
DEFAULT_SEED = REPO_ROOT / "data" / "seed" / "knowledge_seed_urls.txt"
DEFAULT_OUT = REPO_ROOT / "runtime" / "knowledge"

USER_AGENT = "FE Copilot Knowledge Ingester / 0.1"
REQUEST_TIMEOUT = 25.0
POLITE_SLEEP_SECS = 1.5
MAX_URLS = 50

# Make app.services importable when running as `python -m scripts.fetch_elastic_docs`
# with PYTHONPATH=backend, but also when launched with the repo root on sys.path.
_BACKEND = REPO_ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.knowledge_corpus import chunk_html_page, slugify  # noqa: E402


def load_seed_urls(seed_path: Path) -> List[str]:
    if not seed_path.exists():
        raise FileNotFoundError(f"Seed file not found: {seed_path}")
    urls: List[str] = []
    seen = set()
    for raw in seed_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line in seen:
            continue
        seen.add(line)
        urls.append(line)
        if len(urls) >= MAX_URLS:
            break
    return urls


def output_path_for(out_dir: Path, url: str) -> Path:
    parsed = urlparse(url)
    # Combine path slug and last segment so multiple pages from the same area
    # do not collide. Strip leading/trailing slashes.
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        slug = slugify(parsed.netloc)
    else:
        # Use the last 3 path components for readability without going overboard.
        slug = slugify("-".join(parts[-3:]))
    return out_dir / f"{slug}.jsonl"


def fetch_once(client: httpx.Client, url: str) -> Tuple[int, str]:
    resp = client.get(url)
    return resp.status_code, resp.text


def fetch_with_retry(
    client: httpx.Client, url: str, log_prefix: str = ""
) -> Tuple[int, str]:
    """Fetch a URL once, retrying once on 5xx or transient errors."""
    try:
        status, body = fetch_once(client, url)
    except (httpx.HTTPError, httpx.TimeoutException) as exc:
        print(f"{log_prefix}transient error on first try ({exc!r}); retrying once", flush=True)
        time.sleep(POLITE_SLEEP_SECS)
        try:
            status, body = fetch_once(client, url)
        except Exception as exc2:
            print(f"{log_prefix}second attempt failed: {exc2!r}", flush=True)
            return 0, ""
        return status, body

    if 500 <= status < 600:
        print(f"{log_prefix}HTTP {status}; retrying once", flush=True)
        time.sleep(POLITE_SLEEP_SECS)
        try:
            status, body = fetch_once(client, url)
        except Exception as exc:
            print(f"{log_prefix}retry raised: {exc!r}", flush=True)
            return 0, ""
    return status, body


def write_chunks(out_path: Path, chunks: list) -> int:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fh:
        for record in chunks:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    return len(chunks)


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fetch Elastic public docs and write chunked JSONL."
    )
    parser.add_argument(
        "--seed",
        type=Path,
        default=DEFAULT_SEED,
        help="Path to URL seed file (default: data/seed/knowledge_seed_urls.txt)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help="Output directory for JSONL files (default: runtime/knowledge)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch and overwrite even if a JSONL file already exists.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional cap on URLs to process this run (for debugging).",
    )
    args = parser.parse_args(argv)

    out_dir: Path = args.out
    out_dir.mkdir(parents=True, exist_ok=True)

    urls = load_seed_urls(args.seed)
    if args.limit:
        urls = urls[: args.limit]

    started = time.monotonic()
    print(f"fetch_elastic_docs: {len(urls)} URLs -> {out_dir}", flush=True)

    summary = {
        "ok": 0,
        "skipped_existing": 0,
        "skipped_4xx": 0,
        "errors_5xx": 0,
        "errors_other": 0,
        "total_chunks": 0,
    }
    error_log: List[Tuple[int, str]] = []

    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(
        headers=headers,
        follow_redirects=True,
        timeout=REQUEST_TIMEOUT,
        http2=False,
    ) as client:
        for i, url in enumerate(urls, start=1):
            prefix = f"[{i:>2}/{len(urls)}] "
            target = output_path_for(out_dir, url)
            if target.exists() and not args.refresh:
                print(f"{prefix}skip (already on disk): {target.name}", flush=True)
                summary["skipped_existing"] += 1
                continue

            print(f"{prefix}GET {url}", flush=True)
            status, body = fetch_with_retry(client, url, log_prefix=prefix)

            if status == 0:
                summary["errors_other"] += 1
                error_log.append((0, url))
            elif 400 <= status < 500:
                print(f"{prefix}HTTP {status}; skipping", flush=True)
                summary["skipped_4xx"] += 1
                error_log.append((status, url))
            elif status >= 500:
                print(f"{prefix}HTTP {status} after retry; giving up", flush=True)
                summary["errors_5xx"] += 1
                error_log.append((status, url))
            else:
                fetched_at = datetime.now(timezone.utc).isoformat()
                try:
                    chunks = chunk_html_page(body, url=url, fetched_at=fetched_at)
                except Exception as exc:
                    print(f"{prefix}chunking failed: {exc!r}", flush=True)
                    summary["errors_other"] += 1
                    error_log.append((-1, url))
                    chunks = []
                if chunks:
                    n = write_chunks(target, chunks)
                    print(f"{prefix}wrote {n} chunks -> {target.name}", flush=True)
                    summary["ok"] += 1
                    summary["total_chunks"] += n
                else:
                    print(f"{prefix}no chunks extracted; skipping write", flush=True)
                    summary["errors_other"] += 1
                    error_log.append((-2, url))

            # Be polite to elastic.co even if we hit cache or skipped: the
            # next call still goes through the same network path.
            time.sleep(POLITE_SLEEP_SECS)

    elapsed = time.monotonic() - started
    print("\nfetch_elastic_docs: done.", flush=True)
    print(json.dumps({**summary, "elapsed_seconds": round(elapsed, 1)}, indent=2))
    if error_log:
        print("errors:", flush=True)
        for code, url in error_log:
            print(f"  {code}\t{url}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
