"""
filename: __init__.py
description: System prompts and JSON schemas for each agent.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"


def language_instruction(language: str) -> str:
    """Trailing instruction asking Claude to respond in the requested language.

    Empty for English so the cached prefix stays unchanged.
    """
    if not language:
        return ""
    lang = language.strip()
    if not lang or lang.lower() in ("english", "en", "en-us"):
        return ""
    return (
        f"\n\nIMPORTANT: Respond entirely in {lang}. "
        f"All headings, bullets, summaries, action items, MEDDPICC notes, "
        f"competitor mentions, follow-up emails, and alerts MUST be in {lang}. "
        "Keep proper nouns (company names, product names, MEDDPICC category names) untranslated."
    )


def language_preamble(language: str) -> str:
    """Strong upfront instruction prepended to the user message. Haiku follows
    the first paragraph more closely than a trailing one, so we put the
    localisation directive at the very top when the response should not be in English.
    """
    if not language:
        return ""
    lang = language.strip()
    if not lang or lang.lower() in ("english", "en", "en-us"):
        return ""
    return (
        f"OUTPUT LANGUAGE: {lang}.\n"
        f"Every string in your structured response MUST be written in {lang}: "
        f"headline, section headings, bullets, summary, action item titles + descriptions, "
        f"MEDDPICC notes (translate the note; keep the category enum value untranslated), "
        f"competitor context, follow-up email subject + body, alert messages and "
        f"suggested responses. Keep proper nouns (company names, product names, "
        f"and the MEDDPICC category enum values) untranslated.\n\n---\n\n"
    )
