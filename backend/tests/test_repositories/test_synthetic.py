"""
filename: test_synthetic.py
description: Sanity checks on the synthetic repository helpers.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from app.repositories import synthetic


def test_companies_loaded():
    assert len(synthetic.companies()) == 3


def test_find_company_returns_none_for_missing():
    assert synthetic.find_company("does-not-exist") is None


def test_find_meeting_for_northwind():
    m = synthetic.find_meeting("northwind-mtg-001")
    assert m is not None
    assert m["company_id"] == "northwind"


def test_news_for_company_filters():
    items = synthetic.news_for("northwind")
    assert len(items) == 3
    assert all(i["company_id"] == "northwind" for i in items)
    # Every news item must carry a URL; all demo URLs sit on .example domains.
    for n in items:
        assert n["url"].startswith("https://")


def test_transcript_for_meeting_links_back():
    t = synthetic.transcript_for_meeting("northwind-mtg-prev-001")
    assert t is not None
    assert t["company_id"] == "northwind"
    assert len(t["turns"]) > 8


def test_upcoming_calendar_only_future():
    cal = synthetic.upcoming_calendar()
    assert len(cal) == 3
