"""
filename: knowledge_repo.py
description: Repository over the fec-knowledge index. Supports three retrieval modes against the same 407-chunk ELSER-backed corpus: pure semantic (default, fastest), hybrid (semantic + BM25 fused via Reciprocal Rank Fusion), and hybrid_rerank (query expansion plus hybrid plus a Haiku cross-encoder re-rank). Every helper degrades gracefully so a single failure never breaks the FE Brain knowledge-search tool.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.2.0"
__status__ = "Development"

import json
from typing import Any, Dict, List, Optional, Tuple

from app.utils.logging import get_logger

log = get_logger(__name__)

INDEX_NAME = "fec-knowledge"
SEMANTIC_FIELD = "text_semantic"
SNIPPET_LEN = 350
RRF_K = 60
RERANK_POOL = 10
EXPANSION_VARIANTS = 3


class KnowledgeRepo:
    """Read-only repository over the fec-knowledge ELSER-backed index.

    Search modes:
      - "semantic"        : current default, single semantic_text query.
      - "hybrid"          : semantic + BM25 multi_match, fused with RRF (k=60).
      - "hybrid_rerank"   : query expansion + hybrid + Haiku cross-encoder re-rank.

    Every method returns an empty list / False on failure rather than raising,
    so the calling tool can always render a graceful answer.
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

    def search(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "semantic",
    ) -> List[Dict[str, Any]]:
        """Run a search against the fec-knowledge index.

        mode:
          - "semantic"      : ELSER semantic_text only (fastest, current default).
          - "hybrid"        : semantic + BM25 fused with Reciprocal Rank Fusion.
          - "hybrid_rerank" : query expansion + hybrid + Haiku cross-encoder rerank.

        Returns up to ``top_k`` hits, each shaped as:
        ``{score, url, title, section_heading, snippet, chunk_index, breadcrumbs}``.
        Always returns a list; on any failure logs a warning and returns ``[]``.
        """
        if not query or not query.strip():
            return []
        if self._client is None:
            return []

        mode = (mode or "semantic").lower().strip()
        try:
            if mode == "semantic":
                return self._search_semantic(query, top_k)
            if mode == "hybrid":
                return self._search_hybrid(query, top_k)
            if mode == "hybrid_rerank":
                return self._search_hybrid_rerank(query, top_k)
            log.info("knowledge.search.unknown_mode", mode=mode)
            return self._search_semantic(query, top_k)
        except Exception as exc:
            log.warning("knowledge.search_failed", error=str(exc), mode=mode, query=query[:120])
            try:
                # Last-resort safety net: pure semantic.
                return self._search_semantic(query, top_k)
            except Exception:
                return []

    # -------------------------------------------------------- semantic backend

    def _search_semantic(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """ELSER semantic_text query with automatic BM25 fallback.

        ELSER inference can be slow or unavailable in demo environments.
        If the semantic query fails or returns 0 hits, we immediately fall back
        to BM25 so the FE Brain tool always returns grounded citations.
        """
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
                request_timeout=12,
            )
            hits = self._shape_hits(self._extract_hits(res))
            if hits:
                return hits
            log.info("knowledge.semantic_empty_fallback_bm25", query=query[:80])
        except Exception as exc:
            log.warning("knowledge.semantic_failed_fallback_bm25", error=str(exc), query=query[:120])
        return self._search_bm25(query, top_k)

    # -------------------------------------------------------- BM25 backend

    def _search_bm25(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Lexical BM25 multi_match across `text` and `title` (title boosted 2x)."""
        try:
            res = self._client.search(
                index=INDEX_NAME,
                size=top_k,
                query={
                    "multi_match": {
                        "query": query,
                        "fields": ["title^2", "text"],
                        "type": "best_fields",
                        "operator": "or",
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
            log.warning("knowledge.bm25_failed", error=str(exc), query=query[:120])
            return []
        return self._shape_hits(self._extract_hits(res))

    # -------------------------------------------------------- hybrid + RRF

    def _search_hybrid(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Run semantic and BM25 in parallel (over wider pools) and fuse with RRF."""
        pool = max(top_k, RERANK_POOL)
        sem_hits = self._search_semantic(query, pool)
        bm25_hits = self._search_bm25(query, pool)
        fused = self._rrf_fuse([sem_hits, bm25_hits], k=RRF_K)
        return fused[:top_k]

    @staticmethod
    def _doc_key(hit: Dict[str, Any]) -> str:
        """Stable per-chunk key for dedupe + RRF."""
        url = (hit.get("url") or "").strip()
        chunk = hit.get("chunk_index")
        if url and chunk is not None:
            return f"{url}#{chunk}"
        if url:
            return url
        # Fall back to a snippet hash when URL missing.
        return f"snip:{(hit.get('snippet') or '')[:96]}"

    def _rrf_fuse(
        self,
        rankings: List[List[Dict[str, Any]]],
        k: int = RRF_K,
    ) -> List[Dict[str, Any]]:
        """Reciprocal Rank Fusion. Score = sum_i 1 / (k + rank_i). Higher is better."""
        scores: Dict[str, float] = {}
        seen: Dict[str, Dict[str, Any]] = {}
        for ranking in rankings:
            for rank, hit in enumerate(ranking, start=1):
                key = self._doc_key(hit)
                if not key:
                    continue
                scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
                if key not in seen:
                    seen[key] = hit
        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        out: List[Dict[str, Any]] = []
        for key, score in ordered:
            hit = dict(seen[key])
            hit["score"] = round(score, 6)
            out.append(hit)
        return out

    # -------------------------------------------------------- hybrid + rerank

    def _search_hybrid_rerank(self, query: str, top_k: int) -> List[Dict[str, Any]]:
        """Full pipeline: query expansion + hybrid retrieval + Haiku cross-encoder."""
        # Step 1: query expansion (cheap Haiku call).
        variants = self._query_expand(query)

        # Step 2: hybrid retrieval per variant, fused twice (per-variant RRF
        # then a meta-RRF across variants). This deduplicates across rewrites
        # and lets a chunk that ranks well under several variants float up.
        per_variant_rankings: List[List[Dict[str, Any]]] = []
        for variant in variants:
            sem = self._search_semantic(variant, RERANK_POOL)
            bm25 = self._search_bm25(variant, RERANK_POOL)
            fused = self._rrf_fuse([sem, bm25], k=RRF_K)
            if fused:
                per_variant_rankings.append(fused[:RERANK_POOL])

        if not per_variant_rankings:
            return []

        meta_fused = self._rrf_fuse(per_variant_rankings, k=RRF_K)
        candidates = meta_fused[:RERANK_POOL]

        # Step 3: cross-encoder rerank against the *original* query.
        reranked = self._rerank(query, candidates)
        return reranked[:top_k]

    # -------------------------------------------------------- query expansion

    def _query_expand(self, query: str) -> List[str]:
        """Ask Haiku to rewrite the query into a few diverse search variants.

        Always returns a list with at least the original query. On any failure
        falls back to ``[query]`` so retrieval can still proceed.
        """
        original = query.strip()
        try:
            from app.integrations.claude_client import MODEL_HAIKU, get_service

            schema = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "variants": {
                        "type": "array",
                        "items": {"type": "string"},
                    }
                },
                "required": ["variants"],
            }
            system = (
                "You rewrite Elastic Field Engineer questions into search queries for an Elastic "
                "documentation index. Produce diverse rewrites that emphasize different facets "
                "(setup, tuning, troubleshooting, reference syntax, observable signals). Keep each "
                "rewrite under 16 words. Use canonical Elastic feature names (Elasticsearch, ES|QL, "
                "EQL, ILM, semantic_text, ELSER). Never invent product names. Output via the "
                "json_schema response format only."
            )
            user = (
                f"Original Field Engineer question: {original}\n\n"
                f"Return exactly {EXPANSION_VARIANTS} distinct search queries that emphasize "
                "different aspects of the question. Each variant should be a self-contained search "
                "query, not a sentence to a human. Do not include the original question verbatim."
            )

            class _Variants:
                # Lightweight Pydantic-like shim so we can reuse call_structured.
                pass

            from pydantic import BaseModel

            class VariantsOut(BaseModel):
                variants: List[str]

            svc = get_service()
            result = svc.call_structured(
                system=system,
                user=user,
                schema=schema,
                output_model=VariantsOut,
                model=MODEL_HAIKU,
                max_tokens=512,
                effort="low",
                thinking_adaptive=False,
                cache_system=True,
                mock_payload={"variants": [original]},
                audit_meta={"agent": "knowledge_repo", "tool": "query_expand"},
            )
            variants = [v.strip() for v in (result.variants or []) if v and v.strip()]
        except Exception as exc:
            log.info("knowledge.query_expand_failed", error=str(exc))
            variants = []

        # Always include the original query first; dedupe case-insensitively.
        seen = set()
        out: List[str] = []
        for v in [original] + variants:
            key = v.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(v)
        # Cap to 4 variants total to bound parallel ES calls.
        return out[:4]

    # -------------------------------------------------------- cross-encoder rerank

    def _rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Score each candidate against the original query with a Haiku cross-encoder.

        Returns candidates sorted by rerank score (descending). On any failure,
        falls back to the input ordering (which is already RRF-fused).
        """
        if not candidates:
            return []
        try:
            from app.integrations.claude_client import MODEL_HAIKU, get_service
            from pydantic import BaseModel

            schema = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "scored": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "idx": {"type": "integer"},
                                "score": {"type": "integer"},
                                "reason": {"type": "string"},
                            },
                            "required": ["idx", "score", "reason"],
                        },
                    }
                },
                "required": ["scored"],
            }

            class RerankOut(BaseModel):
                scored: List[Dict[str, Any]]

            packed: List[str] = []
            for i, h in enumerate(candidates):
                title = (h.get("title") or "").strip() or "(untitled)"
                section = (h.get("section_heading") or "").strip()
                snippet = (h.get("snippet") or "").strip()
                if len(snippet) > 600:
                    snippet = snippet[:600].rstrip() + "..."
                head = f"[{i}] {title}"
                if section:
                    head += f" -- {section}"
                packed.append(f"{head}\n{snippet}")
            blob = "\n\n".join(packed)

            system = (
                "You are a relevance judge for an Elastic documentation search system. Given a "
                "Field Engineer question and a numbered list of candidate doc snippets, you score "
                "each snippet 1 (irrelevant) to 5 (directly answers the question) and explain in "
                "at most 12 words. Reward snippets that contain the exact setting names, syntax, "
                "or how-to steps the question is asking about. Penalize landing pages and snippets "
                "that only mention the topic in passing. Output via the json_schema response "
                "format only."
            )
            user = (
                f"Field Engineer question:\n{query.strip()}\n\n"
                f"Candidate snippets (numbered 0..{len(candidates) - 1}):\n\n{blob}\n\n"
                "Score every candidate. Return JSON with one entry per candidate, in any order, "
                "each containing idx, score (1-5), reason."
            )

            svc = get_service()
            result = svc.call_structured(
                system=system,
                user=user,
                schema=schema,
                output_model=RerankOut,
                model=MODEL_HAIKU,
                max_tokens=1024,
                effort="low",
                thinking_adaptive=False,
                cache_system=True,
                mock_payload={"scored": [{"idx": i, "score": 3, "reason": "mock"} for i in range(len(candidates))]},
                audit_meta={"agent": "knowledge_repo", "tool": "rerank", "candidates": len(candidates)},
            )

            score_by_idx: Dict[int, Tuple[int, str]] = {}
            for entry in result.scored or []:
                try:
                    idx = int(entry.get("idx"))
                    score = int(entry.get("score"))
                    reason = str(entry.get("reason") or "")
                except (TypeError, ValueError):
                    continue
                if 0 <= idx < len(candidates):
                    score_by_idx[idx] = (max(1, min(5, score)), reason)

            if not score_by_idx:
                log.info("knowledge.rerank_no_scores", candidates=len(candidates))
                return candidates

            def _key(i: int) -> Tuple[int, float]:
                rerank_score = score_by_idx.get(i, (0, ""))[0]
                # RRF score is a useful tiebreaker (it is the score we set above).
                rrf = float(candidates[i].get("score") or 0.0)
                return (rerank_score, rrf)

            order = sorted(range(len(candidates)), key=_key, reverse=True)
            out: List[Dict[str, Any]] = []
            for i in order:
                hit = dict(candidates[i])
                rerank_score, reason = score_by_idx.get(i, (None, ""))
                if rerank_score is not None:
                    hit["rerank_score"] = rerank_score
                    if reason:
                        hit["rerank_reason"] = reason
                out.append(hit)
            return out
        except Exception as exc:
            log.info("knowledge.rerank_failed", error=str(exc), candidates=len(candidates))
            return candidates

    # -------------------------------------------------------- shared helpers

    @staticmethod
    def _extract_hits(res: Any) -> List[Dict[str, Any]]:
        body = res if isinstance(res, dict) else res.body
        return ((body or {}).get("hits") or {}).get("hits") or []

    @staticmethod
    def _shape_hits(raw_hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for hit in raw_hits:
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
                    "text": text,
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
