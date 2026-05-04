"""
filename: proposal_pdf.py
description: Renders Carmen's 1-page customer proposal to PDF via WeasyPrint with Jinja2 templates. Falls back to writing the HTML file when WeasyPrint system libs are missing, so demos never hard-fail. Writes artifacts to runtime/proposals/<meeting_id>-<timestamp>.{pdf,html}.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import contextlib
import io
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE_NAME = "proposal.html"
TEMPLATE_PATH = TEMPLATE_DIR / TEMPLATE_NAME


# ============================================================ Inline template ========


# We write the template lazily on first render so this module ships self-contained
# (the file lives under services/templates/proposal.html alongside brief.html).
_PROPOSAL_TEMPLATE = """<!--
  filename: proposal.html
  description: Jinja2 template for Carmen's 1-page customer proposal PDF (rendered by WeasyPrint). Lochmara primary blue accents on white. US Letter, single page, print-friendly.
  Author: Rodrigo Careaga
  Date: 03-05-2026
-->
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>{{ title }}</title>
  <style>
    @page {
      size: Letter;
      margin: 0.45in 0.5in;
    }
    * { box-sizing: border-box; }
    body {
      font-family: "Inter", -apple-system, "Helvetica Neue", Arial, sans-serif;
      color: #1A1F26;
      font-size: 9pt;
      line-height: 1.35;
      margin: 0;
      padding: 0;
      background: #ffffff;
    }
    .header {
      display: table;
      width: 100%;
      padding: 8pt 10pt;
      border-bottom: 2pt solid #0077CC;
      margin-bottom: 10pt;
    }
    .header .logo-cell {
      display: table-cell;
      width: 28%;
      vertical-align: middle;
      color: #0077CC;
      font-weight: 700;
      font-size: 11pt;
      letter-spacing: 0.5pt;
    }
    .header .title-cell {
      display: table-cell;
      vertical-align: middle;
      text-align: right;
    }
    .header .title-cell h1 {
      margin: 0;
      font-size: 16pt;
      font-weight: 700;
      color: #0A2540;
      line-height: 1.15;
    }
    .header .title-cell .date {
      margin-top: 2pt;
      font-size: 8pt;
      color: #5A6378;
    }
    .summary {
      background: #F0F7FC;
      border-left: 3pt solid #0077CC;
      padding: 8pt 10pt;
      margin-bottom: 10pt;
      font-size: 9.5pt;
      color: #1A2940;
    }
    h2 {
      font-size: 8pt;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.8pt;
      color: #0077CC;
      margin: 8pt 0 4pt 0;
      padding-bottom: 2pt;
      border-bottom: 0.5pt solid #DCE1E8;
    }

    /* Value pillars: 3-column row */
    .pillars { display: table; width: 100%; border-spacing: 6pt 0; margin-left: -6pt; }
    .pillar {
      display: table-cell;
      width: 33.33%;
      vertical-align: top;
      background: #F7FAFC;
      border: 0.5pt solid #DCE1E8;
      border-top: 2pt solid #0077CC;
      padding: 6pt 7pt;
      border-radius: 3pt;
    }
    .pillar .name {
      font-weight: 700;
      font-size: 9pt;
      color: #0A2540;
      margin-bottom: 3pt;
    }
    .pillar .headline {
      font-size: 8pt;
      color: #1A2940;
      margin-bottom: 4pt;
      line-height: 1.3;
    }
    .pillar ul { margin: 0; padding-left: 11pt; }
    .pillar li {
      font-size: 7.5pt;
      color: #2A3541;
      margin-bottom: 2pt;
      line-height: 1.3;
    }
    .pillar li::marker { color: #0077CC; }

    /* Scope: 2 columns */
    .scope { display: table; width: 100%; border-spacing: 6pt 0; margin-left: -6pt; }
    .scope .col {
      display: table-cell;
      width: 50%;
      vertical-align: top;
      padding: 6pt 8pt;
      border-radius: 3pt;
    }
    .scope .in {
      background: rgba(0, 191, 179, 0.08);
      border: 0.5pt solid rgba(0, 191, 179, 0.4);
    }
    .scope .out {
      background: #F7FAFC;
      border: 0.5pt solid #DCE1E8;
    }
    .scope .label {
      font-size: 7.5pt;
      font-weight: 700;
      letter-spacing: 0.5pt;
      text-transform: uppercase;
      margin-bottom: 3pt;
    }
    .scope .in .label { color: #008B82; }
    .scope .out .label { color: #5A6378; }
    .scope ul { margin: 0; padding-left: 11pt; }
    .scope li { font-size: 7.5pt; margin-bottom: 1.5pt; line-height: 1.3; color: #1A1F26; }

    /* Timeline horizontal bar */
    .timeline { display: table; width: 100%; border-spacing: 4pt 0; margin-left: -4pt; }
    .phase {
      display: table-cell;
      vertical-align: top;
      background: #ffffff;
      border: 0.5pt solid #DCE1E8;
      border-top: 3pt solid #0077CC;
      padding: 5pt 6pt;
      border-radius: 3pt;
    }
    .phase .phase-name { font-weight: 700; font-size: 8pt; color: #0A2540; }
    .phase .phase-weeks {
      font-size: 7pt;
      color: #0077CC;
      font-weight: 600;
      margin-bottom: 3pt;
    }
    .phase ul { margin: 0; padding-left: 10pt; }
    .phase li { font-size: 7pt; line-height: 1.25; margin-bottom: 1pt; color: #2A3541; }

    /* Investment block */
    .invest {
      display: table;
      width: 100%;
      background: #F7FAFC;
      border: 0.5pt solid #DCE1E8;
      border-radius: 3pt;
      padding: 6pt 8pt;
    }
    .invest .num-cell {
      display: table-cell;
      width: 33.33%;
      vertical-align: top;
      padding-right: 6pt;
    }
    .invest .num-cell .label {
      font-size: 7pt;
      color: #5A6378;
      text-transform: uppercase;
      letter-spacing: 0.5pt;
      font-weight: 600;
    }
    .invest .num-cell .value {
      font-size: 12pt;
      font-weight: 700;
      color: #0077CC;
      margin-top: 1pt;
    }
    .invest .num-cell .value.muted { color: #8A93A2; font-weight: 600; font-size: 10pt; }
    .invest .notes {
      font-size: 7pt;
      color: #5A6378;
      margin-top: 4pt;
      padding-top: 4pt;
      border-top: 0.5pt dashed #DCE1E8;
    }
    .invest .notes ul { margin: 0; padding-left: 10pt; }
    .invest .notes li { margin-bottom: 1pt; }

    /* Risks + Next steps two-column row */
    .twocol { display: table; width: 100%; border-spacing: 6pt 0; margin-left: -6pt; }
    .twocol .col { display: table-cell; width: 50%; vertical-align: top; }
    .risks li, .nextsteps li { font-size: 7.5pt; margin-bottom: 2pt; line-height: 1.3; }
    .risks li::marker, .nextsteps li::marker { color: #0077CC; }
    .risks .mit { color: #5A6378; font-style: italic; }

    .footer {
      margin-top: 10pt;
      padding-top: 5pt;
      border-top: 0.5pt solid #DCE1E8;
      display: table;
      width: 100%;
      font-size: 7pt;
      color: #8A93A2;
    }
    .footer .text-cell { display: table-cell; vertical-align: middle; }
    .footer .qr-cell {
      display: table-cell;
      vertical-align: middle;
      width: 60pt;
      text-align: right;
    }
    .qr-box {
      display: inline-block;
      width: 36pt;
      height: 36pt;
      border: 0.5pt solid #0077CC;
      background: #F0F7FC;
      color: #0077CC;
      text-align: center;
      font-size: 5.5pt;
      line-height: 36pt;
      letter-spacing: 0.3pt;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="logo-cell">ELASTIC</div>
    <div class="title-cell">
      <h1>{{ title }}</h1>
      <div class="date">Prepared {{ generated_at }}</div>
    </div>
  </div>

  <div class="summary">{{ executive_summary }}</div>

  <h2>Value Pillars</h2>
  <div class="pillars">
    {% for p in value_pillars %}
    <div class="pillar">
      <div class="name">{{ p.name }}</div>
      <div class="headline">{{ p.headline }}</div>
      <ul>
        {% for m in p.metrics %}<li>{{ m }}</li>{% endfor %}
      </ul>
    </div>
    {% endfor %}
  </div>

  <h2>Scope</h2>
  <div class="scope">
    <div class="col in">
      <div class="label">In scope</div>
      <ul>
        {% for s in scope.in_scope %}<li>{{ s }}</li>{% endfor %}
      </ul>
    </div>
    <div class="col out">
      <div class="label">Out of scope</div>
      <ul>
        {% for s in scope.out_of_scope %}<li>{{ s }}</li>{% endfor %}
      </ul>
    </div>
  </div>

  <h2>Timeline</h2>
  <div class="timeline">
    {% for ph in timeline %}
    <div class="phase">
      <div class="phase-weeks">{{ ph.weeks }}</div>
      <div class="phase-name">{{ ph.phase }}</div>
      <ul>
        {% for d in ph.deliverables %}<li>{{ d }}</li>{% endfor %}
      </ul>
    </div>
    {% endfor %}
  </div>

  <h2>Investment</h2>
  <div class="invest">
    <div class="num-cell">
      <div class="label">Elastic Cloud (annual)</div>
      {% if investment.elastic_cloud_annual_usd %}
        <div class="value">${{ "{:,.0f}".format(investment.elastic_cloud_annual_usd) }}</div>
      {% else %}
        <div class="value muted">Sized at POV</div>
      {% endif %}
    </div>
    <div class="num-cell">
      <div class="label">Professional Services</div>
      {% if investment.professional_services_hours %}
        <div class="value">{{ investment.professional_services_hours }} hrs</div>
      {% else %}
        <div class="value muted">Optional</div>
      {% endif %}
    </div>
    <div class="num-cell">
      <div class="label">Free POV (standard offer)</div>
      <div class="value">{{ investment.free_pov_hours }} hrs</div>
    </div>
    {% if investment.notes %}
    <div class="notes">
      <ul>
        {% for n in investment.notes %}<li>{{ n }}</li>{% endfor %}
      </ul>
    </div>
    {% endif %}
  </div>

  <div class="twocol">
    <div class="col risks">
      <h2>Risks</h2>
      <ul>
        {% for r in risks %}
        <li>{{ r.risk }} <span class="mit">Mitigation: {{ r.mitigation }}</span></li>
        {% endfor %}
      </ul>
    </div>
    <div class="col nextsteps">
      <h2>Next Steps</h2>
      <ul>
        {% for n in next_steps %}<li>{{ n }}</li>{% endfor %}
      </ul>
    </div>
  </div>

  <div class="footer">
    <div class="text-cell">
      Elastic Field Engineering. Apache 2.0.
      {% if dashboard_url %}<br/>Customer-fit dashboard: {{ dashboard_url }}{% endif %}
    </div>
    <div class="qr-cell">
      <div class="qr-box">{% if dashboard_url %}QR{% else %}n/a{% endif %}</div>
    </div>
  </div>
</body>
</html>
"""


def _ensure_template() -> None:
    """Write the template to disk if missing. Lets the file be edited externally if desired."""
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    if not TEMPLATE_PATH.exists():
        TEMPLATE_PATH.write_text(_PROPOSAL_TEMPLATE, encoding="utf-8")


@contextlib.contextmanager
def _silence_stdout_stderr():
    """Suppress noisy library banners (WeasyPrint missing-libs message) without losing real exceptions."""
    saved_out, saved_err = sys.stdout, sys.stderr
    devnull_out, devnull_err = io.StringIO(), io.StringIO()
    try:
        sys.stdout, sys.stderr = devnull_out, devnull_err
        yield
    finally:
        sys.stdout, sys.stderr = saved_out, saved_err


def _env() -> Environment:
    _ensure_template()
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_html(
    *,
    proposal: Dict[str, Any],
    dashboard_url: Optional[str] = "",
) -> str:
    template = _env().get_template(TEMPLATE_NAME)
    return template.render(
        title=proposal.get("title", "Proposal"),
        executive_summary=proposal.get("executive_summary", ""),
        value_pillars=proposal.get("value_pillars") or [],
        scope=proposal.get("scope") or {"in_scope": [], "out_of_scope": []},
        timeline=proposal.get("timeline") or [],
        investment=proposal.get("investment")
        or {
            "elastic_cloud_annual_usd": None,
            "professional_services_hours": None,
            "free_pov_hours": 60,
            "notes": [],
        },
        risks=proposal.get("risks") or [],
        next_steps=proposal.get("next_steps") or [],
        dashboard_url=dashboard_url or "",
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )


def render_proposal_pdf(
    *,
    meeting_id: str,
    proposal: Dict[str, Any],
    dashboard_url: Optional[str] = "",
) -> Path:
    """Render a one-page proposal HTML and PDF. Returns the artifact path.

    Always writes the HTML alongside; if WeasyPrint succeeds, returns the .pdf path,
    otherwise falls back to the .html path so demos never hard-fail.
    """
    out_dir = settings.runtime_dir / "proposals"
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    base = out_dir / f"{meeting_id}-{ts}"
    pdf_path = base.with_suffix(".pdf")
    html_path = base.with_suffix(".html")

    html = render_html(proposal=proposal, dashboard_url=dashboard_url)
    html_path.write_text(html, encoding="utf-8")

    try:
        with _silence_stdout_stderr():
            from weasyprint import HTML  # type: ignore

            HTML(string=html).write_pdf(str(pdf_path))
        log.info("proposal_pdf.rendered", path=str(pdf_path))
        return pdf_path
    except Exception as exc:
        log.warning("proposal_pdf.fallback_to_html", reason=str(exc))
        return html_path
