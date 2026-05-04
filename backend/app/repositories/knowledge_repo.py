"""
filename: knowledge_repo.py
description: Repository over the fec-knowledge index (semantic_text + ELSER). Provides a graceful semantic search helper used by the FE Brain knowledge-search MCP tool.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import Any, Dict, List, Optional

from app.utils.logging import get_logger

log = get_logger(__name__)

INDEX_NAME = "fec-knowledge"
SEMANTIC_FIELD = "text_semantic"
SNIPPET_LEN = 350


class KnowledgeRepo:
    """Read-only repository over the fec-knowledge ELSER-backed index.

    Every method degrades gracefully (returns empty result / False) if the
    index is missing or Elasticsearch is unreachable.
    """

    def __init__(self, es: Optional[Any] = None) -> None:
        self._client = es
        if self._client is None:
            try:
                from app.integrations.elasticsearch_client import get_client

                self._client = get_client()
            except Exception as exc:
                log.warning("knowledge.client_init_failed", error=str(exc))
                self._client = None

    # ------------------------------------------------------------------ health

    def available(self) -> bool:
        """True iff the index exists and contains at least one document."""
        if self._client is None:
            return False
        try:
            if not self._client.indices.exists(index=INDEX_NAME):
                return False
            res = self._client.count(index=INDEX_NAME)
            count = res.get("count", 0) if isinstance(res, dict) else res.body.get("count", 0)
            return int(count) > 0
        except Exception as exc:
            log.info("knowledge.available_check_failed", error=str(exc))
            return False

    def health_summary(self) -> Dict[str, Any]:
        """Return a small dict the FE Brain UI can render: docs / unique URLs / index state."""
        summary: Dict[str, Any] = {
            "index": INDEX_NAME,
            "exists": False,
            "docs": 0,
            "urls": 0,
            "available": False,
        }
        if self._client is None:
            summary["error"] = "no_es_client"
            return summary
        try:
            exists = bool(self._client.indices.exists(index=INDEX_NAME))
            summary["exists"] = exists
            if not exists:
                return summary
            count_res = self._client.count(index=INDEX_NAME)
            count = count_res.get("count", 0) if isinstance(count_res, dict) else count_res.body.get("count", 0)
            summary["docs"] = int(count)

            agg_res = self._client.search(
                index=INDEX_NAME,
                size=0,
                aggs={"unique_urls": {"cardinality": {"field": "url"}}},
            )
            body = agg_res if isinstance(agg_res, dict) else agg_res.body
            urls = ((body.get("aggregations") or {}).get("unique_urls") or {}).get("value", 0)
            summary["urls"] = int(urls)
            summary["available"] = summary["docs"] > 0
        except Exception as exc:
            summary["error"] = str(exc)
            log.info("knowledge.health_failed", error=str(exc))
        return summary

    # ------------------------------------------------------------------ search

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Run a semantic query against the ELSER-backed text_semantic field.

        Returns up to ``top_k`` hits, each shaped as:
        ``{score, url, title, section_heading, snippet, chunk_index}``.
        Always returns a list; on any failure logs a warning and returns ``[]``.
        """
        if not query or not query.strip():
            return []
        if self._client is None:
            return []
        try:
            res = self._client.search(
                index=INDEX_NAME,
                size=top_k,
                query={
                    "semantic": {
                        "field": SEMANTIC_FIELD,
                        "query": query,
                    }
                },
                source_includes=[
                    "url",
                    "title",
                    "breadcrumbs",
                    "section.heading",
                    "chunk.index",
                    "text",
                ],
            )
        except Exception as exc:
            log.warning("knowledge.search_failed", error=str(exc), query=query[:120])
            return []

        body = res if isinstance(res, dict) else res.body
        hits = ((body or {}).get("hits") or {}).get("hits") or []
        out: List[Dict[str, Any]] = []
        for hit in hits:
            src = hit.get("_source") or {}
            text = src.get("text") or ""
            snippet = text[:SNIPPET_LEN].rstrip()
            if len(text) > SNIPPET_LEN:
                snippet += "..."
            section = src.get("section") or {}
            chunk = src.get("chunk") or {}
            out.append(
                {
                    "score": hit.get("_score"),
                    "url": src.get("url") or "",
                    "title": src.get("title") or "",
                    "section_heading": section.get("heading") if isinstance(section, dict) else "",
                    "snippet": snippet,
                    "chunk_index": chunk.get("index") if isinstance(chunk, dict) else None,
                    "breadcrumbs": src.get("breadcrumbs") or [],
                }
            )
        return out


# Module-level convenience singleton. Callers may also instantiate directly.
_repo: Optional[KnowledgeRepo] = None


def get_knowledge_repo() -> KnowledgeRepo:
    global _repo
    if _repo is None:
        _repo = KnowledgeRepo()
    return _repo


def reset_knowledge_repo() -> None:
    global _repo
    _repo = None
