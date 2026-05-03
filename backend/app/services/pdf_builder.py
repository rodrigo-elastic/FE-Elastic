"""
filename: pdf_builder.py
description: Renders the Account Brief HTML via Jinja2, then to PDF via WeasyPrint. Falls back to writing the HTML file when WeasyPrint system libs are missing, so demos never hard-fail.
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
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings
from app.utils.logging import get_logger

log = get_logger(__name__)


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

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)


def render_html(*, company: Dict[str, Any], meeting: Dict[str, Any], brief: Dict[str, Any]) -> str:
    template = _env.get_template("brief.html")
    return template.render(
        company=company,
        meeting=meeting,
        brief=brief,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )


def render_pdf(
    *, company: Dict[str, Any], meeting: Dict[str, Any], brief: Dict[str, Any]
) -> Path:
    """Render the brief and return a Path to the artifact (PDF preferred, HTML fallback)."""
    html = render_html(company=company, meeting=meeting, brief=brief)
    out_dir = settings.runtime_dir / "briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    base = out_dir / f"{meeting['id']}"
    pdf_path = base.with_suffix(".pdf")
    html_path = base.with_suffix(".html")

    # Always keep an HTML copy on disk; useful for debugging and demo screenshots.
    html_path.write_text(html, encoding="utf-8")

    try:
        with _silence_stdout_stderr():
            from weasyprint import HTML  # type: ignore

            HTML(string=html).write_pdf(str(pdf_path))
        log.info("pdf.rendered", path=str(pdf_path))
        return pdf_path
    except Exception as exc:
        # WeasyPrint may fail if Pango/Cairo aren't installed on the host; degrade to HTML.
        log.warning("pdf.fallback_to_html", reason=str(exc))
        return html_path
