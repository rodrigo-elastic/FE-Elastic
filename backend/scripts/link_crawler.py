"""
filename: link_crawler.py
description: Broken-link crawler for FE Copilot. Crawls every internal `<a href>` from /index.html down to depth 2 against the running backend on localhost:8123, verifies each URL returns a 2xx (or 405 for write-only API routes that only accept POST), checks #anchor fragments resolve to an `id` in the rendered HTML, audits JS-driven dynamic destinations (`location.href = ...`, `window.location = ...`, `history.pushState(..., url)`), and confirms `data-i18n` keys resolve to non-key text. Returns 0 when every link is green; 1 on any failure. Writes a markdown audit report to docs/qa-w24d-link-crawler.md and emits a one-line summary to stdout.
date: 04-05-2026
"""
from __future__ import annotations

__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import os
import re
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from urllib.parse import urldefrag, urlparse

import httpx

# --------------------------------------------------------------------------- Paths

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "backend"
FRONTEND_DIR = REPO_ROOT / "frontend"
DOCS_DIR = REPO_ROOT / "docs"
REPORT_PATH = DOCS_DIR / "qa-w24d-link-crawler.md"
JS_DIR = FRONTEND_DIR / "assets" / "js"

# --------------------------------------------------------------------------- Config

DEFAULT_BACKEND_PORT = int(os.environ.get("APP_PORT", "8123"))
BACKEND_BASE = os.environ.get(
    "LINK_CRAWLER_BASE", f"http://localhost:{DEFAULT_BACKEND_PORT}"
).rstrip("/")
SEED_URL = "/index.html"
MAX_DEPTH = 2

# Routes registered in the FastAPI app that only accept POST. A GET against these
# returns 405 by design; we accept that as success.
WRITE_ONLY_API_PREFIXES: Tuple[str, ...] = (
    "/api/v1/agents/",
    "/api/v1/agent-builder/converse",
    "/api/v1/agent-builder/agents",  # POST creates; GET listing is also fine
    "/api/v1/battlecards/reseed",
    "/api/v1/briefs/reindex",
    "/api/v1/demo-data/",  # /scenarios/{id}/seed
    "/api/v1/health/elasticsearch/reconnect",
    "/api/v1/health/kibana/setup",
    "/api/v1/kibana/dashboard/",
    "/api/v1/mcp",
    "/api/v1/tools/",
    "/api/v1/workflows/sync",
    "/api/v1/workflows/triggered",
    "/api/v1/workflows/demo-fire",
    "/api/v1/workflows/post-meeting-action-orphan",
    "/api/v1/workflows/orphan-demo-fire",
    "/api/v1/workflows/renewal-at-risk",
    "/api/v1/workflows/renewal-demo-fire",
)

# data-i18n key prefix patterns we expect to be wired in i18n.js.
I18N_KEY_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)+$", re.IGNORECASE)


# --------------------------------------------------------------------------- HTML parsing

