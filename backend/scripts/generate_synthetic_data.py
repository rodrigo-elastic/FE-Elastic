"""
filename: generate_synthetic_data.py
description: Deterministic demo dataset using three REAL companies (Revolut, Mercado Libre, Banco Santander). News items reference real public URLs (Wikipedia, company newsrooms, Reuters, SEC EDGAR) so a demo viewer can click and verify.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.2.0"
__status__ = "Development"

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Anchor "now" so every run on every machine produces identical timestamps.
NOW = datetime(2026, 5, 2, 9, 0, 0, tzinfo=timezone.utc)

OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "synthetic"


# Three REAL companies. Tech stack data based on public engineering blog posts,
# investor decks, and case studies. No customer data is referenced.
COMPANIES = [
    {
        "id": "revolut",
        "name": "Revolut",
        "industry": "Financial Services / Fintech",
        "size": "Enterprise (~10k employees)",
        "headquarters": "London, UK",
        "website": "https://www.revolut.com",
        "tech_stack": {
            "observability": ["Datadog", "Grafana", "Prometheus"],
            "search": ["Elasticsearch (some workloads)"],
            "cloud": ["Google Cloud", "AWS"],
            "other": ["Apache Kafka", "Kubernetes", "Java/Kotlin microservices"],
        },
        "description": (
            "UK-based digital bank serving 50M+ retail customers across 38 countries. "
            "Secured a UK banking licence in July 2024 after a three-year process. "
            "Heavy Kafka + Kubernetes shop on a multi-cloud footprint."
        ),
        "sec_cik": None,
        "ticker": None,
    },
    {
        "id": "mercado-libre",
        "name": "Mercado Libre",
        "industry": "E-commerce / Fintech (LATAM)",
        "size": "Enterprise (~75k employees)",
        "headquarters": "Buenos Aires, Argentina",
        "website": "https://www.mercadolibre.com",
        "tech_stack": {
            "observability": ["Datadog", "internal 'Furious' platform"],
            "search": ["Elasticsearch", "Apache Solr (legacy)"],
            "cloud": ["AWS", "Google Cloud"],
            "other": ["Apache Kafka", "Java/Scala", "Apache Flink"],
        },
        "description": (
            "LATAM's largest e-commerce + fintech platform. Public on NASDAQ as MELI. "
            "Operates Mercado Pago, Mercado Envios fulfilment, and a credit business. "
            "Public engineering blog documents heavy Kafka and ML infrastructure."
        ),
        "sec_cik": "0001099590",
        "ticker": "MELI",
    },
    {
        "id": "santander",
        "name": "Banco Santander",
        "industry": "Banking",
        "size": "Enterprise (~210k employees)",
        "headquarters": "Madrid, Spain",
        "website": "https://www.santander.com",
        "tech_stack": {
            "observability": ["Splunk", "Dynatrace", "Grafana"],
            "search": ["Elasticsearch (regional clusters)"],
            "cloud": ["AWS", "Azure", "Google Cloud", "private cloud"],
            "other": ["Red Hat OpenShift", "IBM mainframe (core banking)", "Gravity platform"],
        },
        "description": (
            "Global banking group headquartered in Spain. Public on NYSE (SAN), Madrid, and São Paulo. "
            "Operates retail, corporate, and investment banking across Europe and the Americas; "
            "internal 'Gravity' platform is the backbone of their multi-cloud digital strategy."
        ),
        "sec_cik": "0000891478",
        "ticker": "SAN",
    },
]


# News items: each has a REAL stable URL the demo viewer can click to verify.
# Wikipedia + official press rooms + SEC EDGAR are durable; Reuters URLs reference
# well-documented public events. days_ago is anchored to NOW (2026-05-02).
NEWS = [
    # --- Revolut --------------------------------------------------------------
    {
        "company_id": "revolut",
        "title": "Revolut secures UK banking licence after 3-year wait (Reuters)",
        "source": "Reuters",
        "days_ago": 6,
        "url": "https://www.reuters.com/business/finance/revolut-gets-uk-banking-licence-after-3-year-wait-2024-07-25/",
        "summary": "PRA grants Revolut a restricted UK banking licence, unlocking deposit-taking and lending products in its largest market.",
    },
    {
        "company_id": "revolut",
        "title": "Revolut overview, products, history, and regulatory milestones (Wikipedia)",
        "source": "Wikipedia",
        "days_ago": 14,
        "url": "https://en.wikipedia.org/wiki/Revolut",
        "summary": "Comprehensive Wikipedia entry: founded 2015 by Nikolay Storonsky and Vlad Yatsenko; reached 50M customers; Schroders-led $45B secondary share sale.",
    },
    {
        "company_id": "revolut",
        "title": "Revolut Newsroom (latest press releases and product announcements)",
        "source": "Revolut Newsroom",
        "days_ago": 22,
        "url": "https://www.revolut.com/news",
        "summary": "Official press feed: latest product launches, market entries, and corporate updates straight from Revolut Communications.",
    },

    # --- Mercado Libre --------------------------------------------------------
    {
        "company_id": "mercado-libre",
        "title": "Mercado Libre Investor Relations (earnings releases, presentations, filings)",
        "source": "MELI Investor Relations",
        "days_ago": 8,
        "url": "https://investor.mercadolibre.com",
        "summary": "Quarterly earnings, annual reports, and investor presentations. Latest reports highlight growth in Mercado Pago and credit portfolio expansion.",
    },
    {
        "company_id": "mercado-libre",
        "title": "Mercado Libre overview, business segments, and engineering culture (Wikipedia)",
        "source": "Wikipedia",
        "days_ago": 16,
        "url": "https://en.wikipedia.org/wiki/Mercado_Libre",
        "summary": "Founded 1999 by Marcos Galperin; NASDAQ-listed (MELI); operates marketplace + Mercado Pago + Mercado Envios across 18 LATAM countries.",
    },
    {
        "company_id": "mercado-libre",
        "title": "Mercado Libre Inc SEC filings (10-K, 10-Q, 8-K) on EDGAR",
        "source": "SEC EDGAR",
        "days_ago": 24,
        "url": "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0001099590&type=10-K",
        "summary": "Direct access to MELI's annual and quarterly filings with the U.S. Securities and Exchange Commission. Risk factors, segment results, and audited financials.",
    },

    # --- Banco Santander ------------------------------------------------------
    {
        "company_id": "santander",
        "title": "Banco Santander Press Room (announcements, strategy updates, ESG news)",
        "source": "Santander Press Room",
        "days_ago": 5,
        "url": "https://www.santander.com/en/press-room",
        "summary": "Official Santander press releases. Recent strategic updates emphasise the 'ONE Transformation' programme and Gravity multi-cloud platform rollout.",
    },
    {
        "company_id": "santander",
        "title": "Banco Santander shareholders and investors (annual results, presentations)",
        "source": "Santander IR",
        "days_ago": 12,
        "url": "https://www.santander.com/en/shareholders-and-investors",
        "summary": "Investor portal with quarterly results, annual reports, ESG disclosures, and AGM materials. Latest reports emphasise digital-channel customer growth.",
    },
    {
        "company_id": "santander",
        "title": "Banco Santander overview, history, and global footprint (Wikipedia)",
        "source": "Wikipedia",
        "days_ago": 20,
        "url": "https://en.wikipedia.org/wiki/Banco_Santander",
        "summary": "Founded 1857 in Santander, Cantabria; globally one of the largest banks by assets; operates in Europe, North America, South America with ~210k employees.",
    },
]


# Each company gets 1 upcoming meeting plus 2 historical meetings.
# starts_in_hours is relative to NOW.
MEETINGS = [
    # Revolut
    {"id": "revolut-mtg-001", "company_id": "revolut",
     "title": "Revolut x Elastic, observability cost & SIEM consolidation",
     "starts_in_hours": 24, "duration_min": 45,
     "attendees": ["rodrigo.careaga@elastic.co", "sarah.chen@revolut.example", "mike.taylor@revolut.example"],
     "notes": "Upcoming pre-meeting trigger candidate. Discovery on observability + security consolidation."},
    {"id": "revolut-mtg-prev-001", "company_id": "revolut",
     "title": "Revolut x Elastic, exec discovery",
     "starts_in_hours": -120, "duration_min": 45,
     "attendees": ["rodrigo.careaga@elastic.co", "sarah.chen@revolut.example", "mike.taylor@revolut.example"],
     "notes": "Past discovery call; transcript on file."},
    {"id": "revolut-mtg-prev-002", "company_id": "revolut",
     "title": "Revolut x Elastic, technical deep dive",
     "starts_in_hours": -72, "duration_min": 30,
     "attendees": ["rodrigo.careaga@elastic.co", "mike.taylor@revolut.example"],
     "notes": "Past technical follow-up."},

    # Mercado Libre
    {"id": "meli-mtg-001", "company_id": "mercado-libre",
     "title": "Mercado Libre x Elastic, search relevance + observability",
     "starts_in_hours": 48, "duration_min": 60,
     "attendees": ["rodrigo.careaga@elastic.co", "lucia.fernandez@mercadolibre.example", "diego.alvarez@mercadolibre.example"],
     "notes": "Upcoming. Search relevance for marketplace + observability consolidation."},
    {"id": "meli-mtg-prev-001", "company_id": "mercado-libre",
     "title": "Mercado Libre x Elastic, exec discovery",
     "starts_in_hours": -168, "duration_min": 45,
     "attendees": ["rodrigo.careaga@elastic.co", "lucia.fernandez@mercadolibre.example", "diego.alvarez@mercadolibre.example"],
     "notes": "Past exec call."},
    {"id": "meli-mtg-prev-002", "company_id": "mercado-libre",
     "title": "Mercado Libre x Elastic, search architecture review",
     "starts_in_hours": -96, "duration_min": 30,
     "attendees": ["rodrigo.careaga@elastic.co", "diego.alvarez@mercadolibre.example"],
     "notes": "Past architecture review."},

    # Santander
    {"id": "santander-mtg-001", "company_id": "santander",
     "title": "Santander x Elastic, Splunk renewal alternative review",
     "starts_in_hours": 144, "duration_min": 45,
     "attendees": ["rodrigo.careaga@elastic.co", "carlos.ruiz@santander.example", "marina.lopez@santander.example"],
     "notes": "Upcoming. Splunk renewal landscape and Gravity platform integration."},
    {"id": "santander-mtg-prev-001", "company_id": "santander",
     "title": "Santander x Elastic, exec discovery",
     "starts_in_hours": -240, "duration_min": 45,
     "attendees": ["rodrigo.careaga@elastic.co", "carlos.ruiz@santander.example", "marina.lopez@santander.example"],
     "notes": "Past exec call."},
    {"id": "santander-mtg-prev-002", "company_id": "santander",
     "title": "Santander x Elastic, regulatory mapping working session",
     "starts_in_hours": -360, "duration_min": 30,
     "attendees": ["rodrigo.careaga@elastic.co", "marina.lopez@santander.example"],
     "notes": "Past regulatory mapping session."},
]


# Two transcripts per company. The first is signals-rich; the second is vanilla.
TRANSCRIPTS = [
    # Revolut signals-rich
    {
        "meeting_id": "revolut-mtg-prev-001",
        "company_id": "revolut",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Sarah, Mike, thanks for the time. What is driving Revolut to look at consolidation now?"},
            {"speaker": "Sarah Chen (Revolut VP Engineering)", "text": "Two reasons. We just got the UK banking licence in July, so the regulator now expects audit-grade observability across the perimeter. And our Datadog spend is approaching 4 million a year."},
            {"speaker": "Mike Taylor (Revolut Platform Lead)", "text": "Plus we have a SIEM gap. We use Splunk for security, Datadog for app metrics, Grafana on Prometheus for infra. Three tools, three on-call rotations."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Got it. Who owns the consolidation decision?"},
            {"speaker": "Sarah Chen (Revolut VP Engineering)", "text": "I sponsor it. Our CTO signs. Mike runs the technical evaluation."},
            {"speaker": "Mike Taylor (Revolut Platform Lead)", "text": "Decision criteria are clear: single platform for logs, metrics, traces, plus SIEM. Native Kubernetes ingestion. Predictable storage costs at our 7 year audit retention."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Timeline?"},
            {"speaker": "Sarah Chen (Revolut VP Engineering)", "text": "Decision by end of Q3 2026. Datadog renewal is November 1. We need 6 months for migration if we go."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Any blockers?"},
            {"speaker": "Mike Taylor (Revolut Platform Lead)", "text": "We need a successful POC at our peak ingest, around 80 thousand events per second. If Elastic cannot keep up, we cannot move."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "I will send a POC plan covering ingest at 80k EPS, SIEM coverage to MITRE ATT&CK, and a Datadog cost comparison. Can we target a follow up next week?"},
            {"speaker": "Sarah Chen (Revolut VP Engineering)", "text": "Tuesday afternoon UK time works. Please loop in our procurement contact early; we lost two weeks last time."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Will do. I will also draft a regulatory mapping for the FCA expectations."},
        ],
    },
    # Revolut vanilla
    {
        "meeting_id": "revolut-mtg-prev-002",
        "company_id": "revolut",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Mike, walking through Elastic Cloud topology you asked about."},
            {"speaker": "Mike Taylor (Revolut Platform Lead)", "text": "Great. Start with regions and tier sizing for our EU workload."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Frankfurt + Dublin for EU; hot tier on i3 nodes, warm on d3."},
            {"speaker": "Mike Taylor (Revolut Platform Lead)", "text": "Index lifecycle?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Hot for 7 days, warm for 30, cold via searchable snapshots on GCS at 7 year retention."},
            {"speaker": "Mike Taylor (Revolut Platform Lead)", "text": "Cross-cluster search to our London region for break-glass investigations?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "CCS or CCR depending on freshness. We can pick based on regulator expectations."},
            {"speaker": "Mike Taylor (Revolut Platform Lead)", "text": "Send the reference architecture diagram and we can review with the platform team."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Sending today with the POC outline."},
        ],
    },

    # Mercado Libre signals-rich
    {
        "meeting_id": "meli-mtg-prev-001",
        "company_id": "mercado-libre",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Lucia, Diego, thanks for joining. What is driving MELI's evaluation right now?"},
            {"speaker": "Lucia Fernandez (MELI Director of Engineering)", "text": "Two things. Search relevance on the marketplace is plateauing; conversion is flat quarter over quarter. And our Datadog spend just crossed 6 million dollars annual."},
            {"speaker": "Diego Alvarez (MELI Search Tech Lead)", "text": "We are using Solr for some legacy product search and Elasticsearch for newer surfaces. We want one platform with vector support for semantic search across products."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "On the observability side, what's the renewal landscape?"},
            {"speaker": "Lucia Fernandez (MELI Director of Engineering)", "text": "Datadog renews September 1. We are evaluating Elastic, OpenSearch, and Datadog renewal. Board mandate is 30 percent cost reduction."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "On metrics, what does success look like in 12 months?"},
            {"speaker": "Lucia Fernandez (MELI Director of Engineering)", "text": "Search latency p99 under 80ms at 10x our current QPS. Observability ingest cost down 30 percent. Conversion lift of 2 percent on semantic-relevance pilot."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Decision process?"},
            {"speaker": "Lucia Fernandez (MELI Director of Engineering)", "text": "I sponsor. CTO signs. Architecture council reviews. Diego is the technical champion. Decision in Q3 2026."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Diego, top technical concerns?"},
            {"speaker": "Diego Alvarez (MELI Search Tech Lead)", "text": "ELSER quality at our catalog scale, dense vector ingest throughput, and cross-region replication latency Sao Paulo to Buenos Aires."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "All native. I'll send a search relevance benchmark and a Datadog migration cost model."},
            {"speaker": "Lucia Fernandez (MELI Director of Engineering)", "text": "Please. Can we book a deep dive next Wednesday?"},
        ],
    },
    # Mercado Libre vanilla
    {
        "meeting_id": "meli-mtg-prev-002",
        "company_id": "mercado-libre",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Diego, walking through public roadmap items relevant to your search workloads."},
            {"speaker": "Diego Alvarez (MELI Search Tech Lead)", "text": "Start with vector search."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Dense vector with HNSW is GA; ELSER as a built-in sparse model is broadly available."},
            {"speaker": "Diego Alvarez (MELI Search Tech Lead)", "text": "Cross cluster replication latency improvements?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Significantly improved in 8.13. We can share the benchmark."},
            {"speaker": "Diego Alvarez (MELI Search Tech Lead)", "text": "Helpful. Anything on the security roadmap?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Attack surface management plus entity analytics expansions; happy to schedule a Security session."},
            {"speaker": "Diego Alvarez (MELI Search Tech Lead)", "text": "Maybe later. Let's focus on search first."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Understood. I'll send the benchmark deck."},
        ],
    },

    # Santander signals-rich
    {
        "meeting_id": "santander-mtg-prev-001",
        "company_id": "santander",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Carlos, Marina, thanks for joining. What is driving Santander's Splunk evaluation now?"},
            {"speaker": "Carlos Ruiz (Santander MD Tech)", "text": "Two reasons. Our Splunk contract renews March 1, 2027 at roughly 12 million euros. And our 'Gravity' multi-cloud platform needs a single observability layer across AWS, Azure, GCP, and the private cloud."},
            {"speaker": "Marina Lopez (Santander Architecture Lead)", "text": "Plus a 90 minute trading platform slowdown last quarter. Log ingestion lag was a contributing factor."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "How is Splunk performing day to day?"},
            {"speaker": "Marina Lopez (Santander Architecture Lead)", "text": "It works, but storage tier costs are punishing for our 10 year audit retention required by ECB and the Bank of Spain. We need a more economical model."},
            {"speaker": "Carlos Ruiz (Santander MD Tech)", "text": "Evaluating Elastic, Sumo Logic, and Splunk renewal. Board wants 30 percent cost reduction at parity coverage."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "On metrics, what does success look like in 12 months?"},
            {"speaker": "Carlos Ruiz (Santander MD Tech)", "text": "Audit reporting from 21 days to under 7. Storage cost down 35 percent. Zero high severity logging incidents during peak trading windows."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Decision process and timeline?"},
            {"speaker": "Carlos Ruiz (Santander MD Tech)", "text": "I sponsor it. CIO Group Tech signs. Architecture council reviews. Marina is the technical champion. Decision in Q4 2026."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Marina, top technical concerns?"},
            {"speaker": "Marina Lopez (Santander Architecture Lead)", "text": "Frozen tier on object storage at 10 year retention, role based access at index level, SAML federation with our internal IDP, and clean integration with Gravity."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "All native. I'll send a Splunk to Elastic migration playbook plus regulatory mapping for ECB, BoS, and FCA reporting controls."},
            {"speaker": "Carlos Ruiz (Santander MD Tech)", "text": "Please. Can we book a deep dive with Marina's architecture team next Wednesday?"},
        ],
    },
    # Santander vanilla
    {
        "meeting_id": "santander-mtg-prev-002",
        "company_id": "santander",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Marina, working session on the regulatory mapping you asked for."},
            {"speaker": "Marina Lopez (Santander Architecture Lead)", "text": "Let's start with ECB GIM expectations."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Audit log immutability, 10 year retention, role based access, full text search across all events."},
            {"speaker": "Marina Lopez (Santander Architecture Lead)", "text": "Bank of Spain reporting requirements?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Quarterly attestation, role based access reviews, segregation of duties. All natively supported."},
            {"speaker": "Marina Lopez (Santander Architecture Lead)", "text": "FCA for our UK retail operations?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "PRA outsourcing rules apply. We have a customer-facing reference deck."},
            {"speaker": "Marina Lopez (Santander Architecture Lead)", "text": "Send the reference and we can review with our compliance team."},
        ],
    },
]


TICKETS = [
    # Revolut
    {"company_id": "revolut", "subject": "Datadog cost forecast vs Splunk renewal scenarios",
     "status": "In Progress", "priority": "P2", "days_ago": 11,
     "description": "Finance asked for a 12 month forecast comparing Datadog renewal vs consolidation onto a single platform."},
    {"company_id": "revolut", "subject": "SIEM coverage gap surfaced by FCA prep",
     "status": "Open", "priority": "P1", "days_ago": 6,
     "description": "Auditor flagged absence of unified SIEM in security operations as part of UK banking licence audit prep."},
    {"company_id": "revolut", "subject": "Peak ingest spike during card-based promo campaigns",
     "status": "Resolved", "priority": "P2", "days_ago": 19,
     "description": "Datadog ingest spike during a card promo caused $80k overage on the previous month's bill."},

    # Mercado Libre
    {"company_id": "mercado-libre", "subject": "Search relevance plateau on marketplace",
     "status": "In Progress", "priority": "P1", "days_ago": 9,
     "description": "Marketplace conversion has been flat 4 quarters in a row. Semantic search pilot proposed to lift relevance."},
    {"company_id": "mercado-libre", "subject": "Datadog cost growth trajectory",
     "status": "Open", "priority": "P2", "days_ago": 4,
     "description": "Procurement asked architecture for vendor consolidation options ahead of September 1 renewal."},
    {"company_id": "mercado-libre", "subject": "Solr to Elasticsearch migration on legacy product search",
     "status": "Open", "priority": "P3", "days_ago": 17,
     "description": "Legacy Solr clusters are EOL on the team's schedule; migration to a single search platform is overdue."},

    # Santander
    {"company_id": "santander", "subject": "Trading platform log ingestion lag",
     "status": "Resolved", "priority": "P1", "days_ago": 21,
     "description": "Lag during peak trading window contributed to a 90 minute slowdown."},
    {"company_id": "santander", "subject": "Audit reporting cycle reduction project",
     "status": "In Progress", "priority": "P2", "days_ago": 12,
     "description": "Initiative to cut audit reporting cycle from 21 days to under 7 days."},
    {"company_id": "santander", "subject": "Splunk cost reduction options for 2027 renewal",
     "status": "Open", "priority": "P2", "days_ago": 4,
     "description": "Procurement asked architecture council for vendor consolidation options ahead of the March 2027 renewal."},
]


def _iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat()


def build_companies(n: int) -> list:
    return COMPANIES[:n]


def build_news(companies: list) -> list:
    company_ids = {c["id"] for c in companies}
    items = []
    for n in NEWS:
        if n["company_id"] not in company_ids:
            continue
        published = NOW - timedelta(days=n["days_ago"])
        items.append(
            {
                "company_id": n["company_id"],
                "title": n["title"],
                "url": n["url"],
                "source": n["source"],
                "published_at": _iso(published),
                "summary": n["summary"],
            }
        )
    return items


def build_meetings(companies: list) -> list:
    company_ids = {c["id"] for c in companies}
    items = []
    for m in MEETINGS:
        if m["company_id"] not in company_ids:
            continue
        start = NOW + timedelta(hours=m["starts_in_hours"])
        end = start + timedelta(minutes=m["duration_min"])
        items.append(
            {
                "id": m["id"],
                "company_id": m["company_id"],
                "title": m["title"],
                "start_time": _iso(start),
                "end_time": _iso(end),
                "attendees": m["attendees"],
                "notes": m["notes"],
            }
        )
    return items


def build_transcripts(companies: list) -> list:
    company_ids = {c["id"] for c in companies}
    return [t for t in TRANSCRIPTS if t["company_id"] in company_ids]


def build_tickets(companies: list) -> list:
    company_ids = {c["id"] for c in companies}
    items = []
    for t in TICKETS:
        if t["company_id"] not in company_ids:
            continue
        created = NOW - timedelta(days=t["days_ago"])
        items.append(
            {
                "company_id": t["company_id"],
                "subject": t["subject"],
                "status": t["status"],
                "priority": t["priority"],
                "created_at": _iso(created),
                "description": t["description"],
            }
        )
    return items


def build_calendar(companies: list) -> list:
    """Calendar surface only includes upcoming meetings (the trigger source for Pre-Meeting agent)."""
    company_ids = {c["id"] for c in companies}
    items = []
    for m in MEETINGS:
        if m["company_id"] not in company_ids:
            continue
        if m["starts_in_hours"] <= 0:
            continue
        start = NOW + timedelta(hours=m["starts_in_hours"])
        end = start + timedelta(minutes=m["duration_min"])
        items.append(
            {
                "company_id": m["company_id"],
                "meeting_id": m["id"],
                "title": m["title"],
                "start_time": _iso(start),
                "end_time": _iso(end),
                "attendees": m["attendees"],
            }
        )
    return items


def write_json(name: str, data) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / f"{name}.json"
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def generate(seed: int = 42, num_companies: int = 3) -> dict:
    """Render synthetic data files; returns counts and paths."""
    random.seed(seed)
    companies = build_companies(num_companies)
    news = build_news(companies)
    meetings = build_meetings(companies)
    transcripts = build_transcripts(companies)
    tickets = build_tickets(companies)
    calendar = build_calendar(companies)

    paths = {
        "companies": write_json("companies", companies),
        "news": write_json("news", news),
        "meetings": write_json("meetings", meetings),
        "transcripts": write_json("transcripts", transcripts),
        "tickets": write_json("tickets", tickets),
        "calendar": write_json("calendar", calendar),
    }
    return {
        "counts": {
            "companies": len(companies),
            "news": len(news),
            "meetings": len(meetings),
            "transcripts": len(transcripts),
            "tickets": len(tickets),
            "calendar": len(calendar),
        },
        "paths": {k: str(v) for k, v in paths.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate FE Copilot synthetic data.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism.")
    parser.add_argument(
        "--companies",
        type=int,
        default=3,
        choices=[1, 2, 3],
        help="Number of companies to include (max 3).",
    )
    args = parser.parse_args()

    result = generate(seed=args.seed, num_companies=args.companies)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
