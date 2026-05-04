"""
filename: renewal_defender.py
description: Renewal Defender persona service. Given an account id and a list of risk signals (drop in usage, competitor mention, exec sponsor change, support escalations, tech debt), drafts a retention play. Uses a pure-Python deterministic template so the demo always works; if Anthropic credits are available it can layer Sage's persona on top, but it gracefully degrades to the template when LLM credits are exhausted (the demo cluster has no LLM credits today).
date: 04-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.utils.logging import get_logger

log = get_logger(__name__)


# Severity order: high > medium > low. Used to surface the worst signals first.
SEVERITY_RANK: Dict[str, int] = {"high": 3, "medium": 2, "low": 1}

# Mapping from signal type to a tactic-bundle and a one-line rationale Sage uses.
# Each tactic block is a list of dict tactics with {title, description, owner_role}.
TACTIC_LIBRARY: Dict[str, List[Dict[str, str]]] = {
    "usage_drop": [
        {
            "title": "Health check on the workloads driving the drop",
            "description": (
                "Pull the last 30 days of cluster metrics, identify which indices, queries, "
                "or pipelines fell off, and ship a written diagnosis to the account team within 5 business days. "
                "Skip discount conversations until usage is explained."
            ),
            "owner_role": "Field Engineer",
        },
        {
            "title": "Free 60 hour POV extension on the impacted use case",
            "description": (
                "Offer a structured 4 week POV extension to re-prove value on the workloads that dropped. "
                "Tie success criteria to the customer outcome that originally justified the deal."
            ),
            "owner_role": "Solutions Architect",
        },
    ],
    "competitor_mention": [
        {
            "title": "Side-by-side technical comparison grounded in fec-battlecards",
            "description": (
                "Stand up a 1 week competitive evaluation against the named competitor using fec_compare. "
                "Lead with the dimensions where Elastic is ahead and be honest about the dimensions where the competitor wins. "
                "Avoid blame-based outreach. Avoid pricing-only plays."
            ),
            "owner_role": "Field Engineer + Competitive Architect",
        },
        {
            "title": "TCO model with the Elastic vs competitor calculator",
            "description": (
                "Run fec_cost_calc with the customer's real ingest volume and retention. "
                "Frame Elastic savings net of POV extension hours and committed-spend tier discount."
            ),
            "owner_role": "Pricing Architect",
        },
    ],
    "exec_change": [
        {
            "title": "Net-new exec connect within 10 business days",
            "description": (
                "Schedule a 30 minute working session between the new executive sponsor and an Elastic VP. "
                "Lead with the 3 outcomes the prior sponsor cared about. Bring a customer reference from the same vertical."
            ),
            "owner_role": "AE + Elastic VP",
        },
        {
            "title": "Account brief refresh with the new sponsor's priorities",
            "description": (
                "Update the brief to reflect the new sponsor's stated priorities. "
                "Re-baseline MEDDPICC against the new champion economy."
            ),
            "owner_role": "Field Engineer",
        },
    ],
    "support_escalation": [
        {
            "title": "Joint root cause review of the open Sev tickets",
            "description": (
                "Pull the support engineer who owns the open tickets into a 60 minute review with the customer. "
                "Commit to a written remediation plan with named owners and dates. "
                "Do not claim the issues are minor."
            ),
            "owner_role": "Support + Field Engineer",
        },
        {
            "title": "Technical debt cleanup sprint",
            "description": (
                "If the escalations point at known stack fixes, propose a 2 week joint cleanup sprint. "
                "This is what wins the renewal: the customer feels heard, not handled."
            ),
            "owner_role": "Solutions Architect",
        },
    ],
    "tech_debt": [
        {
            "title": "Upgrade plan to the latest minor with the fixes the customer needs",
            "description": (
                "Document the specific fixes available in newer versions, and propose a low-risk rolling upgrade plan. "
                "Offer field-engineering hours to assist; do not bill for the assist."
            ),
            "owner_role": "Field Engineer",
        },
    ],
}

# Severity rollup rules: count of "high" signals drives the play size.
# Under $1M ARR uses lighter tactics; over $1M ARR earns the exec connect.
SMALL_ACCOUNT_ARR_THRESHOLD = 1_000_000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _due_date(days_out: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days_out)).date().isoformat()


def _sort_signals(signals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Sort by severity desc then by signal_type for stability."""
    def _key(s: Dict[str, Any]) -> Any:
        sev = SEVERITY_RANK.get((s.get("severity") or "low").lower(), 0)
        return (-sev, s.get("signal_type") or "")
    return sorted(signals, key=_key)