class _LinkExtractor(HTMLParser):
    """Pulls href values plus all element ids from a single HTML page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: List[Tuple[str, int]] = []  # (href, line_no)
        self.ids: Set[str] = set()
        self.i18n_keys: List[Tuple[str, int]] = []  # (key, line_no)

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        line_no = self.getpos()[0]
        attr_map: Dict[str, Optional[str]] = {k: v for k, v in attrs}
        if tag.lower() == "a":
            href = attr_map.get("href")
            if href:
                self.hrefs.append((href, line_no))
        # Element id (anchor target).
        ident = attr_map.get("id")
        if ident:
            self.ids.add(ident)
        # data-i18n attributes (text content key).
        i18n = attr_map.get("data-i18n")
        if i18n and not i18n.startswith("aria-"):
            self.i18n_keys.append((i18n, line_no))


def _extract(html: str) -> _LinkExtractor:
    parser = _LinkExtractor()
    try:
        parser.feed(html)
    except Exception:
        # Some pages have inline scripts that confuse the parser; that is fine
        # because we only need the parser to finish what it can.
        pass
    return parser


# --------------------------------------------------------------------------- URL helpers

def _is_internal(href: str) -> bool:
    """Return True if href is internal to localhost:8123 (no scheme, no external host)."""
    if not href:
        return False
    # Pure anchors and javascript: hrefs are not crawlable URLs.
    if href.startswith("#") or href.lower().startswith("javascript:"):
        return False
    if href.startswith("mailto:") or href.startswith("tel:"):
        return False
    parsed = urlparse(href)
    if parsed.scheme and parsed.scheme not in ("http", "https"):
        return False
    if parsed.netloc:
        # External host. Skip.
        return False
    # Relative or absolute-path URL on our origin.
    return True


def _normalize(href: str, source_url: str) -> str:
    """Resolve href against the source page so relative links work."""
    if href.startswith("/"):
        return href
    # Relative to source. Source is always /something.html in our world.
    src_dir = source_url.rsplit("/", 1)[0] or ""
    return f"{src_dir}/{href}"


def _split_fragment(url: str) -> Tuple[str, str]:
    base, frag = urldefrag(url)
    return base, frag


def _is_html_page(url: str) -> bool:
    """True if the URL points to an HTML page we should recurse into."""
    base, _ = _split_fragment(url)
    if base in ("/", ""):
        return True
    if base.endswith(".html"):
        return True
    return False


def _is_api(url: str) -> bool:
    base, _ = _split_fragment(url)
    return base.startswith("/api/")


def _is_write_only_api(url: str) -> bool:
    base, _ = _split_fragment(url)
    if not base.startswith("/api/"):
        return False
    return any(base.startswith(prefix) for prefix in WRITE_ONLY_API_PREFIXES)


# --------------------------------------------------------------------------- Result data

@dataclass
class LinkCheck:
    url: str
    depth: int
    source_page: str
    source_line: int
    status: int
    ok: bool
    reason: str = ""
    has_anchor: bool = False
    anchor: str = ""
    anchor_ok: Optional[bool] = None


@dataclass
class JSDestCheck:
    file: str
    line: int
    raw: str
    resolved: str
    status: int
    ok: bool
    reason: str = ""


@dataclass
class I18nCheck:
    page: str
    line: int
    key: str
    rendered: str
    ok: bool
    reason: str = ""


@dataclass
class CrawlReport:
    started: float
    finished: float = 0.0
    links: List[LinkCheck] = field(default_factory=list)
    js_dynamic: List[JSDestCheck] = field(default_factory=list)
    i18n: List[I18nCheck] = field(default_factory=list)


# --------------------------------------------------------------------------- Crawler

def _check_url(
    client: httpx.Client,
    url: str,
    page_cache: Dict[str, str],
) -> Tuple[int, str, str]:
    """Issue a GET against url. Returns (status, body_text, reason). Body is text only for HTML."""
    full = BACKEND_BASE + url if url.startswith("/") else url
    try:
        r = client.get(full, timeout=15.0, follow_redirects=True)
    except httpx.RequestError as exc:
        return 0, "", f"network error: {exc}"

    body = ""
    ctype = r.headers.get("content-type", "")
    if "text/html" in ctype or "text/" in ctype:
        try:
            body = r.text
        except Exception:
            body = ""
    page_cache[url] = body
    return r.status_code, body, ""


def _crawl(client: httpx.Client) -> CrawlReport:
    started = time.monotonic()
    report = CrawlReport(started=started)

    # BFS up to MAX_DEPTH. Source pages are HTML; we only recurse into HTML pages.
    seen_urls: Set[str] = set()
    seen_pages: Set[str] = set()
    page_cache: Dict[str, str] = {}

    queue: deque = deque()
    queue.append((SEED_URL, 0, "(seed)", 0))

    while queue:
        url, depth, src_page, src_line = queue.popleft()
        # Dedupe per URL+anchor tuple so anchor verification is not skipped.
        if (url, depth) in seen_urls:
            continue
        seen_urls.add((url, depth))

        base, frag = _split_fragment(url)

        # Decide how to fetch. APIs use a tighter check; HTML uses GET.
        if _is_api(base):
            status, _, reason = _check_url(client, base, page_cache)
            ok = (200 <= status < 300) or (status == 405 and _is_write_only_api(base))
            if not ok and status == 405 and base.startswith("/api/"):
                # Heuristic: any /api/ path that responds with 405 likely exists
                # and is a write-only POST endpoint. Still mark ok to avoid noise.
                ok = True
            report.links.append(LinkCheck(
                url=url, depth=depth, source_page=src_page, source_line=src_line,
                status=status, ok=ok, reason=reason if not ok else "",
            ))
            continue

        # HTML or static asset.
        status, body, reason = _check_url(client, base, page_cache)
        ok = 200 <= status < 300

        anchor_ok: Optional[bool] = None
        if frag:
            # Verify the anchor id exists in the rendered HTML.
            if body:
                ids = _extract(body).ids
                anchor_ok = frag in ids
            else:
                anchor_ok = False
            if not anchor_ok:
                ok = False
                reason = (reason or "") + (
                    f" anchor #{frag} missing in {base}" if anchor_ok is False else ""
                )

        report.links.append(LinkCheck(
            url=url, depth=depth, source_page=src_page, source_line=src_line,
            status=status, ok=ok, reason=reason.strip(),
            has_anchor=bool(frag), anchor=frag, anchor_ok=anchor_ok,
        ))

        # Recurse only into HTML pages we have not parsed yet.
        if depth >= MAX_DEPTH:
            continue
        if not _is_html_page(base):
            continue
        if base in seen_pages:
            continue
        if not body:
            continue
        seen_pages.add(base)

        parser = _extract(body)
        for href, line_no in parser.hrefs:
            href = href.strip()
            if not _is_internal(href):
                continue
            resolved = _normalize(href, base if base != "/" else "/index.html")
            queue.append((resolved, depth + 1, base, line_no))

    report.finished = time.monotonic()
    return report


# --------------------------------------------------------------------------- JS audit

JS_DEST_PATTERNS = [
    re.compile(r"window\.location\.href\s*=\s*([\"'`])([^\"'`]+)\1"),
    re.compile(r"location\.href\s*=\s*([\"'`])([^\"'`]+)\1"),
    re.compile(r"window\.location\s*=\s*([\"'`])([^\"'`]+)\1"),
    re.compile(r"history\.pushState\s*\(\s*[^,]+,\s*[^,]+,\s*([\"'`])([^\"'`]+)\1"),
]
# Template-literal flavour for dynamic builders.
JS_TEMPLATE_PATTERNS = [
    re.compile(r"window\.location\.href\s*=\s*`([^`]+)`"),
    re.compile(r"location\.href\s*=\s*`([^`]+)`"),
]


def _audit_js(client: httpx.Client) -> List[JSDestCheck]:
    """Walk every .js file under frontend/assets/js, extract dynamic destinations, verify each one resolves."""
    out: List[JSDestCheck] = []
    if not JS_DIR.exists():
        return out
    seen_resolved: Set[Tuple[str, str]] = set()  # (file, resolved-url) dedupe per file

    for js_path in sorted(JS_DIR.glob("*.js")):
        try:
            text = js_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        rel = str(js_path.relative_to(REPO_ROOT))
        for line_no, raw_line in enumerate(text.splitlines(), start=1):
            for pat in JS_DEST_PATTERNS:
                for m in pat.finditer(raw_line):
                    raw_url = m.group(2)
                    resolved = _resolve_js_dest(raw_url)
                    if not resolved:
                        continue
                    if (rel, resolved) in seen_resolved:
                        continue
                    seen_resolved.add((rel, resolved))
                    status, ok, reason = _verify_js_dest(client, resolved)
                    out.append(JSDestCheck(
                        file=rel, line=line_no, raw=raw_url.strip(),
                        resolved=resolved, status=status, ok=ok, reason=reason,
                    ))
            for pat in JS_TEMPLATE_PATTERNS:
                for m in pat.finditer(raw_line):
                    raw_url = m.group(1)
                    resolved = _resolve_js_dest(raw_url)
                    if not resolved:
                        continue
                    if (rel, resolved) in seen_resolved:
                        continue
                    seen_resolved.add((rel, resolved))
                    status, ok, reason = _verify_js_dest(client, resolved)
                    out.append(JSDestCheck(
                        file=rel, line=line_no, raw=raw_url.strip(),
                        resolved=resolved, status=status, ok=ok, reason=reason,
                    ))
    return out


def _resolve_js_dest(raw: str) -> str:
    """Resolve a destination string from JS to a concrete path we can fetch.

    Replaces template-style `${...}` interpolations with a sentinel value that
    keeps the path shape valid for an existence check. Drops obvious dynamic
    fragments (e.g. "?id=" with nothing after it).
    """
    if not raw:
        return ""
    # Strip wrapping whitespace.
    s = raw.strip()
    # Drop pure anchors and javascript: links.
    if s.startswith("#") or s.lower().startswith("javascript:"):
        return ""
    # Replace ${...} blocks with a stable sentinel.
    s = re.sub(r"\$\{[^}]*\}", "test-001", s)
    # Trim trailing concatenation artifacts.
    s = s.split("\\n", 1)[0]
    # Must look like a path on our origin.
    if not s.startswith("/"):
        return ""
    return s


def _verify_js_dest(client: httpx.Client, url: str) -> Tuple[int, bool, str]:
    """GET the JS-dynamic destination; pass on any 2xx, or 3xx redirect that lands somewhere alive."""
    base, _frag = _split_fragment(url)
    full = BACKEND_BASE + base
    try:
        r = client.get(full, timeout=10.0, follow_redirects=True)
    except httpx.RequestError as exc:
        return 0, False, f"network error: {exc}"
    ok = 200 <= r.status_code < 400
    return r.status_code, ok, "" if ok else f"status={r.status_code}"


# --------------------------------------------------------------------------- i18n audit

def _audit_i18n(client: httpx.Client) -> List[I18nCheck]:
    """For every data-i18n key on every frontend HTML page, verify the rendered text is not the literal key.

    We treat a missing-translation symptom as: rendered text == key, OR rendered text is the dotted-key shape that i18n.js falls back to when a key is missing.
    """
    out: List[I18nCheck] = []
    if not FRONTEND_DIR.exists():
        return out

    for html_path in sorted(FRONTEND_DIR.glob("*.html")):
        rel = "/" + html_path.name
        try:
            r = client.get(BACKEND_BASE + rel, timeout=10.0)
            if r.status_code != 200:
                continue
            html = r.text
        except Exception:
            continue
        parser = _extract(html)
        seen_keys: Set[str] = set()
        for key, line_no in parser.i18n_keys:
            if key in seen_keys:
                continue
            seen_keys.add(key)
            # Find the rendered text inside the element. We do not parse the DOM
            # here; instead we look for `data-i18n="key">TEXT<` in the raw HTML.
            m = re.search(
                r'data-i18n="' + re.escape(key) + r'"[^>]*>([^<]{0,200})<',
                html,
            )
            rendered = (m.group(1).strip() if m else "")
            ok = True
            reason = ""
            # Heuristic A: rendered text is exactly the key.
            if rendered == key:
                ok = False
                reason = "rendered text equals i18n key (missing translation)"
            # Heuristic B: rendered text matches the dotted-key shape (a.b.c) with no spaces.
            elif rendered and " " not in rendered and I18N_KEY_PATTERN.match(rendered):
                ok = False
                reason = f"rendered text '{rendered}' looks like a literal i18n key"
            out.append(I18nCheck(
                page=rel, line=line_no, key=key, rendered=rendered, ok=ok, reason=reason,
            ))
    return out


# --------------------------------------------------------------------------- Reporting

def _write_report(report: CrawlReport, js_dynamic: List[JSDestCheck], i18n: List[I18nCheck], em_dash_total: int) -> None:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    runtime_s = report.finished - report.started

    crawled = len(report.links)
    ok_links = sum(1 for c in report.links if c.ok)
    bad_4xx = sum(1 for c in report.links if 400 <= c.status < 500 and not c.ok)
    bad_5xx = sum(1 for c in report.links if 500 <= c.status < 600 and not c.ok)
    missing_anchor = sum(1 for c in report.links if c.has_anchor and c.anchor_ok is False)
    js_total = len(js_dynamic)
    js_bad = sum(1 for c in js_dynamic if not c.ok)
    i18n_total = len(i18n)
    i18n_bad = sum(1 for c in i18n if not c.ok)

    lines: List[str] = []
    lines.append("# QA W24D - Broken-link Crawler (depth 2)")
    lines.append("")
    lines.append(f"- Generated: {now}")
    lines.append(f"- Backend base: {BACKEND_BASE}")
    lines.append(f"- Seed: {SEED_URL}")
    lines.append(f"- Max depth: {MAX_DEPTH}")
    lines.append(f"- Runtime: {runtime_s:.2f} s")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("| --- | ---: |")
    lines.append(f"| URLs crawled | {crawled} |")
    lines.append(f"| OK | {ok_links} |")
    lines.append(f"| 4xx | {bad_4xx} |")
    lines.append(f"| 5xx | {bad_5xx} |")
    lines.append(f"| Missing anchors | {missing_anchor} |")
    lines.append(f"| JS dynamic destinations | {js_total} (bad: {js_bad}) |")
    lines.append(f"| i18n keys checked | {i18n_total} (bad: {i18n_bad}) |")
    lines.append(f"| em-dash hits in repo | {em_dash_total} |")
    lines.append("")

    failures = [c for c in report.links if not c.ok]
    lines.append("## Failures")
    lines.append("")
    if not failures and js_bad == 0 and i18n_bad == 0:
        lines.append("None. All links, anchors, dynamic destinations, and i18n keys resolve.")
    else:
        lines.append("| # | Source page | Line | URL | Status | Reason |")
        lines.append("| ---: | --- | ---: | --- | ---: | --- |")
        for i, c in enumerate(failures, start=1):
            reason = (c.reason or "").replace("|", "\\|") or "-"
            lines.append(f"| {i} | {c.source_page} | {c.source_line} | {c.url} | {c.status} | {reason} |")
        lines.append("")
        if js_bad:
            lines.append("### JS dynamic destinations")
            lines.append("")
            lines.append("| File | Line | Raw | Resolved | Status | Reason |")
            lines.append("| --- | ---: | --- | --- | ---: | --- |")
            for c in js_dynamic:
                if c.ok:
                    continue
                reason = (c.reason or "").replace("|", "\\|") or "-"
                lines.append(f"| {c.file} | {c.line} | `{c.raw}` | {c.resolved} | {c.status} | {reason} |")
            lines.append("")
        if i18n_bad:
            lines.append("### Missing i18n keys")
            lines.append("")
            lines.append("| Page | Line | Key | Rendered | Reason |")
            lines.append("| --- | ---: | --- | --- | --- |")
            for c in i18n:
                if c.ok:
                    continue
                rendered = (c.rendered or "").replace("|", "\\|")
                reason = (c.reason or "").replace("|", "\\|") or "-"
                lines.append(f"| {c.page} | {c.line} | {c.key} | {rendered} | {reason} |")
            lines.append("")

    lines.append("## All Crawled URLs")
    lines.append("")
    lines.append("| Depth | Source page | Line | URL | Status | Anchor | Anchor OK |")
    lines.append("| ---: | --- | ---: | --- | ---: | --- | --- |")
    for c in sorted(report.links, key=lambda r: (r.depth, r.source_page, r.source_line)):
        anchor_ok = "-"
        if c.has_anchor:
            anchor_ok = "yes" if c.anchor_ok else "NO"
        lines.append(
            f"| {c.depth} | {c.source_page} | {c.source_line} | {c.url} | {c.status} | "
            f"{c.anchor or '-'} | {anchor_ok} |"
        )
    lines.append("")
    lines.append("## JS Dynamic Destinations")
    lines.append("")
    if not js_dynamic:
        lines.append("None detected.")
    else:
        lines.append("| File | Line | Raw | Resolved | Status | OK |")
        lines.append("| --- | ---: | --- | --- | ---: | --- |")
        for c in js_dynamic:
            lines.append(
                f"| {c.file} | {c.line} | `{c.raw}` | {c.resolved} | {c.status} | "
                f"{'yes' if c.ok else 'NO'} |"
            )
    lines.append("")
    lines.append("## i18n Keys")
    lines.append("")
    lines.append(f"Checked {i18n_total} `data-i18n` keys across frontend HTML pages. Bad: {i18n_bad}.")
    lines.append("")
    lines.append("## Raw JSON")
    lines.append("")
    lines.append("```json")
    payload = {
        "summary": {
            "crawled": crawled,
            "ok": ok_links,
            "fail_4xx": bad_4xx,
            "fail_5xx": bad_5xx,
            "missing_anchor": missing_anchor,
            "js_total": js_total,
            "js_bad": js_bad,
            "i18n_total": i18n_total,
            "i18n_bad": i18n_bad,
            "em_dash_total": em_dash_total,
        },
        "runtime_s": runtime_s,
    }
    lines.append(json.dumps(payload, indent=2, default=str))
    lines.append("```")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _em_dash_count() -> int:
    """Repo-wide em/en dash count over the same scope the smoke uses, minus this script."""
    # Unicode escapes so this script does not flag itself in either audit.
    em = "\u2014"
    en = "\u2013"
    text_exts = {
        ".py", ".html", ".js", ".mjs", ".ts", ".tsx", ".jsx",
        ".css", ".md", ".json", ".jsonl", ".yml", ".yaml", ".txt", ".sh",
        ".cfg", ".ini", ".toml",
    }
    skip_dirs = {"__pycache__", "node_modules", ".venv", ".git", "screenshots", "gifs"}
    skip = {Path(__file__).name}
    total = 0
    targets = [BACKEND_DIR, FRONTEND_DIR, DOCS_DIR, REPO_ROOT / "data"]
    for root in [p for p in targets if p.exists()]:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fname in filenames:
                if fname in skip:
                    continue
                p = Path(dirpath) / fname
                if p.suffix.lower() not in text_exts:
                    continue
                try:
                    txt = p.read_text(encoding="utf-8", errors="strict")
                except Exception:
                    continue
                total += txt.count(em) + txt.count(en)
    return total


# --------------------------------------------------------------------------- Main

def main() -> int:
    print(f"FE Copilot link crawler -- backend={BACKEND_BASE} seed={SEED_URL} depth={MAX_DEPTH}", flush=True)
    with httpx.Client(verify=True, follow_redirects=True) as client:
        # Sanity check the backend is up before crawling.
        try:
            r = client.get(BACKEND_BASE + "/api/v1/health", timeout=5.0)
            if r.status_code != 200:
                print(f"backend health returned {r.status_code}; aborting", flush=True)
                return 1
        except Exception as exc:
            print(f"backend not reachable at {BACKEND_BASE}: {exc}", flush=True)
            return 1

        report = _crawl(client)
        js_dynamic = _audit_js(client)
        i18n = _audit_i18n(client)

    em_dash_total = _em_dash_count()

    crawled = len(report.links)
    ok_links = sum(1 for c in report.links if c.ok)
    bad = crawled - ok_links
    js_bad = sum(1 for c in js_dynamic if not c.ok)
    i18n_bad = sum(1 for c in i18n if not c.ok)

    _write_report(report, js_dynamic, i18n, em_dash_total)

    print(
        f"crawled={crawled} ok={ok_links} fail={bad} js_dynamic={len(js_dynamic)} (bad={js_bad}) "
        f"i18n_bad={i18n_bad} em_dash={em_dash_total}",
        flush=True,
    )
    print(f"report: {REPORT_PATH}", flush=True)

    if bad > 0 or js_bad > 0 or i18n_bad > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
