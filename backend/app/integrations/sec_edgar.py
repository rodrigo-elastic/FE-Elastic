"""
filename: sec_edgar.py
description: Real SEC EDGAR client. Fetches recent filings (10-K, 10-Q, 8-K, 20-F) for public companies via the official data.sec.gov submissions endpoint. No auth required; SEC asks that callers identify themselves via User-Agent.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

from typing import Any, Dict, List, Optional

import httpx

from app.utils.logging import get_logger

log = get_logger(__name__)

USER_AGENT = "FE Copilot Demo (rodrigo.careaga@elastic.co)"

# Form types we care about for the brief, in order of relevance for an FE.
INTERESTING_FORMS = (
    "8-K",      # material events: M&A, leadership changes, regulatory actions
    "10-K",     # annual report (US)
    "10-Q",     # quarterly report (US)
    "20-F",     # annual report (foreign private issuers, e.g. Banco Santander)
    "6-K",      # current reports for foreign private issuers
    "DEF 14A",  # proxy / compensation / governance
)


def fetch_recent_filings(cik: str, limit: int = 6) -> List[Dict[str, Any]]:
    """Call data.sec.gov for the latest filings of a company.

    Returns an empty list on any failure (offline, rate-limited, etc.) so the
    pre-meeting flow degrades gracefully.
    """
    if not cik:
        return []
    cik_padded = cik.lstrip("0").zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=8.0)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log.info("sec.fetch_failed", cik=cik, error=str(exc))
        return []

    filings = (data.get("filings") or {}).get("recent") or {}
    forms = filings.get("form") or []
    accession = filings.get("accessionNumber") or []
    primary_document = filings.get("primaryDocument") or []
    primary_doc_description = filings.get("primaryDocDescription") or []
    filing_date = filings.get("filingDate") or []
    report_date = filings.get("reportDate") or []
    items_raw = filings.get("items") or []

    out: List[Dict[str, Any]] = []
    cik_no_pad = cik_padded.lstrip("0")
    for i in range(min(len(forms), 200)):
        form = forms[i]
        if form not in INTERESTING_FORMS:
            continue
        acc = accession[i] if i < len(accession) else ""
        primary = primary_document[i] if i < len(primary_document) else ""
        # SEC URL conventions: https://www.sec.gov/Archives/edgar/data/{CIK}/{ACC_NO_DASHES_STRIPPED}/{primary}
        acc_clean = acc.replace("-", "")
        archive_url = (
            f"https://www.sec.gov/Archives/edgar/data/{cik_no_pad}/{acc_clean}/{primary}"
            if acc and primary
            else f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_padded}&type={form}"
        )
        out.append(
            {
                "form": form,
                "filing_date": filing_date[i] if i < len(filing_date) else "",
                "report_date": report_date[i] if i < len(report_date) else "",
                "accession_number": acc,
                "primary_document": primary,
                "description": primary_doc_description[i] if i < len(primary_doc_description) else "",
                "items": items_raw[i] if i < len(items_raw) else "",
                "url": archive_url,
            }
        )
        if len(out) >= limit:
            break
    log.info("sec.fetched", cik=cik, count=len(out))
    return out


def company_summary(cik: str) -> Optional[Dict[str, Any]]:
    """Lightweight company snapshot from EDGAR (name, tickers, SIC, exchanges)."""
    if not cik:
        return None
    cik_padded = cik.lstrip("0").zfill(10)
    url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
    try:
        r = httpx.get(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}, timeout=8.0)
        r.raise_for_status()
        data = r.json()
    except Exception as exc:
        log.info("sec.summary_failed", cik=cik, error=str(exc))
        return None
    return {
        "cik": cik_padded,
        "name": data.get("name"),
        "tickers": data.get("tickers") or [],
        "exchanges": data.get("exchanges") or [],
        "sic": data.get("sic"),
        "sic_description": data.get("sicDescription"),
        "ein": data.get("ein"),
        "state_of_incorporation": data.get("stateOfIncorporation"),
        "fiscal_year_end": data.get("fiscalYearEnd"),
        "url": f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik_padded}",
    }
