"""
filename: test_pdf_builder.py
description: Test the brief HTML rendering. PDF generation is best-effort and tested only when WeasyPrint is importable.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from app.services import pdf_builder


def _fixtures():
    company = {
        "id": "revolut",
        "name": "Revolut",
        "industry": "Manufacturing",
        "size": "Mid-Market 1k-5k",
        "tech_stack": {"observability": ["Datadog"], "search": [], "cloud": ["AWS"], "other": []},
    }
    meeting = {
        "id": "revolut-mtg-001",
        "title": "Acme x Elastic discovery",
        "start_time": "2026-05-03T10:00:00+00:00",
    }
    brief = {
        "headline": "Frame consolidation against the August 15 Datadog renewal.",
        "sections": [
            {"heading": "Why now", "bullets": ["renewal date locks in Q3", "outage created air cover"]},
        ],
    }
    return company, meeting, brief


def test_render_html_includes_company_and_headline():
    company, meeting, brief = _fixtures()
    html = pdf_builder.render_html(company=company, meeting=meeting, brief=brief)
    assert "Revolut" in html
    assert brief["headline"] in html
    assert "renewal date locks in Q3" in html


def test_render_pdf_writes_artifact():
    company, meeting, brief = _fixtures()
    path = pdf_builder.render_pdf(company=company, meeting=meeting, brief=brief)
    assert path.exists()
    assert path.suffix in {".pdf", ".html"}
