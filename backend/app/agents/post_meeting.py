"""
filename: post_meeting.py
description: Post-Meeting Action Engine. Produces summary, action items, MEDDPICC signals, competitor mentions, and follow-up email; pushes action items to the Salesforce mock and saves the email draft.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.base import Agent
from app.agents.prompts import language_instruction, language_preamble, post_meeting as prompt
from app.agents.schemas import PostMeetingResultOut
from app.config import settings
from app.integrations import salesforce_mock, slack_mock
from app.integrations.claude_client import get_service
from app.integrations.email_sender import send as send_email
from app.repositories import synthetic
from app.repositories.elasticsearch_repo import get_repo as get_es_repo
from app.services import email_drafter
from app.utils.logging import get_logger

log = get_logger(__name__)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "ad-hoc"


class PostMeetingAgent(Agent):
    name = "post_meeting"

    async def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        meeting_id = payload["meeting_id"]
        meeting = synthetic.find_meeting(meeting_id)
        if meeting is None:
            raise ValueError(f"meeting_id {meeting_id} not found")
        company = synthetic.find_company(meeting["company_id"])
        if company is None:
            raise ValueError(f"company {meeting['company_id']} not found")
        transcript = synthetic.transcript_for_meeting(meeting_id)
        if transcript is None:
            raise ValueError(f"no transcript on file for meeting {meeting_id}")

        language = payload.get("language") or "English"
        log.info("post_meeting.start", meeting_id=meeting_id, language=language)

        result: PostMeetingResultOut = get_service().call_structured(
            system=prompt.SYSTEM,
            user=language_preamble(language) + prompt.render_user_prompt(company, meeting, transcript) + language_instruction(language),
            schema=prompt.OUTPUT_SCHEMA,
            output_model=PostMeetingResultOut,
            model=(payload.get("model") or "").strip() or settings.model_for("post_meeting"),
            max_tokens=8192,
            effort="high",
            mock_payload=prompt.mock_response(company["id"]),
            audit_meta={"agent": "post_meeting", "meeting_id": meeting_id, "company_id": company["id"]},
        )
        data = result.model_dump()

        # Push every action item into the Salesforce mock.
        sfdc_tasks = []
        sfdc_records = []
        impact_to_priority = {"high": "High", "med": "Normal", "low": "Low"}
        for item in data["action_items"]:
            r = salesforce_mock.create_task(
                subject=item["title"],
                owner=item["owner_name"],
                due_date=item.get("due_date") or "TBD",
                description=f"{item['description']}\n\nSource quote: {item['source_quote']}",
                what_id=meeting_id,
                account_id=company["id"],
                priority=impact_to_priority.get((item.get("impact") or "med").lower(), "Normal"),
                impact=item.get("impact"),
                activity_type="Follow Up",
            )
            sfdc_tasks.append(r["task_id"])
            sfdc_records.append({"id": r["task_id"], "url": r["url"], "subject": item["title"]})

        # Persist the follow-up email draft.
        email_path = email_drafter.save(
            meeting_id=meeting_id,
            email=data["follow_up_email"],
            to=meeting.get("attendees", []),
        )

        # Send real email to NOTIFY_EMAIL when configured.
        notify_to = settings.notify_email
        if notify_to:
            fu_email = data.get("follow_up_email") or {}
            action_lines = "\n".join(
                f"- [{a.get('owner', 'unassigned')}] {a.get('title', '')}"
                for a in data.get("action_items", [])
            )
            send_email(
                to=notify_to,
                subject=fu_email.get("subject") or f"[FEC] Post-meeting: {company.get('name', meeting_id)}",
                body_markdown=fu_email.get("body_markdown", "") + f"\n\n---\n**Action items**\n{action_lines}",
                meeting_id=meeting_id,
            )

        # Post Slack summary with action items to #fe-copilot-briefs.
        items = data.get("action_items", [])
        high = [a for a in items if str(a.get("impact", "")).lower() == "high"]
        unassigned = [a for a in items if not a.get("owner_email")]
        item_lines = "\n".join(
            f"  {'*' if str(a.get('impact','')).lower()=='high' else '-'} "
            f"[{a.get('owner', 'unassigned')}] {a.get('title', '')}"
            for a in items[:5]
        )
        slack_mock.post_message(
            channel="#fe-copilot-briefs",
            text=(
                f":checkered_flag: *Post-meeting: {company.get('name', meeting_id)}*\n"
                f"{len(items)} action items | {len(high)} high-impact | {len(unassigned)} unassigned\n"
                f"\n{item_lines}"
                + (f"\n\n:rotating_light: {len(unassigned)} item(s) need an owner." if unassigned else "")
            ),
        )

        # Extended Salesforce writes - the post-meeting flow drives the full deal record.
        sfdc_writes = _full_salesforce_sync(company, meeting_id, data)

        record = {
            "meeting_id": meeting_id,
            "company_id": company["id"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": data["summary"],
            "action_items": data["action_items"],
            "meddpicc_signals": data["meddpicc_signals"],
            "competitor_mentions": data["competitor_mentions"],
            "follow_up_email": data["follow_up_email"],
            "salesforce_task_ids": sfdc_tasks,
            "salesforce_tasks": sfdc_records,
            "salesforce_account": sfdc_writes["account"],
            "salesforce_writes": sfdc_writes,
            "email_draft_path": str(email_path),
        }

        out_dir = settings.runtime_dir / "post_meeting"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{meeting_id}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        # Best-effort ES write.
        get_es_repo().index_post_meeting(record)

        log.info(
            "post_meeting.complete",
            meeting_id=meeting_id,
            actions=len(data["action_items"]),
            sfdc_tasks=len(sfdc_tasks),
        )
        return record

    async def run_ad_hoc(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Process an externally-supplied transcript (Zoom, Gong export, manual paste).

        Sits on top of the same Claude prompt + persistence path as run(), but the company
        and meeting are synthesised from user input. The transcript turns must already be parsed.
        """
        name = (payload.get("company_name") or "").strip()
        if not name:
            raise ValueError("company_name is required")
        turns: Optional[List[Dict[str, Any]]] = payload.get("turns")
        if not turns:
            raise ValueError("turns must be a non-empty list of {speaker,text}")

        slug_id = _slug(name)
        meeting_id = f"transcript-{slug_id}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        company = {
            "id": f"transcript-{slug_id}",
            "name": name,
            "industry": (payload.get("industry") or "").strip() or "Unknown",
            "size": (payload.get("size") or "").strip() or "Unknown",
            "tech_stack": {"observability": [], "search": [], "cloud": [], "other": []},
            "description": payload.get("notes") or None,
        }
        meeting = {
            "id": meeting_id,
            "company_id": company["id"],
            "title": (payload.get("meeting_title") or "").strip() or f"Transcript with {name}",
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "attendees": [],
            "notes": payload.get("notes"),
        }
        transcript = {"meeting_id": meeting_id, "company_id": company["id"], "turns": turns}

        language = payload.get("language") or "English"
        log.info("post_meeting.ad_hoc.start", meeting_id=meeting_id, turns=len(turns), language=language)

        result: PostMeetingResultOut = get_service().call_structured(
            system=prompt.SYSTEM,
            user=language_preamble(language) + prompt.render_user_prompt(company, meeting, transcript) + language_instruction(language),
            schema=prompt.OUTPUT_SCHEMA,
            output_model=PostMeetingResultOut,
            model=(payload.get("model") or "").strip() or settings.model_for("post_meeting"),
            max_tokens=8192,
            effort="high",
            mock_payload=prompt.mock_response("acme-001"),
            audit_meta={
                "agent": "post_meeting",
                "mode": "ad_hoc",
                "company_name": name,
                "meeting_id": meeting_id,
            },
        )
        data = result.model_dump()

        sfdc_tasks = []
        sfdc_records = []
        impact_to_priority = {"high": "High", "med": "Normal", "low": "Low"}
        for item in data["action_items"]:
            r = salesforce_mock.create_task(
                subject=item["title"],
                owner=item["owner_name"],
                due_date=item.get("due_date") or "TBD",
                description=f"{item['description']}\n\nSource quote: {item['source_quote']}",
                what_id=meeting_id,
                account_id=company["id"],
                priority=impact_to_priority.get((item.get("impact") or "med").lower(), "Normal"),
                impact=item.get("impact"),
                activity_type="Follow Up",
            )
            sfdc_tasks.append(r["task_id"])
            sfdc_records.append({"id": r["task_id"], "url": r["url"], "subject": item["title"]})

        email_path = email_drafter.save(meeting_id=meeting_id, email=data["follow_up_email"], to=[])

        _writes_adhoc = _full_salesforce_sync(company, meeting_id, data)

        record = {
            "meeting_id": meeting_id,
            "company_id": company["id"],
            "company_name": name,
            "ad_hoc": True,
            "transcript_source": payload.get("transcript_source") or "uploaded",
            "transcript_turns": len(turns),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": data["summary"],
            "action_items": data["action_items"],
            "meddpicc_signals": data["meddpicc_signals"],
            "competitor_mentions": data["competitor_mentions"],
            "follow_up_email": data["follow_up_email"],
            "salesforce_task_ids": sfdc_tasks,
            "salesforce_tasks": sfdc_records,
            "salesforce_account": _writes_adhoc["account"],
            "salesforce_writes": _writes_adhoc,
            "email_draft_path": str(email_path),
            "company_snapshot": company,
            "meeting_snapshot": meeting,
            "transcript_snapshot": transcript,
        }
        out_dir = settings.runtime_dir / "post_meeting"
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{meeting_id}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        get_es_repo().index_post_meeting(record)

        log.info(
            "post_meeting.ad_hoc.complete",
            meeting_id=meeting_id,
            actions=len(data["action_items"]),
            sfdc_tasks=len(sfdc_tasks),
        )
        return record


