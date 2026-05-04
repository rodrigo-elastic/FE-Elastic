"""
filename: knowledge_corpus.py
description: Pure-Python helpers that turn raw fetched HTML chunks on disk into
clean, ECS-leaning records ready to bulk-index into Elasticsearch. Used by the
fetch script (writer side) and by the indexing agent (reader side).
date: 03-05-2026
"""
from __future__ import annotations

__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional

from bs4 import BeautifulSoup

# Rough heuristic: 1 token ~ 4 chars of English prose. Keeps us off the
# tokenizer dependency tree for ingestion. Good enough for chunk sizing.
CHARS_PER_TOKEN = 4
TARGET_TOKENS_PER_CHUNK = 800
TARGET_CHARS_PER_CHUNK = TARGET_TOKENS_PER_CHUNK * CHARS_PER_TOKEN  # 3200
CHUNK_OVERLAP_CHARS = 200

# Tags we never want in the extracted body even if they live inside <article>.
_NOISY_TAGS = (
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "button",
    "svg",
)

# Selectors that bracket the actual doc body on elastic.co. Probed empirically
# against /docs/ pages (May 2026).
_MAIN_SELECTORS = (
    "article",
    "main article",
    "main",
    "[role=main]",
    "#main-content",
)

_HEADING_TAGS = ("h1", "h2", "h3", "h4")


# ---------------------------------------------------------------------------
# Token + text helpers
# ---------------------------------------------------------------------------


def rough_token_count(text: str) -> int:
    """Approximate token count without pulling in a real tokenizer."""
    if not text:
        return 0
    return max(1, len(text) // CHARS_PER_TOKEN)


def normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace, normalize unicode, strip control chars."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    # Drop zero-width + control characters except tab/newline.
    text = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch >= " ")
    # Collapse repeated blank lines but keep paragraph boundaries.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def slugify(value: str) -> str:
    """URL- and filesystem-safe slug. Used to name JSONL output files."""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "page"


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------


def _select_main(soup: BeautifulSoup):
    for sel in _MAIN_SELECTORS:
        node = soup.select_one(sel)
        if node is not None:
            return node
    return soup.body or soup


def _strip_noise(node) -> None:
    for tag in node.find_all(_NOISY_TAGS):
        tag.decompose()
    # Drop edit-on-github, "report issue", and image-only blocks that bloat chunks.
    for a in node.find_all("a"):
        href = (a.get("href") or "").lower()
        if "github.com" in href and ("edit" in href or "issue" in href):
            a.decompose()


def extract_breadcrumbs(soup: BeautifulSoup) -> List[str]:
    """Best-effort breadcrumb trail extraction. Returns [] if not found."""
    selectors = (
        "nav[aria-label='breadcrumb']",
        "nav[aria-label='Breadcrumb']",
        ".breadcrumb",
        "[class*=breadcrumb]",
    )
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            crumbs = [normalize_whitespace(a.get_text(" ", strip=True)) for a in node.find_all("a")]
            crumbs = [c for c in crumbs if c]
            if crumbs:
                return crumbs
    return []


def extract_title(soup: BeautifulSoup, fallback: str = "") -> str:
    """Page title. Prefer the h1 in the article; fall back to <title>."""
    article = _select_main(soup)
    h1 = article.find("h1") if article else None
    if h1 and h1.get_text(strip=True):
        return normalize_whitespace(h1.get_text(" ", strip=True))
    if soup.title and soup.title.string:
        title = soup.title.string
        # Elastic appends " | Elastic Docs" to most pages.
        title = re.sub(r"\s*\|\s*Elastic Docs?\s*$", "", title, flags=re.IGNORECASE)
        return normalize_whitespace(title)
    return fallback


def extract_clean_html(html: str) -> tuple[str, BeautifulSoup]:
    """Returns (clean inner-html-of-main, full-soup). Caller can inspect both."""
    soup = BeautifulSoup(html, "html.parser")
    main = _select_main(soup)
    _strip_noise(main)
    return str(main), soup


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def _iter_sections(main_node) -> Iterator[Dict[str, str]]:
    """
    Walk the main content top to bottom, emitting blocks of
    {section_heading, text} that respect heading boundaries.
    """
    current_heading = ""
    buffer: List[str] = []

    def flush() -> Optional[Dict[str, str]]:
        joined = normalize_whitespace("\n".join(buffer))
        buffer.clear()
        if joined:
            return {"section_heading": current_heading, "text": joined}
        return None

    # We only walk direct + nested children at any depth, but stop traversal
    # into elements that themselves emit text (avoids double counting).
    for el in main_node.descendants:
        name = getattr(el, "name", None)
        if name is None:
            continue
        if name in _HEADING_TAGS:
            section = flush()
            if section:
                yield section
            current_heading = normalize_whitespace(el.get_text(" ", strip=True))
            continue
        if name in ("p", "li", "pre", "code", "blockquote", "td", "th", "dt", "dd"):
            txt = el.get_text(" ", strip=True)
            if txt:
                buffer.append(txt)
    section = flush()
    if section:
        yield section


