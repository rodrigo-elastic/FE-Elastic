"""
filename: claude_client.py
description: Anthropic SDK wrapper. Handles prompt caching, structured outputs via output_config.format, model-aware param shaping (no thinking/effort on Haiku), and mock mode for offline demos.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


def _audit(record: Dict[str, Any]) -> None:
    """Append-only audit log for every Claude call. Compliance surface.

    Writes to the local JSONL file unconditionally (cheap, always available).
    Also pushes to the `fec-audit` ES index when the cluster is reachable,
    so a SOC operator can query token spend in Kibana without parsing files.
    """
    try:
        path = settings.runtime_dir / "audit.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except Exception as exc:
        # Never fail an agent call because audit logging hiccupped.
        log.warning("audit.write_failed", reason=str(exc))

    # Best-effort secondary write to Elasticsearch. Never raises.
    try:
        from app.repositories.elasticsearch_repo import get_repo

        get_repo().index_audit(record)
    except Exception:
        pass

# Model strings, kept centralized so swapping models is one line.
MODEL_OPUS = "claude-opus-4-7"
MODEL_HAIKU = "claude-haiku-4-5"

PLACEHOLDER_KEYS = {"", "sk-ant-replace-me"}

T = TypeVar("T", bound=BaseModel)


def _is_haiku(model: str) -> bool:
    return "haiku" in model


class ClaudeService:
    """Lightweight wrapper around the Anthropic SDK.

    Two responsibilities:
    1. Build a request that respects model constraints (no thinking/effort on Haiku 4.5; no temperature/top_p/top_k on Opus 4.7).
    2. Cache the stable system prompt so repeated calls hit the prefix cache.
    """

    def __init__(self, api_key: Optional[str] = None, mock_mode: Optional[bool] = None) -> None:
        key = api_key if api_key is not None else settings.anthropic_api_key
        # Auto-enable mock mode when no real key is configured. Lets demos run offline.
        auto_mock = key.strip() in PLACEHOLDER_KEYS
        self.mock_mode = mock_mode if mock_mode is not None else auto_mock
        self._client = None
        if not self.mock_mode:
            from anthropic import Anthropic

            self._client = Anthropic(api_key=key)
        log.info("claude.init", mock_mode=self.mock_mode)

    def call_structured(
        self,
        *,
        system: str,
        user: str,
        schema: Dict[str, Any],
        output_model: Type[T],
        model: str = MODEL_OPUS,
        max_tokens: int = 8192,
        effort: str = "high",
        thinking_adaptive: bool = True,
        cache_system: bool = True,
        mock_payload: Optional[Dict[str, Any]] = None,
        audit_meta: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Force Claude to return a structured JSON object that matches `schema`.

        Returns a validated instance of `output_model` (a Pydantic class).
        Every call is appended to runtime/audit.jsonl with timestamp, model, token usage, and any caller-provided audit_meta (e.g. agent name, meeting_id).
        """
        ts = datetime.now(timezone.utc).isoformat()
        if self.mock_mode:
            payload = mock_payload or {}
            _audit(
                {
                    "ts": ts,
                    "model": model,
                    "mode": "mock",
                    "input_tokens": 0,
                    "output_tokens": 0,
                    **(audit_meta or {}),
                }
            )
            return output_model.model_validate(payload)

        # System block carries the cache_control breakpoint when cache_system is True.
        if cache_system:
            system_param: Any = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_param = system

        output_config: Dict[str, Any] = {
            "format": {"type": "json_schema", "schema": schema},
        }
        kwargs: Dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_param,
            "messages": [{"role": "user", "content": user}],
            "output_config": output_config,
        }

        # effort errors on Haiku 4.5 and adaptive thinking is unsupported there.
        if not _is_haiku(model):
            output_config["effort"] = effort
            if thinking_adaptive:
                kwargs["thinking"] = {"type": "adaptive"}

        log.info(
            "claude.call",
            model=model,
            cached=cache_system,
            effort=output_config.get("effort"),
            schema_keys=list(schema.get("properties", {}).keys()),
        )

        response = self._client.messages.create(**kwargs)
        usage = getattr(response, "usage", None)
        in_tok = getattr(usage, "input_tokens", 0) if usage else 0
        out_tok = getattr(usage, "output_tokens", 0) if usage else 0
        cache_r = getattr(usage, "cache_read_input_tokens", 0) if usage else 0
        cache_w = getattr(usage, "cache_creation_input_tokens", 0) if usage else 0
        if usage is not None:
            log.info("claude.usage", input=in_tok, output=out_tok, cache_read=cache_r, cache_write=cache_w)
        _audit(
            {
                "ts": ts,
                "model": model,
                "mode": "live",
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "cache_read_input_tokens": cache_r,
                "cache_creation_input_tokens": cache_w,
                **(audit_meta or {}),
            }
        )

        stop_reason = getattr(response, "stop_reason", None)
        if stop_reason == "refusal":
            raise RuntimeError("Claude refused the request for safety reasons.")
        if stop_reason == "max_tokens":
            raise RuntimeError(
                "Claude hit max_tokens before finishing the structured output. "
                "Increase max_tokens or lower the schema complexity."
            )

        text = self._first_text_block(response)
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            log.error("claude.json_parse_failed", error=str(e), preview=text[:200])
            raise

        try:
            return output_model.model_validate(data)
        except ValidationError as e:
            log.error("claude.validation_failed", error=str(e), data=data)
            raise

    @staticmethod
    def _first_text_block(response: Any) -> str:
        for block in response.content:
            if getattr(block, "type", None) == "text":
                return block.text
        raise ValueError("Claude response contained no text block.")


# Module-level singleton; created lazily so settings are honored.
_service: Optional[ClaudeService] = None


def get_service() -> ClaudeService:
    global _service
    if _service is None:
        _service = ClaudeService()
    return _service


def reset_service() -> None:
    """Test hook: forces re-creation on the next get_service() call."""
    global _service
    _service = None
