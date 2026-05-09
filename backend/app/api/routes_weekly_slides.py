"""
filename: routes_weekly_slides.py
description: Weekly customer status slide deck. Aggregates post-meeting records
for a given week, groups by company, and uses Claude to synthesize slide content
matching the Field Engineering weekly standup format (Actions, Renewals, Cases,
Consumption, Feature Adoption, Risks/Notes/Top of mind).
date: 09-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import settings
from app.integrations.claude_client import get_elastic_service
from app.utils.logging import get_logger

log = get_logger(__name__)

router = APIRouter(prefix="/weekly-slides", tags=["weekly-slides"])


# ============================================================ Pydantic output schema =


class SlideRenewal(BaseModel):
    label: str = ""
    notes: str = ""
    risk: str = ""
    amount: str = ""
    date: str = ""


class WeeklySlideOut(BaseModel):
    use_case: str = ""
    temperature: str = "stable"
    temperature_reason: str = ""
    current_actions: List[str] = Field(default_factory=list)
    upcoming_actions: List[str] = Field(default_factory=list)
    renewals: List[SlideRenewal] = Field(default_factory=list)
    cases: List[str] = Field(default_factory=list)
    consumption: str = ""
    wow_pct: str = "N/A"
    feature_adoption: List[str] = Field(default_factory=list)
    risks_notes: List[str] = Field(default_factory=list)


_SLIDE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "use_case": {"type": "string"},
        "temperature": {"type": "string", "enum": ["churn", "stable", "growth"]},
        "temperature_reason": {"type": "string"},
        "current_actions": {"type": "array", "items": {"type": "string"}},
        "upcoming_actions": {"type": "array", "items": {"type": "string"}},
        "renewals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "notes": {"type": "string"},
                    "risk": {"type": "string"},
                    "amount": {"type": "string"},
                    "date": {"type": "string"},
                },
                "required": ["label"],
            },
        },
        "cases": {"type": "array", "items": {"type": "string"}},
        "consumption": {"type": "string"},
        "wow_pct": {"type": "string"},
        "feature_adoption": {"type": "array", "items": {"type": "string"}},
        "risks_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "use_case", "temperature", "current_actions",
        "upcoming_actions", "consumption", "risks_notes",
    ],
}


# ============================================================ Helpers ===============


def _week_bounds(week_start_str: Optional[str]):
    if week_start_str:
        try:
            d = date.fromisoformat(week_start_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid week_start. Use YYYY-MM-DD.")
    else:
        today = date.today()
        d = today - timedelta(days=today.weekday())
    start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    return start, start + timedelta(days=7)


def _load_post_meetings(demo_mode: bool, start: datetime, end: datetime) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    seen: set = set()

    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo
        es = get_es_repo()
        if es.available:
            for rec in es.list_post_meetings(limit=500):
                mid = rec.get("meeting_id", "")
                if mid in seen:
                    continue
                if not demo_mode:
                    ga = rec.get("generated_at", "")
                    if not ga:
                        continue
                    try:
                        ts = datetime.fromisoformat(ga.replace("Z", "+00:00"))
                        if not (start <= ts < end):
                            continue
                    except Exception:
                        continue
                records.append(rec)
                seen.add(mid)
    except Exception as exc:
        log.warning("weekly_slides.es_load_failed", error=str(exc))

    post_dir = settings.runtime_dir / "post_meeting"
    if post_dir.exists():
        for p in sorted(post_dir.glob("*.json")):
            try:
                rec = json.loads(p.read_text(encoding="utf-8"))
                mid = rec.get("meeting_id", p.stem)
                if mid in seen:
                    continue
                if not demo_mode:
                    ga = rec.get("generated_at", "")
                    if not ga:
                        continue
                    ts = datetime.fromisoformat(ga.replace("Z", "+00:00"))
                    if not (start <= ts < end):
                        continue
                records.append(rec)
                seen.add(mid)
            except Exception:
                pass

    return records


def _group_by_company(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for rec in records:
        key = (rec.get("company_name") or rec.get("company_id") or "Unknown").strip()
        grouped.setdefault(key, []).append(rec)
    return grouped


def _extract_sf(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    for rec in sorted(records, key=lambda r: r.get("generated_at", ""), reverse=True):
        sw = rec.get("salesforce_writes") or {}
        if sw:
            return sw
    return {}


def _build_slide(company_name: str, records: List[Dict[str, Any]], sf: Dict[str, Any]) -> Dict[str, Any]:
    summaries = [r.get("summary", "") for r in records if r.get("summary")]
    all_actions: List[Dict[str, Any]] = []
    for rec in records:
        all_actions.extend(rec.get("action_items") or [])
    meddpicc: List[Dict[str, Any]] = []
    for rec in records:
        meddpicc.extend(rec.get("meddpicc_signals") or [])

    opp = sf.get("opportunity") or {}
    account = sf.get("account") or {}

    sf_ctx_lines = []
    if account.get("Name"):
        sf_ctx_lines.append(f"Account: {account['Name']}, Industry: {account.get('Industry', 'N/A')}")
    if opp.get("Name"):
        amt = opp.get("Amount") or 0
        sf_ctx_lines.append(
            f"Opportunity: {opp['Name']}, Stage: {opp.get('StageName', '')}, "
            f"Amount: ${amt:,}, Close: {opp.get('CloseDate', '')}"
        )
    sf_ctx = "\n".join(sf_ctx_lines) or "Not available."

    ai_lines = "\n".join(
        f"- {ai.get('title', '')} (owner: {ai.get('owner_name', 'TBD')}, "
        f"due: {ai.get('due_date', 'TBD')}, impact: {ai.get('impact', 'med')})"
        for ai in all_actions
    ) or "No action items."

    meddpicc_lines = "\n".join(
        f"- [{m.get('category', '')}] {m.get('note', '') or m.get('quote', '')[:120]}"
        for m in meddpicc[:8]
    ) or "No MEDDPICC signals."

    summary_text = "\n\n---\n\n".join(summaries) or "No meeting summaries available."

    system = (
        "You are a Field Engineering weekly standup assistant at Elastic. "
        "You produce structured, concise, executive-ready customer status summaries. "
        "Be specific - use real names, amounts, dates from the input data. "
        "Never invent facts not in the input. If data is missing, say so briefly."
    )

    user = f"""Generate a weekly customer status slide for the FE team standup.