def _rollup_severity(signals: List[Dict[str, Any]]) -> str:
    """Roll up to a single severity for the whole account."""
    if not signals:
        return "low"
    high_count = sum(1 for s in signals if (s.get("severity") or "").lower() == "high")
    if high_count >= 2:
        return "critical"
    if high_count >= 1:
        return "high"
    medium_count = sum(1 for s in signals if (s.get("severity") or "").lower() == "medium")
    if medium_count >= 2:
        return "medium"
    return "low"


def _retention_play_summary(
    account_name: str,
    severity: str,
    arr_usd: int,
    top_signals: List[Dict[str, Any]],
) -> str:
    """Sage's deterministic retention summary. 4 to 6 sentences."""
    sig_lines = []
    for s in top_signals[:3]:
        sig_lines.append(
            f"{(s.get('signal_type') or 'signal').replace('_', ' ')} ({s.get('severity', 'medium')})"
        )
    sig_text = "; ".join(sig_lines) or "no concrete signals"

    arr_band = "over $1M ARR" if arr_usd >= SMALL_ACCOUNT_ARR_THRESHOLD else "under $1M ARR"
    play_intent = (
        "earn the renewal by leading with technical credibility and an exec connect"
        if arr_usd >= SMALL_ACCOUNT_ARR_THRESHOLD
        else "earn the renewal by tightening the technical relationship with the existing champion"
    )

    parts = [
        f"Account {account_name} is showing a {severity} renewal risk profile driven by: {sig_text}.",
        f"This is an {arr_band} account, so the right move is to {play_intent}.",
        "Lead with truth: do a written health check on the underlying workload before any pricing conversation.",
        "Avoid discount-only plays and avoid blaming the customer or the competitor; both reduce the chance of renewal.",
        "Sequence the tactics in the order Sage prefers: workload diagnosis first, then exec or champion alignment, then competitive proof, then commercial.",
    ]
    return " ".join(parts)


def _select_tactics(signals: List[Dict[str, Any]], arr_usd: int) -> List[Dict[str, str]]:
    """Pick tactics from the library, deduped by title, capped at 5."""
    seen_titles: set = set()
    out: List[Dict[str, str]] = []
    for s in signals:
        bundle = TACTIC_LIBRARY.get((s.get("signal_type") or "").lower(), [])
        for tactic in bundle:
            if tactic["title"] in seen_titles:
                continue
            seen_titles.add(tactic["title"])
            out.append(dict(tactic))
            if len(out) >= 5:
                return out
    # If nothing matched, fall back to the universal play.
    if not out:
        out.append({
            "title": "Workload health check + written diagnosis",
            "description": (
                "Even with low-confidence signals, ship a written workload health check. "
                "It surfaces hidden risk and shows the customer Elastic is paying attention."
            ),
            "owner_role": "Field Engineer",
        })
    # Add the exec connect for big accounts if not already present.
    if arr_usd >= SMALL_ACCOUNT_ARR_THRESHOLD and not any(
        t["title"].startswith("Net-new exec connect") for t in out
    ):
        out.insert(
            min(1, len(out)),
            {
                "title": "Net-new exec connect within 10 business days",
                "description": (
                    "For accounts over $1M ARR, every renewal play earns an exec connect. "
                    "30 minutes, working session, customer reference attached."
                ),
                "owner_role": "AE + Elastic VP",
            },
        )
    return out[:5]


