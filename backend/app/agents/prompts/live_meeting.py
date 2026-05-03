"""
filename: live_meeting.py
description: System prompt and JSON schema for the Live Meeting Companion (Haiku).
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

# Tight system prompt: this runs on Haiku 4.5 per turn, so latency matters.
SYSTEM = """You are an Elastic FE's live whisper assistant during a customer meeting.

Given the most recent transcript turn plus optional context, return ONLY actionable alerts. Stay silent (empty alerts list) when nothing meaningful happened.

Alert types:
- competitor: customer named Splunk, Datadog, Sumo Logic, Grafana, New Relic, etc.
- meddpicc: customer surfaced a Metrics, Economic Buyer, Decision Criteria, Decision Process, Identify Pain, Champion, or Competition signal.
- question: customer asked something the FE should answer crisply.
- risk: red flag (timeline pressure, blocker, internal opposition).

Hard rules:
- message must be under 80 characters; FE sees this as a popup.
- suggested_response must be 1 to 2 sentences, ready to paraphrase.
- Skip vanilla pleasantries and small talk.
- Never use the em dash character."""

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "alerts": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["competitor", "meddpicc", "question", "risk"],
                    },
                    "severity": {
                        "type": "string",
                        "enum": ["low", "med", "high"],
                    },
                    "message": {"type": "string"},
                    "suggested_response": {"type": "string"},
                },
                "required": ["type", "severity", "message", "suggested_response"],
            },
        }
    },
    "required": ["alerts"],
}


def render_user_prompt(turn: dict, recent_context: list | None = None) -> str:
    parts = []
    if recent_context:
        parts.append("# Recent context (last few turns)")
        for t in recent_context[-4:]:
            parts.append(f"- {t['speaker']}: {t['text']}")
        parts.append("")
    parts.append("# New turn")
    parts.append(f"{turn['speaker']}: {turn['text']}")
    parts.append("")
    parts.append("Return alerts now (empty list if nothing actionable).")
    return "\n".join(parts)


def mock_response_for(text: str) -> dict:
    """Cheap heuristic mock used in offline mode and demos."""
    text_lower = text.lower()
    alerts = []

    competitors = ["splunk", "datadog", "sumo logic", "grafana", "new relic"]
    for comp in competitors:
        if comp in text_lower:
            alerts.append(
                {
                    "type": "competitor",
                    "severity": "high",
                    "message": f"Competitor named: {comp.title()}",
                    "suggested_response": (
                        f"Acknowledge their {comp.title()} usage neutrally, then anchor to a measurable "
                        "pain that Elastic resolves better."
                    ),
                }
            )

    if any(k in text_lower for k in ["million dollars", "$", "renewal", "budget", "audit", "soc 2"]):
        alerts.append(
            {
                "type": "meddpicc",
                "severity": "med",
                "message": "Metrics or Decision Process signal in this turn.",
                "suggested_response": (
                    "Capture the dollar figure or date precisely; ask one follow-up to confirm the constraint "
                    "(who owns it, when it locks)."
                ),
            }
        )

    if "?" in text:
        alerts.append(
            {
                "type": "question",
                "severity": "low",
                "message": "Customer asked a question; answer crisply.",
                "suggested_response": "Give a one sentence answer first, then offer to send a follow-up artifact.",
            }
        )

    return {"alerts": alerts}
