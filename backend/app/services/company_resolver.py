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

# Known global consulting firms; their attendees should not anchor the customer guess.
CONSULTING_DOMAINS = {
    "accenture.com",
    "deloitte.com",
    "mckinsey.com",
    "ey.com",
    "kpmg.com",
    "pwc.com",
    "capgemini.com",
    "bcg.com",
    "infosys.com",
    "tcs.com",
    "wipro.com",
    "cognizant.com",
    "hcl.com",
    "tatasteel.com",
    "ibm.com",  # often acts as advisor / SI in observability deals
    "oracle.com",
    "boozallen.com",
    "bain.com",
    "rolandberger.com",
    "thoughtworks.com",
}

# Free / personal mail providers — present in the room but not a corporate signal.
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
# (Mercado Pago, Mercado Envios) map back to the parent account.
DOMAIN_TO_COMPANY_ID = {
    "revolut.com": "revolut",
    "revolut.co.uk": "revolut",
    "revoluttechnologies.com": "revolut",
    "mercadolibre.com": "mercado-libre",
    "mercadolibre.com.ar": "mercado-libre",
    "mercadolibre.com.br": "mercado-libre",
    "mercadolibre.com.mx": "mercado-libre",
    "mercadopago.com": "mercado-libre",
    "mercadoenvios.com": "mercado-libre",
    "santander.com": "santander",
    "santander.co.uk": "santander",
    "santander.es": "santander",
    "santanderbank.com": "santander",
    "openbank.es": "santander",
}

# Coarse keyword fallbacks for company names that appear in titles but not as email
# domains (e.g. customer dialled in from a freemail account, brokered by a consultant).
TITLE_KEYWORDS = {
    "bbva": "BBVA",
    "stripe": "Stripe",
    "shopify": "Shopify",
    "spotify": "Spotify",
    "klarna": "Klarna",
    "adyen": "Adyen",
    "block": "Block (Square)",
    "square": "Block (Square)",
    "wise": "Wise",
    "n26": "N26",
    "monzo": "Monzo",
    "starling": "Starling Bank",
    "rappi": "Rappi",
    "nubank": "Nubank",
    "itau": "Banco Itau",
    "bradesco": "Banco Bradesco",
    "bcp": "BCP",
    "openpay": "Openpay",
    "kavak": "Kavak",
    "linio": "Linio",
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
    # Soft-match: company name vs domain stem (e.g. "revolut" in "revolut.com").
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
