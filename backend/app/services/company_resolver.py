"""
filename: company_resolver.py
description: Smart resolver that decides which customer a calendar event actually belongs to. Filters internal Elastic accounts, deprioritises known consulting firms, matches against the synthetic customer DB by domain, and falls back to title-keyword scanning.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from app.repositories import synthetic

# Hosts treated as internal Elastic. Multiple variants because real orgs use sub-domains.
INTERNAL_DOMAINS = {
    "elastic.co",
    "elastic.example",
    "elasticsearch.com",
    "elasticcloud.com",
}

# Fictional consulting firms used in demo invites; their attendees should not anchor
# the customer guess. We deliberately avoid naming real consulting firms so demo data
# never looks like leaked customer intel.
CONSULTING_DOMAINS = {
    "helixadvisory.example",
    "pinnacleconsulting.example",
    "apexadvisory.example",
    "vegaconsulting.example",
    "meridiansi.example",
    "lumenpartners.example",
    "cardinalstrategy.example",
    "northstaradvisory.example",
}

# Free / personal mail providers - present in the room but not a corporate signal.
FREEMAIL_DOMAINS = {
    "gmail.com",
    "outlook.com",
    "hotmail.com",
    "yahoo.com",
    "proton.me",
    "icloud.com",
    "me.com",
}

# Customer aliases beyond the canonical synthetic IDs. Both subdomains and brand variants
# map back to the parent account. All domains are fictional .example placeholders.
DOMAIN_TO_COMPANY_ID = {
    "northwindpay.example": "northwind",
    "northwind.example": "northwind",
    "northwindtechnologies.example": "northwind",
    "mercadoatlas.example": "mercado-atlas",
    "mercadoatlas.com.ar": "mercado-atlas",
    "mercadoatlas.com.br": "mercado-atlas",
    "mercadoatlas.com.mx": "mercado-atlas",
    "mercadoatlaspago.example": "mercado-atlas",
    "mercadoatlasenvios.example": "mercado-atlas",
    "bancoatlantico.example": "atlantico",
    "bancoatlantico.co.uk": "atlantico",
    "bancoatlantico.es": "atlantico",
    "atlanticobank.example": "atlantico",
    "openatlantico.es": "atlantico",
}

# Coarse keyword fallbacks for fictional company names that appear in titles but not as
# email domains (e.g. customer dialled in from a freemail account, brokered by a
# consultant). All entries are fictional placeholders the demo can showcase.
TITLE_KEYWORDS = {
    "fjordbank": "Fjordbank",
    "stripeway": "Stripeway",
    "shopifold": "Shopifold",
    "spotifire": "Spotifire",
    "klarnix": "Klarnix",
    "adynox": "Adynox",
    "blockstone": "Blockstone",
    "wisetide": "Wisetide",
    "novobank": "Novobank",
    "monzaro": "Monzaro",
    "starlit": "Starlit Bank",
    "rappix": "Rappix",
    "nubo": "Nubo",
    "itaurus": "Banco Itaurus",
    "bravesco": "Banco Bravesco",
    "bcprime": "BCPrime",
    "openpay": "Openpay (demo)",
    "kavalry": "Kavalry",
    "linario": "Linario",
}


def _domain_of(email: str) -> str:
    """Lower-case domain after the @, or empty when malformed."""
    if not email or "@" not in email:
        return ""
    return email.split("@", 1)[1].strip().lower()


def _normalise_domain(domain: str) -> str:
    """Strip common prefixes (mail., smtp., etc.) and the trailing slash if present."""
    domain = domain.strip().lower()
    for prefix in ("mail.", "smtp.", "email.", "www."):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    return domain.rstrip("/")


def _classify_attendee(email: str) -> Tuple[str, str]:
    """Return (bucket, domain). bucket ∈ internal | consulting | freemail | external."""
    domain = _normalise_domain(_domain_of(email))
    if not domain:
        return "unknown", ""
    if domain in INTERNAL_DOMAINS or any(domain.endswith("." + d) for d in INTERNAL_DOMAINS):
        return "internal", domain
    if domain in CONSULTING_DOMAINS:
        return "consulting", domain
    if domain in FREEMAIL_DOMAINS:
        return "freemail", domain
    return "external", domain


def _company_for_domain(domain: str) -> Optional[Dict[str, Any]]:
    """Lookup against the synthetic customer DB by exact or aliased domain."""
    if not domain:
        return None
    if domain in DOMAIN_TO_COMPANY_ID:
        return synthetic.find_company(DOMAIN_TO_COMPANY_ID[domain])
    # Soft-match: company name vs domain stem (e.g. "northwindpay" in "northwindpay.example").
    stem = domain.split(".")[0]
    for c in synthetic.companies():
        cid = (c.get("id") or "").replace("-", "")
        cname = (c.get("name") or "").lower().replace(" ", "")
        if stem and (stem in cid or cid in stem or stem in cname):
            return c
    return None


def _company_from_title(title: str) -> Optional[Dict[str, Any]]:
    """Last-mile fallback: scan title for known company tokens."""
    if not title:
        return None
    lower = title.lower()
    # Try synthetic customers first.
    for c in synthetic.companies():
        name = (c.get("name") or "").lower()
        if name and name in lower:
            return c
    # Then well-known industry keywords (companies the demo doesn't have records for).
    for token, friendly in TITLE_KEYWORDS.items():
        if re.search(r"\b" + re.escape(token) + r"\b", lower):
            return {"id": f"unknown-{token}", "name": friendly, "_source": "title-keyword"}
    return None


def resolve_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Return a structured guess for which customer this calendar event belongs to.

    Returns:
      {
        company: {id, name, ...} | None,
        confidence: "high" | "medium" | "low" | "internal",
        method: short reason string,
        candidates: [{name, domain, count}, ...],
        external_domains: [...],
        consulting_present: bool,
      }
    """
    attendees: List[Dict[str, Any]] = event.get("attendees") or []
    title: str = event.get("summary") or ""

    by_bucket: Dict[str, List[str]] = {"internal": [], "consulting": [], "freemail": [], "external": [], "unknown": []}
    domain_counts: Counter[str] = Counter()
    for a in attendees:
        bucket, domain = _classify_attendee(a.get("email", ""))
        by_bucket[bucket].append(domain)
        if bucket == "external":
            domain_counts[domain] += 1

    consulting_present = bool(by_bucket["consulting"])

    # Internal-only meeting: short-circuit.
    if not by_bucket["external"] and not by_bucket["consulting"] and not by_bucket["freemail"]:
        return {
            "company": None,
            "confidence": "internal",
            "method": "all attendees are internal",
            "candidates": [],
            "external_domains": [],
            "consulting_present": False,
        }

    # 1) Strong: a single non-consulting external domain mapped to a known customer.
    if domain_counts:
        top_domain, top_count = domain_counts.most_common(1)[0]
        company = _company_for_domain(top_domain)
        if company:
            return {
                "company": company,
                "confidence": "high",
                "method": f"matched {top_domain} ({top_count} attendee(s)) against customer DB",
                "candidates": _to_candidates(domain_counts),
                "external_domains": list(domain_counts),
                "consulting_present": consulting_present,
            }
        # External domain present but no DB match: report as medium with the domain stem.
        company = {
            "id": f"unknown-{top_domain.split('.')[0]}",
            "name": top_domain.split(".")[0].replace("-", " ").title(),
            "_source": "domain-stem",
            "_domain": top_domain,
        }
        return {
            "company": company,
            "confidence": "medium",
            "method": f"external domain {top_domain} not in customer DB; using stem",
            "candidates": _to_candidates(domain_counts),
            "external_domains": list(domain_counts),
            "consulting_present": consulting_present,
        }

    # 2) Title-keyword fallback (consultants + freemail + title-named customer).
    company = _company_from_title(title)
    if company:
        return {
            "company": company,
            "confidence": "low",
            "method": f"title keyword matched '{company['name']}' (no clean customer domain in invite)",
            "candidates": [],
            "external_domains": [],
            "consulting_present": consulting_present,
        }

    # 3) Last resort: list the consulting firms present so the FE can ask.
    consulting = sorted(set(by_bucket["consulting"]))
    return {
        "company": None,
        "confidence": "low",
        "method": "no customer domain or title keyword matched; consultants present in invite",
        "candidates": [{"name": d, "domain": d, "count": by_bucket["consulting"].count(d)} for d in consulting],
        "external_domains": [],
        "consulting_present": consulting_present,
    }


def _to_candidates(counter: Counter) -> List[Dict[str, Any]]:
    return [{"domain": d, "count": n, "name": d.split(".")[0].title()} for d, n in counter.most_common()]
