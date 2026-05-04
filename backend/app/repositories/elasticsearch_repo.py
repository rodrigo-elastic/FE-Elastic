"""
filename: elasticsearch_repo.py
description: Optional Elasticsearch persistence for briefs, post-meeting outputs, and audit log. Best-effort writes; reads fall back to disk if ES is unreachable.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)

INDEX_BRIEFS = "fec-briefs"
INDEX_POST = "fec-post-meetings"
INDEX_AUDIT = "fec-audit"
INDEX_BATTLECARDS = "fec-battlecards"
BATTLECARDS_SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seed" / "battlecards.json"

MAPPINGS_PATH = Path(__file__).resolve().parents[2] / "data" / "seed" / "es_mappings.json"


def _load_mappings() -> Dict[str, Any]:
    if not MAPPINGS_PATH.exists():
        return {}
    return json.loads(MAPPINGS_PATH.read_text(encoding="utf-8"))


class ElasticsearchRepo:
    """Thin wrapper over the ES client. Every method degrades gracefully when ES is unreachable."""

    def __init__(self) -> None:
        self._client = None
        self._available = False
        self._last_error: Optional[str] = None
        self._connect()

    def _connect(self) -> None:
        try:
            from app.integrations.elasticsearch_client import get_client

            client = get_client()
            if client.ping():
                self._client = client
                self._available = True
                log.info("es.connected", url=settings.elasticsearch_url)
        except Exception as exc:
            self._available = False
            self._last_error = str(exc)
            log.info("es.unavailable", reason=self._last_error)

    @property
    def available(self) -> bool:
        return self._available

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def reconnect(self) -> bool:
        """Force a fresh ping; useful after starting docker-compose mid-session."""
        self._connect()
        return self._available

    def ensure_indices(self) -> Dict[str, str]:
        """Create our app-owned indices if missing. Returns a status map."""
        if not self._available:
            return {}
        mappings = _load_mappings()
        status: Dict[str, str] = {}
        for idx in (INDEX_BRIEFS, INDEX_POST, INDEX_AUDIT, INDEX_BATTLECARDS):
            try:
                if not self._client.indices.exists(index=idx):
                    body = mappings.get(idx, {})
                    self._client.indices.create(index=idx, body=body)
                    status[idx] = "created"
                else:
                    status[idx] = "exists"
            except Exception as exc:
                status[idx] = f"error: {exc}"
                log.warning("es.ensure_index_failed", index=idx, error=str(exc))
        # Seed battlecards if the index is empty (first-run experience).
        try:
            self._seed_battlecards_if_empty()
        except Exception as exc:
            log.warning("es.battlecards_seed_failed", error=str(exc))
        return status

    def _seed_battlecards_if_empty(self) -> None:
        if not self._available or not BATTLECARDS_SEED_PATH.exists():
            return
        try:
            count = self._client.count(index=INDEX_BATTLECARDS).get("count", 0)
        except Exception:
            count = 0
        if count > 0:
            return
        cards = json.loads(BATTLECARDS_SEED_PATH.read_text(encoding="utf-8"))
        for card in cards:
            try:
                self._client.index(index=INDEX_BATTLECARDS, id=card["id"], document=card, refresh=False)
            except Exception as exc:
                log.warning("es.battlecard_index_failed", id=card.get("id"), error=str(exc))
        try:
            self._client.indices.refresh(index=INDEX_BATTLECARDS)
        except Exception:
            pass
        log.info("es.battlecards_seeded", count=len(cards))

    def reseed_battlecards(self) -> Dict[str, Any]:
        """Force-reindex every card from the seed file. Used when the schema changes
        (for example when verticals are added) and the existing index is stale."""
        if not self._available or not BATTLECARDS_SEED_PATH.exists():
            return {"ok": False, "reason": "es_unavailable_or_no_seed"}
        cards = json.loads(BATTLECARDS_SEED_PATH.read_text(encoding="utf-8"))
        indexed = 0
        for card in cards:
            try:
                self._client.index(index=INDEX_BATTLECARDS, id=card["id"], document=card, refresh=False)
                indexed += 1
            except Exception as exc:
                log.warning("es.battlecard_reseed_failed", id=card.get("id"), error=str(exc))
        try:
            self._client.indices.refresh(index=INDEX_BATTLECARDS)
        except Exception:
            pass
        log.info("es.battlecards_reseeded", count=indexed, total=len(cards))
        return {"ok": True, "indexed": indexed, "total": len(cards)}

    # ------------------------------------------------------------------ briefs

    def index_brief(self, record: Dict[str, Any]) -> bool:
        if not self._available:
            return False
        try:
            self._client.index(index=INDEX_BRIEFS, id=record["meeting_id"], document=record, refresh=False)
            return True
        except Exception as exc:
            log.warning("es.index_brief_failed", error=str(exc))
            return False

    def get_brief(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        if not self._available:
            return None
        try:
            res = self._client.get(index=INDEX_BRIEFS, id=meeting_id)
            return res.get("_source")
        except Exception:
            return None

    def list_briefs(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self._available:
            return []
        try:
            res = self._client.search(
                index=INDEX_BRIEFS,
                body={
                    "size": limit,
                    "sort": [{"generated_at": {"order": "desc"}}],
                    "query": {"match_all": {}},
                },
            )
            return [hit["_source"] for hit in res["hits"]["hits"]]
        except Exception as exc:
            log.warning("es.list_briefs_failed", error=str(exc))
            return []

    # ------------------------------------------------------------ post-meeting

    def index_post_meeting(self, record: Dict[str, Any]) -> bool:
        if not self._available:
            return False
        try:
            self._client.index(index=INDEX_POST, id=record["meeting_id"], document=record, refresh=False)
            return True
        except Exception as exc:
            log.warning("es.index_post_failed", error=str(exc))
            return False

    def get_post_meeting(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        if not self._available:
            return None
        try:
            res = self._client.get(index=INDEX_POST, id=meeting_id)
            return res.get("_source")
        except Exception:
            return None

    def list_post_meetings(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self._available:
            return []
        try:
            res = self._client.search(
                index=INDEX_POST,
                body={
                    "size": limit,
                    "sort": [{"generated_at": {"order": "desc"}}],
                    "query": {"match_all": {}},
                },
            )
            return [hit["_source"] for hit in res["hits"]["hits"]]
        except Exception as exc:
            log.warning("es.list_post_failed", error=str(exc))
            return []

    # ---------------------------------------------------------- battlecards

    def find_battlecard(self, competitor: str) -> Optional[Dict[str, Any]]:
        """Best-match lookup for a competitor name (case-insensitive substring)."""
        if not self._available or not competitor:
            return None
        try:
            res = self._client.search(
                index=INDEX_BATTLECARDS,
                body={
                    "size": 1,
                    "query": {
                        "bool": {
                            "should": [
                                {"term": {"competitor_slug": competitor.lower()}},
                                {"match_phrase_prefix": {"competitor": competitor}},
                                {"match": {"competitor": {"query": competitor, "fuzziness": "AUTO"}}},
                            ],
                            "minimum_should_match": 1,
                        }
                    },
                },
            )
            hits = res["hits"]["hits"]
            return hits[0]["_source"] if hits else None
        except Exception as exc:
            log.warning("es.find_battlecard_failed", competitor=competitor, error=str(exc))
            return None

    def list_battlecards(self) -> List[Dict[str, Any]]:
        if not self._available:
            return []
        try:
            res = self._client.search(
                index=INDEX_BATTLECARDS,
                body={"size": 200, "query": {"match_all": {}}, "sort": [{"competitor_slug": "asc"}]},
            )
            return [hit["_source"] for hit in res["hits"]["hits"]]
        except Exception:
            return []

    # -------------------------------------------------------------------- audit

    def index_audit(self, record: Dict[str, Any]) -> bool:
        if not self._available:
            return False
        try:
            self._client.index(index=INDEX_AUDIT, document=record, refresh=False)
            return True
        except Exception:
            return False

    # --------------------------------------------------------------- reindex

    def reindex_from_disk(self) -> Dict[str, int]:
        """Push everything currently on disk into ES. Returns counts per index."""
        if not self._available:
            return {"briefs": 0, "post_meetings": 0}
        self.ensure_indices()
        briefs = 0
        posts = 0

        briefs_dir = settings.runtime_dir / "briefs"
        if briefs_dir.exists():
            for p in briefs_dir.glob("*.json"):
                try:
                    rec = json.loads(p.read_text(encoding="utf-8"))
                    if self.index_brief(rec):
                        briefs += 1
                except Exception as exc:
                    log.warning("es.reindex_brief_failed", path=str(p), error=str(exc))

        post_dir = settings.runtime_dir / "post_meeting"
        if post_dir.exists():
            for p in post_dir.glob("*.json"):
                try:
                    rec = json.loads(p.read_text(encoding="utf-8"))
                    if self.index_post_meeting(rec):
                        posts += 1
                except Exception as exc:
                    log.warning("es.reindex_post_failed", path=str(p), error=str(exc))

        try:
            self._client.indices.refresh(index=f"{INDEX_BRIEFS},{INDEX_POST}")
        except Exception:
            pass
        return {"briefs": briefs, "post_meetings": posts}


# Module-level singleton.
_repo: Optional[ElasticsearchRepo] = None


def get_repo() -> ElasticsearchRepo:
    global _repo
    if _repo is None:
        _repo = ElasticsearchRepo()
    return _repo


def reset_repo() -> None:
    global _repo
    _repo = None
