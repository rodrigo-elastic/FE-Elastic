"""
filename: test_synthetic.py
description: Validates the synthetic data generator output: counts, shape, and links.
date: 02-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import json
from pathlib import Path

import pytest

from scripts.generate_synthetic_data import OUTPUT_DIR, generate


@pytest.fixture(scope="module", autouse=True)
def _generated():
    return generate(seed=42, num_companies=3)


def _load(name: str):
    return json.loads((OUTPUT_DIR / f"{name}.json").read_text(encoding="utf-8"))


def test_companies_shape():
    data = _load("companies")
    assert len(data) == 3
    required = {"id", "name", "industry", "size", "tech_stack", "description"}
    for c in data:
        assert required.issubset(c.keys())


def test_news_count_and_links():
    news = _load("news")
    assert len(news) == 9  # 3 per company
    company_ids = {c["id"] for c in _load("companies")}
    assert {n["company_id"] for n in news}.issubset(company_ids)
    for n in news:
        assert "published_at" in n and "summary" in n


def test_meetings_count_and_per_company():
    meetings = _load("meetings")
    assert len(meetings) == 9  # 3 per company
    by_company = {}
    for m in meetings:
        by_company.setdefault(m["company_id"], []).append(m)
    assert all(len(v) == 3 for v in by_company.values())


def test_transcripts_link_to_past_meetings_and_have_turns():
    transcripts = _load("transcripts")
    meetings = {m["id"]: m for m in _load("meetings")}
    assert len(transcripts) == 6  # 2 per company
    for t in transcripts:
        assert t["meeting_id"] in meetings
        assert len(t["turns"]) >= 8


def test_tickets_count_and_priority():
    tickets = _load("tickets")
    assert len(tickets) == 9
    valid_statuses = {"Open", "In Progress", "Resolved"}
    valid_priorities = {"P1", "P2", "P3"}
    for t in tickets:
        assert t["status"] in valid_statuses
        assert t["priority"] in valid_priorities


def test_calendar_only_upcoming():
    calendar = _load("calendar")
    assert len(calendar) == 3  # one upcoming per company
    meeting_ids = {m["id"] for m in _load("meetings")}
    for ev in calendar:
        assert ev["meeting_id"] in meeting_ids


def test_generator_is_deterministic():
    first_run = Path(OUTPUT_DIR / "companies.json").read_text(encoding="utf-8")
    generate(seed=42, num_companies=3)
    second_run = Path(OUTPUT_DIR / "companies.json").read_text(encoding="utf-8")
    assert first_run == second_run
