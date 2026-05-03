"""
filename: test_transcript_parser.py
description: Tests for transcript_parser helpers.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from app.services import transcript_parser


def _transcript():
    return {
        "meeting_id": "x",
        "turns": [
            {"speaker": "FE", "text": "Hi"},
            {"speaker": "Customer", "text": "Hello"},
            {"speaker": "FE", "text": "Question?"},
            {"speaker": "Customer", "text": "Answer."},
            {"speaker": "FE", "text": "Bye"},
        ],
    }


def test_to_text_joins_turns():
    text = transcript_parser.to_text(_transcript())
    assert "FE: Hi" in text
    assert "Customer: Hello" in text


def test_recent_context_returns_window():
    out = transcript_parser.recent_context(_transcript(), turn_index=4, window=2)
    assert len(out) == 2
    assert out[-1]["text"] == "Answer."


def test_speakers_returns_unique_order():
    speakers = transcript_parser.speakers(_transcript())
    assert speakers == ["FE", "Customer"]
