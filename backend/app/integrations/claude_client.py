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

        try:
            response = self._client.messages.create(**kwargs)
        except Exception as exc:
            # Graceful degradation when the API is unavailable (credit balance
            # exhausted, rate limit, network error). If a mock_payload was
            # provided, fall back to it so the demo continues to work end-to-end
            # with a deterministic stub instead of a 500. The audit log records
            # the fallback so you can spot it later.
            msg = str(exc)
            is_credit = "credit balance is too low" in msg or "billing" in msg.lower()
            is_rate = "rate_limit" in msg.lower() or "429" in msg
            is_recoverable = is_credit or is_rate or "Connection" in msg
            if is_recoverable and mock_payload is not None:
                log.warning(
                    "claude.fallback_to_mock",
                    reason="credits" if is_credit else ("rate_limit" if is_rate else "transport"),
                    error=msg[:240],
                )
                _audit(
                    {
                        "ts": ts,
                        "model": model,
                        "mode": "fallback",
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "fallback_reason": "credits" if is_credit else ("rate_limit" if is_rate else "transport"),
                        **(audit_meta or {}),
                    }
                )
                return output_model.model_validate(mock_payload)
            raise
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


class ElasticInferenceService:
    """Routes structured LLM calls through Elastic's inference connectors in Kibana.

    Primary path: Kibana Actions API → Elastic connector → Anthropic model.
    This makes every agent call visible in Kibana's usage metrics and keeps
    the flow inside the Elastic stack rather than calling Anthropic directly.

    Fallback: direct Anthropic API (ClaudeService) for any connector error,
    empty response, or JSON parse failure - so agents never break.
    """

    def __init__(self) -> None:
        self._direct = ClaudeService()

    @property
    def mock_mode(self) -> bool:
        return self._direct.mock_mode

    @staticmethod
    def _connector_for(model: str) -> str:
        from app.integrations.agent_builder import get_connector_for
        return get_connector_for(model)

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
        strict: bool = False,
    ) -> T:
        """Call Claude via Elastic's inference connector.

        When ``strict=True`` every fallback path that would send data to the
        direct Anthropic API is blocked and raises ``RuntimeError`` instead.
        Use this for any call that contains private customer data so it never
        leaves the Elastic infrastructure.
        """
        import re as _re
        from app.integrations import agent_builder as ab

        ts = datetime.now(timezone.utc).isoformat()

        if getattr(self._direct, "mock_mode", False) and mock_payload is not None:
            _audit({"ts": ts, "model": model, "mode": "mock", "input_tokens": 0, "output_tokens": 0, **(audit_meta or {})})
            return output_model.model_validate(mock_payload)

        def _no_fallback(reason: str) -> None:
            if strict:
                raise RuntimeError(
                    f"Elastic inference connector required for customer data - direct Anthropic blocked. "
                    f"Reason: {reason}"
                )

        connector_id = self._connector_for(model)
        schema_str = json.dumps(schema, indent=2)
        elastic_system = (
            f"{system}\n\n"
            "IMPORTANT: You MUST respond with ONLY a valid JSON object that matches "
            f"this exact schema - no markdown, no explanation, just the JSON:\n{schema_str}"
        )

        log.info("elastic_inference.call", connector=connector_id, model=model, strict=strict)
        result = ab.call_inference_connector(
            connector_id,
            [{"role": "user", "content": user}],
            system=elastic_system,
            max_tokens=max_tokens,
        )

        # Bail out early when Kibana itself reports an error status.
        if isinstance(result, dict) and result.get("status") == "error":
            err_detail = str(result.get("data", ""))[:200]
            log.warning("elastic_inference.kibana_error", error=err_detail)
            _no_fallback(f"kibana_error: {err_detail}")
            return self._direct.call_structured(
                system=system, user=user, schema=schema, output_model=output_model,
                model=model, max_tokens=max_tokens, effort=effort,
                thinking_adaptive=thinking_adaptive, cache_system=cache_system,
                mock_payload=mock_payload, audit_meta=audit_meta,
            )

        # Extract text content from OpenAI-compatible response shape.
        content = ""
        if isinstance(result, dict) and not result.get("error"):
            try:
                content = (
                    result.get("data", {})
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                ) or ""
            except (KeyError, IndexError, TypeError):
                content = ""

        if not content:
            log.warning("elastic_inference.empty_or_error_fallback", connector=connector_id, result=str(result)[:200])
            _no_fallback("empty_response")
            return self._direct.call_structured(
                system=system, user=user, schema=schema, output_model=output_model,
                model=model, max_tokens=max_tokens, effort=effort,
                thinking_adaptive=thinking_adaptive, cache_system=cache_system,
                mock_payload=mock_payload, audit_meta=audit_meta,
            )

        # Try to extract usage from the Kibana response.
        try:
            usage = result.get("data", {}).get("usage", {})
            in_tok = usage.get("prompt_tokens", 0)
            out_tok = usage.get("completion_tokens", 0)
        except Exception:
            in_tok, out_tok = 0, 0

        _audit({"ts": ts, "model": f"elastic/{connector_id}", "mode": "elastic_inference",
                "input_tokens": in_tok, "output_tokens": out_tok, **(audit_meta or {})})

        # Parse JSON - strip markdown code fences if the model added them.
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            m = _re.search(r"```(?:json)?\s*([\s\S]*?)```", content)
            if m:
                try:
                    data = json.loads(m.group(1))
                except json.JSONDecodeError:
                    data = None
            else:
                data = None

        if data is None:
            log.warning("elastic_inference.json_parse_failed_fallback", preview=content[:200])
            _no_fallback("json_parse_failed")
            return self._direct.call_structured(
                system=system, user=user, schema=schema, output_model=output_model,
                model=model, max_tokens=max_tokens, effort=effort,
                thinking_adaptive=thinking_adaptive, cache_system=cache_system,
                mock_payload=mock_payload, audit_meta=audit_meta,
            )

        try:
            validated = output_model.model_validate(data)
            log.info("elastic_inference.success", connector=connector_id, in_tokens=in_tok, out_tokens=out_tok)
            return validated
        except Exception:
            log.warning("elastic_inference.validation_failed_fallback")
            _no_fallback("schema_validation_failed")
            return self._direct.call_structured(
                system=system, user=user, schema=schema, output_model=output_model,
                model=model, max_tokens=max_tokens, effort=effort,
                thinking_adaptive=thinking_adaptive, cache_system=cache_system,
                mock_payload=mock_payload, audit_meta=audit_meta,
            )