Company: {company_name}
Salesforce: {sf_ctx}

Meeting summaries this week:
{summary_text}

Action items:
{ai_lines}

MEDDPICC signals:
{meddpicc_lines}

Return a JSON object with these exact keys:
{{
  "use_case": "Short description of main Elastic use cases (e.g. 'Security + Observability')",
  "temperature": "churn|stable|growth",
  "temperature_reason": "One sentence explaining the account health signal.",
  "current_actions": ["2-5 in-flight action items. Include owner. One concise line each."],
  "upcoming_actions": ["1-3 planned future actions."],
  "renewals": [{{"label": "Renewal name/description", "notes": "Brief context", "risk": "low|med|high", "amount": "$amount", "date": "YYYY-MM-DD"}}],
  "cases": ["L2 - Title - Status (use format from data if available)"],
  "consumption": "1-2 sentence summary of consumption trend and account health.",
  "wow_pct": "??% or actual week-over-week % if inferable from data",
  "feature_adoption": ["Elastic feature being actively adopted - max 4"],
  "risks_notes": ["Key risk, note, or top-of-mind item - 2-4 items"]
}}

Rules:
- temperature: 'growth' if positive deal signals or expansion; 'churn' if risk, disengagement, or renewal concerns; 'stable' otherwise.
- current_actions: in-flight or due soon. upcoming_actions: planned for future meetings/sprints.
- cases: [] if no case data available.
- renewals: use opportunity data; [] if none.
- Respond with ONLY the JSON object. No markdown. No explanation."""

    mock_payload: Dict[str, Any] = {
        "use_case": "Security + Observability",
        "temperature": "stable",
        "temperature_reason": "Active engagement across multiple workstreams. No major risk signals.",
        "current_actions": [
            f"Follow up on open action items from {company_name} meetings",
            "Send meeting summary and next steps",
        ],
        "upcoming_actions": ["Schedule next business review"],
        "renewals": [],
        "cases": [],
        "consumption": "Stable consumption. On-prem deployment limits telemetry visibility.",
        "wow_pct": "N/A",
        "feature_adoption": ["Elastic Stack", "Agent Builder", "Observability"],
        "risks_notes": ["Review pending action items and ownership assignments"],
    }

    model_name = settings.model_for("post_meeting")

    # Always use the Elastic inference connector - customer data must not leave
    # the Elastic infrastructure. strict=True blocks all fallback paths to the
    # direct Anthropic API.
    try:
        svc = get_elastic_service()
        result: WeeklySlideOut = svc.call_structured(
            system=system,
            user=user,
            schema=_SLIDE_SCHEMA,
            output_model=WeeklySlideOut,
            model=model_name,
            max_tokens=1500,
            effort="high",
            thinking_adaptive=True,
            cache_system=True,
            mock_payload=mock_payload,
            audit_meta={"agent": "weekly_slides", "company": company_name},
            strict=True,
        )
        slide = result.model_dump()
    except RuntimeError as exc:
        # get_elastic_service() raised - Kibana not configured or strict block triggered.
        log.warning("weekly_slides.elastic_required", company=company_name, error=str(exc)[:200])
        raise
    except Exception as exc:
        log.warning("weekly_slides.claude_failed", company=company_name, error=str(exc)[:200])
        slide = mock_payload.copy()

    arr = opp.get("Amount") or 0
    slide["company_name"] = company_name
    slide["arr"] = f"${arr:,}" if arr else ""
    slide["cloud_arr"] = ""
    slide["training_services"] = ""
    slide["renewable_base"] = ""
    slide["open_ne"] = ""
    slide["salesforce_url"] = account.get("Url") or opp.get("Url") or ""
    slide["meeting_count"] = len(records)
    slide["meeting_ids"] = [r.get("meeting_id", "") for r in records]
    slide["updated"] = date.today().isoformat()
    return slide


# ============================================================ PPTX builder ==========


def _build_pptx(slide_data: Dict[str, Any]) -> "Path":
    """Generate a .pptx file from slide_data using python-pptx.

    Layout matches the Field Engineering standup slide format:
    header (logo, ARR, company, temp) | 4-col body (actions, renewals, cases, consumption)
    | 2-col bottom (features, risks) | footer icons.
    """
    try:
        from pptx import Presentation  # type: ignore[import]
        from pptx.dml.color import RGBColor  # type: ignore[import]
        from pptx.enum.text import PP_ALIGN  # type: ignore[import]
        from pptx.util import Inches, Pt  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError("python-pptx required: pip install python-pptx") from exc

    # ── Color palette ──────────────────────────────────────────────
    RED   = RGBColor(0xE8, 0x4B, 0x37)
    NAVY  = RGBColor(0x1A, 0x2D, 0x5A)
    ORNGE = RGBColor(0xE0, 0x64, 0x40)
    TEAL  = RGBColor(0x00, 0xB4, 0xA2)
    GOLD  = RGBColor(0xD4, 0xA0, 0x17)
    WHITE = RGBColor(0xFF, 0xFF, 0xFF)
    LGRAY = RGBColor(0xF2, 0xF2, 0xF2)
    DGRAY = RGBColor(0xD0, 0xD0, 0xD0)
    DTEXT = RGBColor(0x22, 0x22, 0x22)
    MUTED = RGBColor(0x99, 0x99, 0x99)

    prs = Presentation()
    prs.slide_width  = Inches(13.33)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank

    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = WHITE

    I = Inches

    # ── Helpers ────────────────────────────────────────────────────

    def _rect(l, t, w, h, bg, border_color=None):
        s = slide.shapes.add_shape(1, I(l), I(t), I(w), I(h))
        s.fill.solid()
        s.fill.fore_color.rgb = bg
        if border_color:
            s.line.color.rgb = border_color
            s.line.width = Pt(0.5)
        else:
            s.line.fill.background()
        return s

    def _textbox(l, t, w, h, lines, sizes=None, bolds=None, colors=None, aligns=None, italics=None):
        box = slide.shapes.add_textbox(I(l), I(t), I(w), I(h))
        tf = box.text_frame
        tf.word_wrap = True
        for i, text in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_before = Pt(1)
            p.alignment = (aligns[i] if aligns else PP_ALIGN.LEFT)
            run = p.add_run()
            run.text = str(text)
            run.font.size = Pt((sizes[i] if sizes else 7.5) or 7.5)
            run.font.bold  = bool((bolds[i]   if bolds   else False))
            run.font.italic = bool((italics[i] if italics else False))
            run.font.color.rgb = (colors[i] if colors else DTEXT) or DTEXT
        return box

    def _section(l, t, w, h, title, bg, items, title_underline=False):
        """Colored header + light-gray body + content text."""
        HDR = 0.28
        # header shape
        hdr = slide.shapes.add_shape(1, I(l), I(t), I(w), I(HDR))
        hdr.fill.solid()
        hdr.fill.fore_color.rgb = bg
        hdr.line.fill.background()
        tf = hdr.text_frame
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        run = tf.paragraphs[0].add_run()
        run.text = title
        run.font.size = Pt(9)
        run.font.bold = True
        run.font.underline = title_underline
        run.font.color.rgb = WHITE
        # body bg
        _rect(l, t + HDR, w, h - HDR, LGRAY)
        # content
        if items:
            _textbox(
                l + 0.07, t + HDR + 0.05, w - 0.14, h - HDR - 0.1,
                [x[0] for x in items],
                sizes=[x[1] for x in items],
                bolds=[x[2] for x in items],
                colors=[x[3] for x in items],
            )

    def _pill_shape(l, t, w, h, text, bg, fg=WHITE, size=7.5):
        s = slide.shapes.add_shape(5, I(l), I(t), I(w), I(h))  # 5 = rounded rect
        s.fill.solid()
        s.fill.fore_color.rgb = bg
        s.line.fill.background()
        tf = s.text_frame
        tf.paragraphs[0].alignment = PP_ALIGN.CENTER
        run = tf.paragraphs[0].add_run()
        run.text = text
        run.font.size = Pt(size)
        run.font.bold = True
        run.font.color.rgb = fg

    # ── Layout constants ───────────────────────────────────────────
    H_HDR  = 1.45   # header height
    BODY_T = H_HDR
    BODY_H = 3.8
    BTM_T  = BODY_T + BODY_H   # 5.25
    BTM_H  = 7.0 - BTM_T       # 1.75
    COL_W  = 13.33 / 4         # 3.3325 per body column
    FEAT_W = 4.44
    RISK_W = 13.33 - FEAT_W

    # ── HEADER ─────────────────────────────────────────────────────
    # Logo box (border)
    _rect(0.05, 0.05, 1.7, H_HDR - 0.1, WHITE, border_color=DGRAY)
    _textbox(0.05, 0.45, 1.7, 0.55, ["Company logo"], sizes=[8], italics=[True], colors=[MUTED],
             aligns=[PP_ALIGN.CENTER])

    # ARR pills
    arr_txt  = f"ARR:  {slide_data.get('arr') or '-'}"
    carr_txt = f"Cloud ARR:  {slide_data.get('cloud_arr') or '-'}"
    _rect(1.82, 0.15, 1.2, 0.27, DGRAY)
    _textbox(1.87, 0.18, 1.1, 0.22, [arr_txt], sizes=[7])
    _rect(1.82, 0.49, 1.2, 0.27, DGRAY)
    _textbox(1.87, 0.52, 1.1, 0.22, [carr_txt], sizes=[7])

    # Company name + use case + updated
    cx, cw = 3.1, 5.5
    _textbox(cx, 0.05, cw, 0.75, [slide_data.get("company_name", "")],
             sizes=[20], bolds=[True], aligns=[PP_ALIGN.CENTER])
    _textbox(cx, 0.78, cw, 0.38, [slide_data.get("use_case", "")],
             sizes=[11], aligns=[PP_ALIGN.CENTER])
    _textbox(cx, 1.13, cw, 0.28, [f"Updated: {slide_data.get('updated', '')}"],
             sizes=[8], italics=[True], colors=[MUTED], aligns=[PP_ALIGN.CENTER])

    # Meta pills (T/S, RB, N&E)
    mx = 8.72
    for row_i, (label, val) in enumerate([
        ("Training/Services:", slide_data.get("training_services") or "-"),
        ("Renewable Base:", slide_data.get("renewable_base") or "-"),
        ("Open N&E:", slide_data.get("open_ne") or "-"),
    ]):
        ty = 0.1 + row_i * 0.38
        _rect(mx, ty, 1.82, 0.28, DGRAY)
        _textbox(mx + 0.05, ty + 0.04, 1.72, 0.2, [f"{label} {val}"], sizes=[7])

    # Temperature box
    tx = 10.62
    _rect(tx, 0, 2.71, H_HDR, WHITE)
    # header bar
    s = slide.shapes.add_shape(1, I(tx), I(0), I(2.71), I(0.32))
    s.fill.solid(); s.fill.fore_color.rgb = NAVY; s.line.fill.background()
    tf = s.text_frame
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    run = tf.paragraphs[0].add_run()
    run.text = "Potential / Temperature"
    run.font.size = Pt(9); run.font.bold = True; run.font.color.rgb = WHITE
    # arrow
    _textbox(tx, 0.33, 2.71, 0.3, ["▼"], sizes=[15], colors=[NAVY], aligns=[PP_ALIGN.CENTER])
    # pills
    temp = (slide_data.get("temperature") or "stable").lower()
    pill_data = [
        ("Churn",  RGBColor(0xE8, 0x4B, 0x37) if temp == "churn"  else RGBColor(0xF8, 0xC8, 0xC2), temp == "churn"),
        ("Stable", RGBColor(0xF1, 0xA7, 0x30) if temp == "stable" else RGBColor(0xF8, 0xE8, 0xC8), temp == "stable"),
        ("Growth", RGBColor(0x3C, 0xB4, 0x4B) if temp == "growth" else RGBColor(0xC8, 0xEC, 0xD0), temp == "growth"),
    ]
    for pi, (lbl, bg, active) in enumerate(pill_data):
        _pill_shape(tx + 0.05 + pi * 0.88, 0.72, 0.82, 0.3, lbl, bg,
                    fg=WHITE if active else DTEXT, size=8)
    reason = (slide_data.get("temperature_reason") or "")[:90]
    if reason:
        _textbox(tx + 0.05, 1.07, 2.61, 0.36, [reason], sizes=[6.5], italics=[True],
                 colors=[MUTED], aligns=[PP_ALIGN.CENTER])

    # ── BODY ROW ───────────────────────────────────────────────────
    # Col 1: Actions
    current  = slide_data.get("current_actions")  or []
    upcoming = slide_data.get("upcoming_actions") or []
    act_items: List[tuple] = []
    if current:
        act_items.append(("Current Actions", 8, True, DTEXT))
        act_items += [(f"  {a}", 7.5, False, DTEXT) for a in current[:4]]
    if upcoming:
        act_items.append(("Upcoming actions", 8, True, DTEXT))
        act_items += [(f"  {a}", 7.5, False, DTEXT) for a in upcoming[:3]]
    if not act_items:
        act_items = [("No actions recorded.", 7.5, False, MUTED)]
    _section(0, BODY_T, COL_W, BODY_H, "Current and upcoming actions", RED, act_items)

    # Col 2: Renewals
    renewals = slide_data.get("renewals") or []
    ren_items: List[tuple] = []
    for r in renewals[:3]:
        lbl  = r.get("label") or ""
        amt  = r.get("amount") or ""
        dt   = r.get("date") or ""
        notes = r.get("notes") or ""
        risk  = r.get("risk") or ""
        line  = f"- {lbl}" + (f" - {amt}" if amt else "") + (f", {dt}" if dt else "")
        ren_items.append((line, 7.5, True, DTEXT))
        if notes: ren_items.append((f"  Notes: {notes}", 7, False, DTEXT))
        if risk:  ren_items.append((f"  Risk: {risk}", 7, False, DTEXT))
    if not ren_items:
        ren_items = [("No renewals on record.", 7.5, False, MUTED)]
    _section(COL_W, BODY_T, COL_W, BODY_H, "Renewals", NAVY, ren_items)

    # Col 3: Cases
    cases = slide_data.get("cases") or []
    case_items: List[tuple] = [(f"- {c}", 7.5, False, DTEXT) for c in cases[:5]]
    if not case_items:
        case_items = [("No open cases.", 7.5, False, MUTED)]
    _section(COL_W * 2, BODY_T, COL_W, BODY_H, "Cases", ORNGE, case_items)

    # Col 4: Consumption
    wow  = slide_data.get("wow_pct") or "N/A"
    cons = (slide_data.get("consumption") or "")[:260]
    cons_items: List[tuple] = [
        (f"WoW: {wow}", 9, True, DTEXT),
        ("", 4, False, DTEXT),
        (cons, 7.5, False, DTEXT),
    ]
    _section(COL_W * 3, BODY_T, COL_W, BODY_H, "Consumption", TEAL, cons_items,
             title_underline=True)

    # ── BOTTOM ROW ─────────────────────────────────────────────────
    features = slide_data.get("feature_adoption") or []
    feat_items: List[tuple] = [(f"Feature {i+1}: {f}", 7.5, False, DTEXT) for i, f in enumerate(features[:4])]
    if not feat_items:
        feat_items = [("No feature data.", 7.5, False, MUTED)]
    _section(0, BTM_T, FEAT_W, BTM_H, "Feature Adoption", RED, feat_items)

    risks = slide_data.get("risks_notes") or []
    risk_items: List[tuple] = [(f"- {r}", 7.5, False, DTEXT) for r in risks[:4]]
    if not risk_items:
        risk_items = [("None noted.", 7.5, False, MUTED)]
    _section(FEAT_W, BTM_T, RISK_W, BTM_H, "Risks / Notes / Top of mind", GOLD, risk_items)

    # ── FOOTER ─────────────────────────────────────────────────────
    _rect(0, 7.0, 13.33, 0.5, LGRAY)
    footer = "  [Salesforce]    [Consumption]    [Contacts]    [LinkedIn]    [Org chart]    [GDrive]    [elastic]"
    _textbox(0.5, 7.07, 12.33, 0.38, [footer], sizes=[7.5], colors=[MUTED])

    # ── Save ───────────────────────────────────────────────────────
    slides_dir = settings.runtime_dir / "slides"
    slides_dir.mkdir(parents=True, exist_ok=True)
    slug = "".join(c if c.isalnum() or c in "-_" else "_" for c in (slide_data.get("company_name") or "slide"))
    fname = f"{slug}_{(slide_data.get('updated') or date.today().isoformat()).replace('-', '')}.pptx"
    out = slides_dir / fname
    prs.save(str(out))
    log.info("weekly_slides.pptx_saved", path=str(out))
    return out


# ============================================================ Slack upload ==========


def _slack_send_slide(pptx_path: "Path", company_name: str, channel: str, pptx_url: str) -> Dict[str, Any]:
    """Upload PPTX to Slack via bot token, or fall back to webhook message with link."""
    bot_token = settings.slack_bot_token.strip()
    webhook   = settings.slack_webhook_url.strip()

    # ── Bot token path: actual file upload ──────────────────────────
    if bot_token:
        try:
            with pptx_path.open("rb") as fh:
                resp = httpx.post(
                    "https://slack.com/api/files.upload",
                    headers={"Authorization": f"Bearer {bot_token}"},
                    data={
                        "channels": channel,
                        "filename": pptx_path.name,
                        "initial_comment": f":bar_chart: *{company_name}* - Weekly status slide",
                    },
                    files={"file": (pptx_path.name, fh,
                                    "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
                    timeout=30.0,
                )
            data = resp.json()
            if data.get("ok"):
                log.info("weekly_slides.slack_uploaded", channel=channel, file=pptx_path.name)
                return {"ok": True, "method": "upload", "channel": channel,
                        "slack_url": data.get("file", {}).get("permalink", "")}
            log.warning("weekly_slides.slack_upload_failed", error=data.get("error"))
        except Exception as exc:
            log.warning("weekly_slides.slack_upload_error", error=str(exc)[:200])

    # ── Webhook fallback: post message with download link ───────────
    if webhook:
        try:
            msg = {
                "text": f":bar_chart: *{company_name}* - Weekly status slide ready",
                "attachments": [{
                    "color": "#00B4A2",
                    "text": f"<{pptx_url}|Download PPTX> | _{pptx_path.name}_",
                }],
            }
            resp = httpx.post(webhook, json=msg, timeout=10.0)
            if resp.status_code == 200:
                log.info("weekly_slides.slack_webhook_sent", channel=channel)
                return {"ok": True, "method": "webhook", "channel": channel, "slack_url": ""}
        except Exception as exc:
            log.warning("weekly_slides.slack_webhook_error", error=str(exc)[:200])

    return {"ok": False, "method": "none", "channel": channel, "error": "No Slack credentials configured."}


# ============================================================ Endpoints =============


@router.get("/download/{filename}")
def download_slide(filename: str):
    """Serve a generated PPTX file."""
    from fastapi.responses import FileResponse

    safe = "".join(c for c in filename if c.isalnum() or c in "-_.")
    path = settings.runtime_dir / "slides" / safe
    if not path.exists() or path.suffix != ".pptx":
        raise HTTPException(status_code=404, detail="Slide not found.")
    return FileResponse(
        str(path),
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=safe,
    )


@router.post("/from-meeting/{meeting_id}")
def slide_from_meeting(meeting_id: str) -> Dict[str, Any]:
    """Generate a PPTX customer status slide from a single post-meeting record
    and send it to the configured Slack channel.

    Uses the Elastic inference connector (strict mode - customer data never
    leaves Elastic infrastructure). Falls back to mock content when in demo/offline mode.
    """
    # ── Load the post-meeting record ────────────────────────────────
    rec: Optional[Dict[str, Any]] = None

    try:
        from app.repositories.elasticsearch_repo import get_repo as get_es_repo
        es = get_es_repo()
        if es.available:
            rec = es.get_post_meeting(meeting_id)
    except Exception:
        pass

    if rec is None:
        post_path = settings.runtime_dir / "post_meeting" / f"{meeting_id}.json"
        if post_path.exists():
            try:
                rec = json.loads(post_path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise HTTPException(status_code=500, detail=f"Failed to read post-meeting: {exc}")

    if rec is None:
        raise HTTPException(status_code=404, detail=f"No post-meeting record found for meeting {meeting_id}.")

    company_name = (rec.get("company_name") or rec.get("company_id") or "Unknown").strip()
    sf = rec.get("salesforce_writes") or {}

    # ── Generate slide content via Elastic Claude ───────────────────
    try:
        slide_data = _build_slide(company_name, [rec], sf)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Elastic inference connector required. {exc}",
        )

    # ── Build PPTX ─────────────────────────────────────────────────
    try:
        pptx_path = _build_pptx(slide_data)
    except Exception as exc:
        log.warning("weekly_slides.pptx_failed", meeting_id=meeting_id, error=str(exc)[:200])
        raise HTTPException(status_code=500, detail=f"PPTX generation failed: {exc}")

    # ── Resolve download URL ────────────────────────────────────────
    from app.api.routes_workflow_settings import _load_settings as _load_wf_settings
    try:
        wf = _load_wf_settings()
        slack_channel = wf.get("slack_channel") or "#fe-copilot-briefs"
    except Exception:
        slack_channel = "#fe-copilot-briefs"

    backend_base = settings.__dict__.get("backend_base_url") or "https://fe-c85291a2a8b144188ee6be1078e79a95.ecs.us-east-1.on.aws"
    pptx_url = f"{backend_base}/api/v1/weekly-slides/download/{pptx_path.name}"

    # ── Send to Slack ───────────────────────────────────────────────
    slack_result = _slack_send_slide(pptx_path, company_name, slack_channel, pptx_url)

    log.info("weekly_slides.from_meeting_done",
             meeting_id=meeting_id, company=company_name,
             slack_ok=slack_result.get("ok"))

    return {
        "ok": True,
        "company_name": company_name,
        "meeting_id": meeting_id,
        "slide_name": pptx_path.name,
        "pptx_url": pptx_url,
        "slack": slack_result,
        "slack_channel": slack_channel,
    }


@router.get("")
def get_weekly_slides(
    week_start: Optional[str] = Query(None, description="Monday YYYY-MM-DD. Defaults to current week."),
    demo: bool = Query(False, description="Use all available post-meetings regardless of date."),
) -> Dict[str, Any]:
    """Generate weekly customer status slides from post-meeting records.

    Groups meetings by company, calls Claude to synthesize slide content
    (actions, renewals, cases, consumption, features, risks/notes).
    Pass demo=true to include all historical meetings when the current week has none.
    """
    start, end = _week_bounds(week_start)
    records = _load_post_meetings(demo, start, end)

    if not records:
        return {
            "ok": True,
            "week_start": start.date().isoformat(),
            "week_end": (end - timedelta(days=1)).date().isoformat(),
            "slides": [],
            "companies": 0,
            "meetings": 0,
            "demo": demo,
        }

    grouped = _group_by_company(records)
    slides = []
    for company_name, company_records in grouped.items():
        sf = _extract_sf(company_records)
        try:
            slide = _build_slide(company_name, company_records, sf)
        except RuntimeError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Elastic inference connector required for customer data. {exc}",
            )
        slides.append(slide)

    return {
        "ok": True,
        "week_start": start.date().isoformat(),
        "week_end": (end - timedelta(days=1)).date().isoformat(),
        "slides": slides,
        "companies": len(slides),
        "meetings": len(records),
        "demo": demo,
    }
