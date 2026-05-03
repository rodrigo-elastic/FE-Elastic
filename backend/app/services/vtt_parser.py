"""
filename: vtt_parser.py
description: Lightweight WebVTT parser. Accepts WebVTT cue blocks and plain "Speaker: text" transcripts; emits the same {speaker, text} shape the Post-Meeting agent expects.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import re
from typing import List, Dict


_VOICE_RE = re.compile(r"<v\s+([^>]+)>(.*?)(?:</v>)?$", re.DOTALL)
_TIMING_RE = re.compile(r"\d{2}:\d{2}:\d{2}\.\d{3}\s*-->")


def parse_vtt(text: str) -> List[Dict[str, str]]:
    """Parse a WebVTT (or plain "Speaker: text") transcript into turn dicts.

    Recognises:
    - WebVTT cues with <v Speaker> voice tags.
    - WebVTT cues with "Speaker: text" body.
    - Plain text with one "Speaker: text" per line.
    """
    if not text or not text.strip():
        return []

    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    looks_like_vtt = text.upper().startswith("WEBVTT") or bool(_TIMING_RE.search(text))
    return _parse_vtt_blocks(text) if looks_like_vtt else _parse_plain(text)


def _parse_vtt_blocks(text: str) -> List[Dict[str, str]]:
    turns: List[Dict[str, str]] = []
    blocks = re.split(r"\n\s*\n", text)
    for block in blocks:
        block = block.strip()
        if not block or block.upper().startswith("WEBVTT") or block.upper().startswith("NOTE"):
            continue
        lines = [l for l in block.split("\n") if l.strip()]
        timing_idx = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if timing_idx is None:
            continue
        cue = "\n".join(lines[timing_idx + 1 :]).strip()
        if not cue:
            continue
        speaker, text_body = _split_speaker(cue)
        if text_body:
            turns.append({"speaker": speaker, "text": text_body})
    return _coalesce(turns)


def _parse_plain(text: str) -> List[Dict[str, str]]:
    turns: List[Dict[str, str]] = []
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        speaker, text_body = _split_speaker(line)
        if text_body:
            turns.append({"speaker": speaker, "text": text_body})
    return _coalesce(turns)


def _split_speaker(cue: str) -> tuple[str, str]:
    """Pull a speaker label out of a cue. Falls back to 'Unknown' when no label is present."""
    cue = cue.strip()
    voice = _VOICE_RE.match(cue)
    if voice:
        return voice.group(1).strip(), voice.group(2).strip()
    # "Speaker: text" pattern; cap speaker label at 80 chars to avoid eating whole lines.
    if ":" in cue:
        head, _, tail = cue.partition(":")
        head = head.strip()
        if 0 < len(head) <= 80 and not head.isdigit() and "<" not in head:
            return head, tail.strip()
    return "Unknown", cue


def _coalesce(turns: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Merge consecutive turns from the same speaker (Zoom often splits a sentence into multiple cues)."""
    merged: List[Dict[str, str]] = []
    for t in turns:
        if merged and merged[-1]["speaker"] == t["speaker"]:
            merged[-1]["text"] = (merged[-1]["text"] + " " + t["text"]).strip()
        else:
            merged.append(dict(t))
    return merged
