"""
filename: transcript_parser.py
description: Lightweight helpers for transcript inspection (joining turns, recent context windows).
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import Any, Dict, List


def to_text(transcript: Dict[str, Any]) -> str:
    return "\n".join(f"{t['speaker']}: {t['text']}" for t in transcript.get("turns", []))


def recent_context(transcript: Dict[str, Any], turn_index: int, window: int = 4) -> List[Dict[str, Any]]:
    turns = transcript.get("turns", [])
    start = max(0, turn_index - window)
    return turns[start:turn_index]


def speakers(transcript: Dict[str, Any]) -> List[str]:
    seen = []
    for t in transcript.get("turns", []):
        if t["speaker"] not in seen:
            seen.append(t["speaker"])
    return seen