def chunk_sections(
    sections: Iterable[Dict[str, str]],
    target_chars: int = TARGET_CHARS_PER_CHUNK,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> List[Dict[str, str]]:
    """
    Pack section blocks into ~target_chars chunks, preserving section_heading
    on the chunk that owns most of the content. Splits overlong sections with
    a small overlap so semantic boundaries survive.
    """
    chunks: List[Dict[str, str]] = []
    buf_text = ""
    buf_heading = ""

    def push(text: str, heading: str) -> None:
        text = text.strip()
        if not text:
            return
        chunks.append({"section_heading": heading, "text": text})

    for sec in sections:
        heading = sec["section_heading"]
        text = sec["text"]
        if not text:
            continue

        # Long section: split on paragraph boundaries with overlap.
        if len(text) > target_chars:
            if buf_text:
                push(buf_text, buf_heading)
                buf_text, buf_heading = "", ""
            paras = [p.strip() for p in re.split(r"\n{2,}|(?<=\.)\s{2,}", text) if p.strip()]
            current = ""
            for p in paras:
                if len(current) + len(p) + 1 <= target_chars:
                    current = f"{current}\n{p}".strip()
                else:
                    if current:
                        push(current, heading)
                        # Start the next chunk with a tail-overlap from the previous.
                        tail = current[-overlap_chars:] if overlap_chars else ""
                        current = f"{tail}\n{p}".strip() if tail else p
                    else:
                        # Single paragraph longer than target_chars: hard wrap.
                        for i in range(0, len(p), target_chars - overlap_chars):
                            piece = p[i : i + target_chars]
                            push(piece, heading)
                        current = ""
            if current:
                push(current, heading)
            continue

        # Short section: append to the running buffer if it still fits.
        candidate_len = len(buf_text) + len(text) + 2
        if candidate_len <= target_chars:
            if buf_text:
                buf_text = f"{buf_text}\n\n{text}"
                # Keep the earliest heading for the buffer; do not overwrite.
                buf_heading = buf_heading or heading
            else:
                buf_text, buf_heading = text, heading
        else:
            push(buf_text, buf_heading)
            buf_text, buf_heading = text, heading

    if buf_text:
        push(buf_text, buf_heading)

    return chunks


def chunk_html_page(
    html: str,
    url: str,
    fetched_at: Optional[str] = None,
) -> List[Dict]:
    """
    End-to-end: raw HTML -> list of chunk records. Each chunk record matches
    the JSONL schema written to disk by fetch_elastic_docs.py.
    """
    _, soup = extract_clean_html(html)
    main = _select_main(soup)
    _strip_noise(main)

    title = extract_title(soup, fallback=url)
    breadcrumbs = extract_breadcrumbs(soup)
    sections = list(_iter_sections(main))
    raw_chunks = chunk_sections(sections)
    if not raw_chunks:
        # Fallback: dump the whole text into one chunk so we never silently
        # produce zero chunks for a page that did fetch successfully.
        whole = normalize_whitespace(main.get_text("\n", strip=True))
        if whole:
            raw_chunks = [{"section_heading": title, "text": whole[:TARGET_CHARS_PER_CHUNK]}]

    fetched_at = fetched_at or datetime.now(timezone.utc).isoformat()
    records: List[Dict] = []
    for idx, ch in enumerate(raw_chunks):
        records.append(
            {
                "url": url,
                "title": title,
                "breadcrumbs": breadcrumbs,
                "section_heading": ch["section_heading"],
                "chunk_index": idx,
                "text": ch["text"],
                "fetched_at": fetched_at,
            }
        )
    return records


# ---------------------------------------------------------------------------
# Disk IO + ES preparation
# ---------------------------------------------------------------------------


def iter_chunks(corpus_dir: Path) -> Iterable[Dict]:
    """Yield every chunk record stored under corpus_dir/*.jsonl, in file order."""
    corpus_dir = Path(corpus_dir)
    if not corpus_dir.exists():
        return
    for path in sorted(corpus_dir.glob("*.jsonl")):
        with path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    # Skip malformed lines but keep iterating.
                    continue


def prepare_for_index(chunk: Dict) -> Dict:
    """
    Normalize a chunk record into an ECS-leaning shape for the index.
    Keeps the original fields too so downstream callers can pick what they
    need. Indexing pipeline (owned by S3B) will add the ELSER inference field.
    """
    fetched_at = chunk.get("fetched_at") or datetime.now(timezone.utc).isoformat()
    return {
        "@timestamp": fetched_at,
        "url": chunk.get("url"),
        "title": chunk.get("title"),
        "text": chunk.get("text", ""),
        "section": {"heading": chunk.get("section_heading", "")},
        "chunk": {"index": int(chunk.get("chunk_index", 0))},
        "breadcrumbs": chunk.get("breadcrumbs", []) or [],
        "labels": {"source": "elastic-docs", "ingester": "fe-copilot"},
    }


__all__ = [
    "rough_token_count",
    "normalize_whitespace",
    "slugify",
    "extract_breadcrumbs",
    "extract_title",
    "extract_clean_html",
    "chunk_sections",
    "chunk_html_page",
    "iter_chunks",
    "prepare_for_index",
    "TARGET_CHARS_PER_CHUNK",
    "CHUNK_OVERLAP_CHARS",
]