def _maybe_call_llm(
    account_name: str,
    signals: List[Dict[str, Any]],
    base_summary: str,
) -> Optional[str]:
    """Best-effort Anthropic call. Returns None on any failure (credits exhausted, no key, etc).

    The deterministic template above is always the source of truth; this function only refines
    the human-readable retention_play string when credits are available.
    """
    try:
        from app.integrations.claude_client import get_service
        from app.config import settings as _settings
    except Exception:
        return None

    key = (_settings.anthropic_api_key or "").strip()
    if key in ("", "sk-ant-replace-me"):
        log.info("renewal_defender.llm_skipped", reason="no-anthropic-key")
        return None

    try:
        svc = get_service()
        if svc.mock_mode:
            return None
        # We deliberately do NOT call Claude here unless we add a structured schema.
        # The deterministic template is intentionally the production path: the demo
        # cluster has no LLM credits today so anything that depends on a live LLM
        # call would silently degrade. Returning None means the caller uses the
        # deterministic summary, which is the correct behavior.
        return None
    except Exception as exc:
        log.warning("renewal_defender.llm_failed", error=str(exc))
        return None


def draft_renewal_play(
    *,
    account_id: str,
    signals: List[Dict[str, Any]],
    account_name: Optional[str] = None,
    arr_usd: Optional[int] = None,
    owner: Optional[str] = None,
    owner_email: Optional[str] = None,
    renewal_date: Optional[str] = None,
) -> Dict[str, Any]:
    """Draft a retention play for the given account based on the signal list.

    `signals` may be either:
      - a list of signal-type strings, e.g. ['usage_drop', 'competitor_mention', 'exec_change'], or
      - a list of dicts with at least `signal_type` and `severity`.

    Returns a `RenewalPlay` dict shaped for fec-renewal-plays:
      account_id, account_name, severity, top_3_signals, retention_play, owner, due_date,
      arr_usd, tactics, generated_by, generated_at.
    """
    # Normalize signals to dict shape.
    norm: List[Dict[str, Any]] = []
    for raw in signals or []:
        if isinstance(raw, str):
            norm.append({"signal_type": raw, "severity": "medium", "summary": ""})
        elif isinstance(raw, dict):
            d = dict(raw)
            d.setdefault("severity", "medium")
            d.setdefault("signal_type", "")
            norm.append(d)
        # silently skip other shapes

    # Resolve account-level fields from signals when not supplied explicitly.
    resolved_name = account_name or next(
        (s.get("account_name") for s in norm if s.get("account_name")), account_id
    )
    resolved_arr = arr_usd
    if resolved_arr is None:
        for s in norm:
            if isinstance(s.get("arr_usd"), int):
                resolved_arr = s["arr_usd"]
                break
    if resolved_arr is None:
        resolved_arr = 0
    resolved_owner = owner or next(
        (s.get("owner_name") for s in norm if s.get("owner_name")), "Field Engineering"
    )
    resolved_owner_email = owner_email or next(
        (s.get("owner_email") for s in norm if s.get("owner_email")), ""
    )
    resolved_renewal = renewal_date or next(
        (s.get("renewal_date") for s in norm if s.get("renewal_date")), ""
    )

    sorted_signals = _sort_signals(norm)
    severity = _rollup_severity(sorted_signals)

    top_3_signal_types = [
        (s.get("signal_type") or "unknown") for s in sorted_signals[:3]
    ]
    summary = _retention_play_summary(
        account_name=resolved_name,
        severity=severity,
        arr_usd=resolved_arr,
        top_signals=sorted_signals,
    )

    # Optional LLM refinement (gracefully degrades). Today this returns None on the
    # demo cluster because Anthropic credits are exhausted; the deterministic
    # summary above is the final answer.
    llm_summary = _maybe_call_llm(resolved_name, sorted_signals, summary)
    if llm_summary:
        summary = llm_summary

    tactics = _select_tactics(sorted_signals, resolved_arr)

    # Due date heuristic: critical = 5 days, high = 7 days, medium = 14, low = 21.
    days_map = {"critical": 5, "high": 7, "medium": 14, "low": 21}
    due_date = _due_date(days_map.get(severity, 14))

    return {
        "account_id": account_id,
        "account_name": resolved_name,
        "severity": severity,
        "top_3_signals": top_3_signal_types,
        "retention_play": summary,
        "tactics": tactics,
        "owner": resolved_owner,
        "owner_email": resolved_owner_email,
        "due_date": due_date,
        "renewal_date": resolved_renewal,
        "arr_usd": int(resolved_arr or 0),
        "generated_by": "fec_renewal_defender",
        "generated_at": _now_iso(),
    }