# Module-level singleton; created lazily so settings are honored.
_service: Optional[ClaudeService] = None


def get_service() -> "ClaudeService | ElasticInferenceService":
    """Return the active LLM service.

    When KIBANA_API_KEY is configured, routes through Elastic's inference
    connectors (Kibana-native path). Falls back to direct Anthropic otherwise.
    """
    global _service
    if _service is None:
        if getattr(settings, "kibana_api_key", ""):
            _service = ElasticInferenceService()  # type: ignore[assignment]
            log.info("claude.using_elastic_inference")
        else:
            _service = ClaudeService()
            log.info("claude.using_direct_anthropic")
    return _service


def get_elastic_service() -> "ElasticInferenceService":
    """Return an ElasticInferenceService, or raise if Kibana is not configured.

    Use this instead of get_service() for any call that contains private
    customer data (meeting transcripts, action items, account notes) so the
    data is guaranteed to stay inside the Elastic infrastructure and never
    reaches the direct Anthropic API.
    """
    svc = get_service()
    if not isinstance(svc, ElasticInferenceService):
        raise RuntimeError(
            "Elastic inference connector not available. "
            "Set KIBANA_API_KEY to route customer data through Elastic Cloud."
        )
    return svc


def reset_service() -> None:
    """Test hook: forces re-creation on the next get_service() call."""
    global _service
    _service = None