def _full_salesforce_sync(company: Dict[str, Any], meeting_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Drive every Salesforce write the post-meeting flow performs:

    1. Resolve Account + Opportunity records (mock)
    2. Create a ContentNote linked to the Opp with the meeting summary + MEDDPICC + actions.
    3. Update MEDDPICC custom fields on the Opportunity (with verbatim quote evidence).
    4. Update primary competitor + competitor history.
    5. Update deal-health score derived from MEDDPICC completeness.
    6. Post a Slack message to the deal-channel via the SF-Slack connector.

    Each write is appended to runtime/salesforce.log with an `_action` tag.
    """
    account = salesforce_mock.get_account(
        company_id=company["id"],
        company_name=company.get("name", ""),
        industry=company.get("industry", ""),
        size=company.get("size", ""),
    )
    opportunity = salesforce_mock.get_opportunity(account_id=account["Id"], company_name=company.get("name", ""))

    note_body = _render_note_body(company, meeting_id, data)
    note = salesforce_mock.create_content_note(
        opportunity_id=opportunity["Id"],
        account_id=account["Id"],
        title=f"FE Copilot brief - {meeting_id}",
        body=note_body,
    )

    meddpicc_update = salesforce_mock.update_opp_meddpicc(
        opportunity_id=opportunity["Id"],
        signals=data.get("meddpicc_signals", []),
    )

    competitors = data.get("competitor_mentions", []) or []
    competitor_update = None
    if competitors:
        competitor_update = salesforce_mock.update_competitor(
            opportunity_id=opportunity["Id"],
            primary=competitors[0].get("competitor", ""),
            others=[c.get("competitor", "") for c in competitors[1:5]],
        )

    unique_categories = len({s.get("category") for s in (data.get("meddpicc_signals") or []) if s.get("category")})
    deal_health = salesforce_mock.update_deal_health(
        opportunity_id=opportunity["Id"],
        score=unique_categories,
        max_score=7,
    )

    slack_post = salesforce_mock.post_to_slack(
        channel=f"#deal-{(company.get('id') or 'account')}",
        opportunity_id=opportunity["Id"],
        text=(
            f"*FE Copilot post-meeting brief*\n"
            f"{(data.get('summary') or '')[:280]}\n\n"
            f"{len(data.get('action_items', []))} action items "
            f"· {unique_categories}/7 MEDDPICC categories captured "
            f"· {len(competitors)} competitor mention(s)"
        ),
        brief_url=note["url"],
    )

    pdf_attach = None
    pdf_path = settings.runtime_dir / "briefs" / f"{meeting_id}.pdf"
    html_path = settings.runtime_dir / "briefs" / f"{meeting_id}.html"
    artifact = pdf_path if pdf_path.exists() else (html_path if html_path.exists() else None)
    if artifact is not None:
        pdf_attach = salesforce_mock.attach_content_document(
            opportunity_id=opportunity["Id"],
            file_path=str(artifact),
            title=f"FE Copilot brief artifact - {meeting_id}",
        )

    return {
        "account": account,
        "opportunity": opportunity,
        "note": note,
        "meddpicc": meddpicc_update,
        "competitor": competitor_update,
        "deal_health": deal_health,
        "slack": slack_post,
        "content_document": pdf_attach,
    }


def _render_note_body(company: Dict[str, Any], meeting_id: str, data: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"# Meeting summary - {company.get('name', '')}")
    lines.append("")
    lines.append(data.get("summary", "") or "")
    lines.append("")
    if data.get("action_items"):
        lines.append("## Action items")
        for a in data["action_items"]:
            due = a.get("due_date") or "TBD"
            impact = a.get("impact") or "med"
            lines.append(f"- **[{impact.upper()}]** {a.get('title')} - owner: {a.get('owner_name')} - due {due}")
            lines.append(f"  > _Source quote_: \"{a.get('source_quote')}\"")
        lines.append("")
    if data.get("meddpicc_signals"):
        lines.append("## MEDDPICC signals")
        for s in data["meddpicc_signals"]:
            lines.append(f"- **{s.get('category')}**: \"{s.get('quote')}\"")
        lines.append("")
    if data.get("competitor_mentions"):
        lines.append("## Competitor mentions")
        for c in data["competitor_mentions"]:
            lines.append(f"- **{c.get('competitor')}**: {c.get('context')}")
        lines.append("")
    email = data.get("follow_up_email") or {}
    if email:
        lines.append("## Follow-up email draft")
        lines.append(f"_Subject:_ {email.get('subject', '')}")
        lines.append("")
        lines.append(email.get("body_markdown", "") or "")
    return "\n".join(lines)
