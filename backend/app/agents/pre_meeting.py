"""
filename: pre_meeting.py
description: Pre-Meeting Researcher agent. Builds an account brief, posts to Slack mock, generates PDF, persists JSON.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict

from app.agents.base import Agent
from app.agents.prompts import language_instruction, language_preamble, pre_meeting as prompt
from app.agents.schemas import PreMeetingBriefOut
from app.config import settings
from app.integrations import sec_edgar, slack_mock
from app.integrations.claude_client import get_service
from app.repositories import synthetic
from app.repositories.elasticsearch_repo import get_repo as get_es_repo
from app.services import pdf_builder
from app.utils.logging import get_logger

log = get_logger(__name__)

SLACK_CHANNEL = "#fe-copilot-briefs"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s or "ad-hoc"


def _split_csv(value: str) -> list[str]:
    return [p.strip() for p in value.split(",") if p.strip()]


class PreMeetingAgent(Agent):
    name = "pre_meeting"

    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        meeting_id = payload["meeting_id"]
        meeting = synthetic.find_meeting(meeting_id)
        if meeting is None:
            raise ValueError(f"meeting_id {meeting_id} not found in synthetic data")
        company = synthetic.find_company(meeting["company_id"])
        if company is None:
            raise ValueError(f"company {meeting['company_id']} not found")

        # Real-data enrichment: pull recent SEC filings when the company is publicly listed.
        sec_filings = sec_edgar.fetch_recent_filings(company.get("sec_cik") or "", limit=5)

        dossier = {
            "company": company,
            "meeting": meeting,
            "news": synthetic.news_for(company["id"]),
            "tickets": synthetic.tickets_for(company["id"]),
            "past_transcripts": synthetic.past_transcripts_for(company["id"]),
            "sec_filings": sec_filings,
        }

        language = payload.get("language") or "English"
        log.info("pre_meeting.start", meeting_id=meeting_id, company=company["name"], language=language)

        result: PreMeetingBriefOut = get_service().call_structured(
            system=prompt.SYSTEM,
            user=language_preamble(language) + prompt.render_user_prompt(dossier) + language_instruction(language),
            schema=prompt.OUTPUT_SCHEMA,
            output_model=PreMeetingBriefOut,
            model=(payload.get("model") or "").strip() or settings.model_for("pre_meeting"),
            max_tokens=4096,
            effort="high",
            mock_payload=prompt.mock_response(company["id"]),
            audit_meta={"agent": "pre_meeting", "meeting_id": meeting_id, "company_id": company["id"]},
        )
        brief_dict = result.model_dump()

        artifact_path = pdf_builder.render_pdf(company=company, meeting=meeting, brief=brief_dict)

        slack_text = self._format_slack(company, meeting, brief_dict, artifact_path)
        slack_mock.post_message(channel=SLACK_CHANNEL, text=slack_text)

        record = {
            "meeting_id": meeting_id,
            "company_id": company["id"],
            "company_name": company.get("name"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "headline": brief_dict["headline"],
            "sections": brief_dict["sections"],
            "artifact_path": str(artifact_path),
            "slack_channel": SLACK_CHANNEL,
            # Underlying sources Claude saw when producing the brief; surfaced in the UI
            # as clickable links so the FE can verify every claim.
            "sources_used": {
                "news": [
                    {"title": n.get("title"), "url": n.get("url"), "source": n.get("source"), "published_at": n.get("published_at")}
                    for n in dossier.get("news", [])
                ],
                "tickets": [
                    {"subject": t.get("subject"), "priority": t.get("priority"), "status": t.get("status"), "company_id": t.get("company_id")}
                    for t in dossier.get("tickets", [])
                ],
                "past_transcripts": [
                    {"meeting_id": t.get("meeting_id"), "turn_count": len(t.get("turns", []))}
                    for t in dossier.get("past_transcripts", [])
                ],
                "sec_filings": sec_filings,
            },
        }
        out_dir = settings.runtime_dir / "briefs"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{meeting_id}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        # Best-effort ES write. Disk is the source of truth; ES is a queryable mirror.
        get_es_repo().index_brief(record)

        log.info("pre_meeting.complete", meeting_id=meeting_id, artifact=str(artifact_path))
        return record

    async def run_ad_hoc(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Quick Research: build a transient dossier from user-typed input and run the Pre-Meeting agent.

        Takes only the fields the FE typed; nothing else leaves the boundary. The result is persisted
        as `runtime/briefs/ad-hoc-<slug>.json` so the meeting view can read it back.
        """
        name = (payload.get("company_name") or "").strip()
        if not name:
            raise ValueError("company_name is required")

        slug_id = _slug(name)
        meeting_id = f"ad-hoc-{slug_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"

        company = {
            "id": f"ad-hoc-{slug_id}",
            "name": name,
            "industry": (payload.get("industry") or "").strip() or "Unknown",
            "size": (payload.get("size") or "").strip() or "Unknown",
            "headquarters": None,
            "website": None,
            "tech_stack": {
                "observability": _split_csv(payload.get("tech_stack") or ""),
                "search": [],
                "cloud": [],
                "other": [],
            },
            "description": (payload.get("notes") or "").strip() or None,
        }
        meeting = {
            "id": meeting_id,
            "company_id": company["id"],
            "title": (payload.get("meeting_title") or "").strip() or f"Discovery with {name}",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "attendees": [],
            "notes": payload.get("notes"),
        }
        dossier = {
            "company": company,
            "meeting": meeting,
            "news": [],
            "tickets": [],
            "past_transcripts": [],
        }

        language = payload.get("language") or "English"
        log.info("pre_meeting.ad_hoc.start", company=name, meeting_id=meeting_id, language=language)

        result: PreMeetingBriefOut = get_service().call_structured(
            system=prompt.SYSTEM,
            user=language_preamble(language) + prompt.render_user_prompt(dossier) + language_instruction(language),
            schema=prompt.OUTPUT_SCHEMA,
            output_model=PreMeetingBriefOut,
            model=(payload.get("model") or "").strip() or settings.model_for("pre_meeting"),
            max_tokens=4096,
            effort="high",
            mock_payload=prompt.mock_response("acme-001"),  # generic fallback for offline demos
            audit_meta={
                "agent": "pre_meeting",
                "mode": "ad_hoc",
                "company_name": name,
                "meeting_id": meeting_id,
            },
        )
        brief_dict = result.model_dump()
        artifact_path = pdf_builder.render_pdf(company=company, meeting=meeting, brief=brief_dict)

        record = {
            "meeting_id": meeting_id,
            "company_id": company["id"],
            "company_name": name,
            "ad_hoc": True,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "headline": brief_dict["headline"],
            "sections": brief_dict["sections"],
            "artifact_path": str(artifact_path),
            "company_snapshot": company,
            "meeting_snapshot": meeting,
            # Ad-hoc has no external news/tickets, but the user-typed input IS the source.
            # Surfacing it explicitly is more honest than hiding the panel.
            "sources_used": {
                "news": [],
                "tickets": [],
                "past_transcripts": [],
                "user_input": {
                    "company_name": name,
                    "industry": company["industry"],
                    "size": company["size"],
                    "tech_stack_notes": (payload.get("tech_stack") or "").strip(),
                    "notes": (payload.get("notes") or "").strip(),
                    "meeting_title": meeting["title"],
                },
            },
        }
        out_dir = settings.runtime_dir / "briefs"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{meeting_id}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        get_es_repo().index_brief(record)

        log.info("pre_meeting.ad_hoc.complete", meeting_id=meeting_id, artifact=str(artifact_path))
        return record

    @staticmethod
    def _format_slack(
        company: Dict[str, Any],
        meeting: Dict[str, Any],
        brief: Dict[str, Any],
        artifact: "object",
    ) -> str:
        name = company.get("name", "Account")
        headline = brief.get("headline", "")
        sections = brief.get("sections", [])

        # Pull the most useful bullets: first bullet of each of the first 3 sections.
        highlights = []
        for sec in sections[:3]:
            bullets = sec.get("bullets", [])
            if bullets:
                highlights.append(f"  - *{sec['heading']}:* {bullets[0]}")

        # Grab the first discovery question if present (last section often named "Questions").
        question = ""
        for sec in reversed(sections):
            heading = sec.get("heading", "").lower()
            if "question" in heading or "discovery" in heading:
                bullets = sec.get("bullets", [])
                if bullets:
                    question = bullets[0]
                break

        lines = [
            f":memo: *Brief ready: {name}*",
            f"_{meeting.get('title', 'Meeting')} - {meeting.get('start_time', '')}._",
            "",
            f"*{headline}*",
            "",
        ]
        lines.extend(highlights)
        if question:
            lines += ["", f":speech_balloon: *Open with:* {question}"]
        return "\n".join(lines)
