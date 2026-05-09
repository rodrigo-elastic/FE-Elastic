"""
filename: generate_synthetic_data.py
description: Deterministic demo dataset using three FICTIONAL companies (Northwind Pay, Mercado Atlas, Banco Atlántico). All identities, employees, financial figures, and URLs are illustrative demo data; nothing here represents a real customer.
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


# Three FICTIONAL companies. All employee names, attendee lists, financial figures,
# and stack details are illustrative; nothing here represents a real customer.
COMPANIES = [
    {
        "id": "northwind",
        "name": "Northwind Pay",
        "industry": "Financial Services / Fintech",
        "size": "Enterprise (~10k employees)",
        "headquarters": "Dublin, Ireland",
        "website": "https://www.northwindpay.example",
        "tech_stack": {
            "observability": ["Datadog", "Grafana", "Prometheus"],
            "search": ["Elasticsearch (some workloads)"],
            "cloud": ["Google Cloud", "AWS"],
            "other": ["Apache Kafka", "Kubernetes", "Java/Kotlin microservices"],
        },
        "description": (
            "Fictional EU-based digital bank serving 50M+ retail customers across 38 countries. "
            "Secured an EU banking licence in Q3 2025 after a three-year process. "
            "Heavy Kafka + Kubernetes shop on a multi-cloud footprint."
        ),
        "sec_cik": None,
        "ticker": None,
    },
    {
        "id": "mercado-atlas",
        "name": "Mercado Atlas",
        "industry": "E-commerce / Fintech (LATAM)",
        "size": "Enterprise (~75k employees)",
        "headquarters": "Buenos Aires, Argentina",
        "website": "https://www.mercadoatlas.example",
        "tech_stack": {
            "observability": ["Datadog", "internal 'Aurora' platform"],
            "search": ["Elasticsearch", "Apache Solr (legacy)"],
            "cloud": ["AWS", "Google Cloud"],
            "other": ["Apache Kafka", "Java/Scala", "Apache Flink"],
        },
        "description": (
            "Fictional LATAM e-commerce + fintech platform. "
            "Operates Mercado Atlas Pay, Mercado Atlas Envios fulfilment, and a credit business. "
            "Public engineering blog documents heavy Kafka and ML infrastructure."
        ),
        "sec_cik": None,
        "ticker": None,
    },
    {
        "id": "searchlightcap",
        "name": "Searchlight Capital",
        "industry": "Financial Services / Asset Management",
        "size": "Enterprise (~3,800 employees)",
        "headquarters": "New York, USA",
        "website": "https://www.searchlightcap.example",
        "tech_stack": {
            "observability": ["Splunk Enterprise (incumbent)", "Datadog (APM only)", "PagerDuty"],
            "search": ["Elasticsearch (legacy logging on a few teams)"],
            "cloud": ["AWS", "Azure"],
            "other": ["Snowflake", "Kubernetes (EKS)", "GitLab CI"],
        },
        "description": (
            "Fictional global private-investment firm with $14B AUM across infrastructure, energy, "
            "and financial services. Splunk is the incumbent SIEM and observability platform with a "
            "60-day renewal window. DORA audit pending in Q3. Champions: Priya Sharma (VP Platform), "
            "James Liu (Lead SRE), Sandra Park (CFO)."
        ),
        "sec_cik": None,
        "ticker": None,
    },
]


# News items: each links to a fictional .example URL. Wikipedia, Reuters, SEC EDGAR
# references have been removed because the underlying companies are not real public
# entities. days_ago is anchored to NOW (2026-05-02).
NEWS = [
    # --- Northwind Pay --------------------------------------------------------
    {
        "company_id": "northwind",
        "title": "Northwind Pay secures EU banking licence after 3-year wait (fictional)",
        "source": "Northwind Pay Newsroom (demo)",
        "days_ago": 6,
        "url": "https://www.northwindpay.example/news/eu-banking-licence",
        "summary": "Demo article: regulator grants Northwind Pay a restricted EU banking licence, unlocking deposit-taking and lending products in its largest market.",
    },
    {
        "company_id": "northwind",
        "title": "Northwind Pay overview, products, history, and regulatory milestones (fictional)",
        "source": "Northwind Pay (demo)",
        "days_ago": 14,
        "url": "https://www.northwindpay.example/about",
        "summary": "Demo background page: founded 2015 by fictional founders; reached 50M customers; secondary share sale led by an unnamed investor.",
    },
    {
        "company_id": "northwind",
        "title": "Northwind Pay Newsroom (latest press releases and product announcements, fictional)",
        "source": "Northwind Pay Newsroom (demo)",
        "days_ago": 22,
        "url": "https://www.northwindpay.example/news",
        "summary": "Demo press feed: latest product launches, market entries, and corporate updates straight from Northwind Pay Communications.",
    },

    # --- Mercado Atlas --------------------------------------------------------
    {
        "company_id": "mercado-atlas",
        "title": "Mercado Atlas Investor Relations (earnings releases, presentations, filings, fictional)",
        "source": "Mercado Atlas IR (demo)",
        "days_ago": 8,
        "url": "https://investor.mercadoatlas.example",
        "summary": "Demo IR portal: quarterly earnings, annual reports, and investor presentations. Latest reports highlight growth in Mercado Atlas Pay and credit portfolio expansion.",
    },
    {
        "company_id": "mercado-atlas",
        "title": "Mercado Atlas overview, business segments, and engineering culture (fictional)",
        "source": "Mercado Atlas (demo)",
        "days_ago": 16,
        "url": "https://www.mercadoatlas.example/about",
        "summary": "Demo background page: founded 1999 by fictional founders; operates marketplace + Mercado Atlas Pay + Mercado Atlas Envios across 18 LATAM countries.",
    },
    {
        "company_id": "mercado-atlas",
        "title": "Mercado Atlas annual report (fictional)",
        "source": "Mercado Atlas IR (demo)",
        "days_ago": 24,
        "url": "https://investor.mercadoatlas.example/annual-report",
        "summary": "Demo annual report: risk factors, segment results, and audited financials. All figures are illustrative.",
    },

    # --- Searchlight Capital --------------------------------------------------
    {
        "company_id": "searchlightcap",
        "title": "Searchlight Capital announces $4.2B Fund V close (fictional)",
        "source": "Searchlight Capital Press Room (demo)",
        "days_ago": 5,
        "url": "https://www.searchlightcap.example/news/fund-v-close",
        "summary": "Demo article: Searchlight Capital closes its fifth flagship fund at $4.2 billion, focusing on infrastructure, energy, and financial services. AUM crosses $14 billion across the platform.",
    },
    {
        "company_id": "searchlightcap",
        "title": "Searchlight Capital overview, strategy, and portfolio (fictional)",
        "source": "Searchlight Capital (demo)",
        "days_ago": 12,
        "url": "https://www.searchlightcap.example/about",
        "summary": "Demo background page: global private investment firm founded 2010; offices in New York, London, and Toronto; focused on long-duration infrastructure and FSI assets.",
    },
    {
        "company_id": "searchlightcap",
        "title": "DORA in 2026 - what asset managers must report (fictional analyst note)",
        "source": "FSI Analyst Watch (demo)",
        "days_ago": 20,
        "url": "https://www.fsianalyst.example/dora-2026",
        "summary": "Demo analyst note: with DORA enforcement now in full swing, asset managers face quarterly attestation on operational resilience. Cited firms include Searchlight Capital, with a June audit window.",
    },
]


# Each company gets 1 upcoming meeting plus 2 historical meetings.
# starts_in_hours is relative to NOW.
MEETINGS = [
    # Northwind Pay
    {"id": "northwind-mtg-001", "company_id": "northwind",
     "title": "Northwind Pay x Elastic, observability cost & SIEM consolidation",
     "starts_in_hours": 24, "duration_min": 45,
     "attendees": ["rodrigo.careaga@elastic.co", "sarah.chen@northwindpay.example", "mike.taylor@northwindpay.example"],
     "notes": "Upcoming pre-meeting trigger candidate. Discovery on observability + security consolidation."},
    {"id": "northwind-mtg-prev-001", "company_id": "northwind",
     "title": "Northwind Pay x Elastic, exec discovery",
     "starts_in_hours": -120, "duration_min": 45,
     "attendees": ["rodrigo.careaga@elastic.co", "sarah.chen@northwindpay.example", "mike.taylor@northwindpay.example"],
     "notes": "Past discovery call; transcript on file."},
    {"id": "northwind-mtg-prev-002", "company_id": "northwind",
     "title": "Northwind Pay x Elastic, technical deep dive",
     "starts_in_hours": -72, "duration_min": 30,
     "attendees": ["rodrigo.careaga@elastic.co", "mike.taylor@northwindpay.example"],
     "notes": "Past technical follow-up."},

    # Mercado Atlas
    {"id": "mercadoatlas-mtg-001", "company_id": "mercado-atlas",
     "title": "Mercado Atlas x Elastic, search relevance + observability",
     "starts_in_hours": 48, "duration_min": 60,
     "attendees": ["rodrigo.careaga@elastic.co", "lucia.fernandez@mercadoatlas.example", "diego.alvarez@mercadoatlas.example"],
     "notes": "Upcoming. Search relevance for marketplace + observability consolidation."},
    {"id": "mercadoatlas-mtg-prev-001", "company_id": "mercado-atlas",
     "title": "Mercado Atlas x Elastic, exec discovery",
     "starts_in_hours": -168, "duration_min": 45,
     "attendees": ["rodrigo.careaga@elastic.co", "lucia.fernandez@mercadoatlas.example", "diego.alvarez@mercadoatlas.example"],
     "notes": "Past exec call."},
    {"id": "mercadoatlas-mtg-prev-002", "company_id": "mercado-atlas",
     "title": "Mercado Atlas x Elastic, search architecture review",
     "starts_in_hours": -96, "duration_min": 30,
     "attendees": ["rodrigo.careaga@elastic.co", "diego.alvarez@mercadoatlas.example"],
     "notes": "Past architecture review."},

    # Searchlight Capital
    {"id": "searchlight-mtg-001", "company_id": "searchlightcap",
     "title": "Searchlight Capital x Elastic, Splunk displacement (60-day renewal window)",
     "starts_in_hours": 48, "duration_min": 45,
     "attendees": ["rodrigo.careaga@elastic.co", "priya.sharma@searchlightcap.example", "james.liu@searchlightcap.example", "sandra.park@searchlightcap.example"],
     "notes": "Upcoming. Final commercial review before Splunk renewal lock. Sandra Park (CFO) attending."},
    {"id": "searchlight-mtg-prev-001", "company_id": "searchlightcap",
     "title": "Searchlight Capital x Elastic, exec discovery",
     "starts_in_hours": -240, "duration_min": 45,
     "attendees": ["rodrigo.careaga@elastic.co", "priya.sharma@searchlightcap.example", "james.liu@searchlightcap.example"],
     "notes": "First discovery call. Confirmed Splunk renewal in 60 days at $1.2M/year and DORA audit pending in June."},
    {"id": "searchlight-mtg-prev-002", "company_id": "searchlightcap",
     "title": "Searchlight Capital x Elastic, technical deep dive",
     "starts_in_hours": -120, "duration_min": 60,
     "attendees": ["rodrigo.careaga@elastic.co", "james.liu@searchlightcap.example"],
     "notes": "Architecture review with James Liu. 2.4 TB/day ingest across 14 indexes; sized Elastic Cloud for parity with Splunk."},
]


# Two transcripts per company. The first is signals-rich; the second is vanilla.
TRANSCRIPTS = [
    # Northwind Pay signals-rich
    {
        "meeting_id": "northwind-mtg-prev-001",
        "company_id": "northwind",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Sarah, Mike, thanks for the time. What is driving Northwind Pay to look at consolidation now?"},
            {"speaker": "Sarah Chen (Northwind Pay VP Engineering)", "text": "Two reasons. We just got the EU banking licence in Q3 2025, so the regulator now expects audit-grade observability across the perimeter. And our Datadog spend is approaching 4 million a year."},
            {"speaker": "Mike Taylor (Northwind Pay Platform Lead)", "text": "Plus we have a SIEM gap. We use Splunk for security, Datadog for app metrics, Grafana on Prometheus for infra. Three tools, three on-call rotations."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Got it. Who owns the consolidation decision?"},
            {"speaker": "Sarah Chen (Northwind Pay VP Engineering)", "text": "I sponsor it. Our CTO signs. Mike runs the technical evaluation."},
            {"speaker": "Mike Taylor (Northwind Pay Platform Lead)", "text": "Decision criteria are clear: single platform for logs, metrics, traces, plus SIEM. Native Kubernetes ingestion. Predictable storage costs at our 7 year audit retention."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Timeline?"},
            {"speaker": "Sarah Chen (Northwind Pay VP Engineering)", "text": "Decision by end of Q3 2026. Datadog renewal is November 1. We need 6 months for migration if we go."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Any blockers?"},
            {"speaker": "Mike Taylor (Northwind Pay Platform Lead)", "text": "We need a successful POC at our peak ingest, around 80 thousand events per second. If Elastic cannot keep up, we cannot move."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "I will send a POC plan covering ingest at 80k EPS, SIEM coverage to MITRE ATT&CK, and a Datadog cost comparison. Can we target a follow up next week?"},
            {"speaker": "Sarah Chen (Northwind Pay VP Engineering)", "text": "Tuesday afternoon EU time works. Please loop in our procurement contact early; we lost two weeks last time."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Will do. I will also draft a regulatory mapping for the EU banking expectations."},
        ],
    },
    # Northwind Pay vanilla
    {
        "meeting_id": "northwind-mtg-prev-002",
        "company_id": "northwind",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Mike, walking through Elastic Cloud topology you asked about."},
            {"speaker": "Mike Taylor (Northwind Pay Platform Lead)", "text": "Great. Start with regions and tier sizing for our EU workload."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Frankfurt + Dublin for EU; hot tier on i3 nodes, warm on d3."},
            {"speaker": "Mike Taylor (Northwind Pay Platform Lead)", "text": "Index lifecycle?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Hot for 7 days, warm for 30, cold via searchable snapshots on GCS at 7 year retention."},
            {"speaker": "Mike Taylor (Northwind Pay Platform Lead)", "text": "Cross-cluster search to our Dublin region for break-glass investigations?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "CCS or CCR depending on freshness. We can pick based on regulator expectations."},
            {"speaker": "Mike Taylor (Northwind Pay Platform Lead)", "text": "Send the reference architecture diagram and we can review with the platform team."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Sending today with the POC outline."},
        ],
    },

    # Mercado Atlas signals-rich
    {
        "meeting_id": "mercadoatlas-mtg-prev-001",
        "company_id": "mercado-atlas",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Lucia, Diego, thanks for joining. What is driving Mercado Atlas's evaluation right now?"},
            {"speaker": "Lucia Fernandez (Mercado Atlas Director of Engineering)", "text": "Two things. Search relevance on the marketplace is plateauing; conversion is flat quarter over quarter. And our Datadog spend just crossed 6 million dollars annual."},
            {"speaker": "Diego Alvarez (Mercado Atlas Search Tech Lead)", "text": "We are using Solr for some legacy product search and Elasticsearch for newer surfaces. We want one platform with vector support for semantic search across products."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "On the observability side, what's the renewal landscape?"},
            {"speaker": "Lucia Fernandez (Mercado Atlas Director of Engineering)", "text": "Datadog renews September 1. We are evaluating Elastic, OpenSearch, and Datadog renewal. Board mandate is 30 percent cost reduction."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "On metrics, what does success look like in 12 months?"},
            {"speaker": "Lucia Fernandez (Mercado Atlas Director of Engineering)", "text": "Search latency p99 under 80ms at 10x our current QPS. Observability ingest cost down 30 percent. Conversion lift of 2 percent on semantic-relevance pilot."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Decision process?"},
            {"speaker": "Lucia Fernandez (Mercado Atlas Director of Engineering)", "text": "I sponsor. CTO signs. Architecture council reviews. Diego is the technical champion. Decision in Q3 2026."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Diego, top technical concerns?"},
            {"speaker": "Diego Alvarez (Mercado Atlas Search Tech Lead)", "text": "ELSER quality at our catalog scale, dense vector ingest throughput, and cross-region replication latency Sao Paulo to Buenos Aires."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "All native. I'll send a search relevance benchmark and a Datadog migration cost model."},
            {"speaker": "Lucia Fernandez (Mercado Atlas Director of Engineering)", "text": "Please. Can we book a deep dive next Wednesday?"},
        ],
    },
    # Mercado Atlas vanilla
    {
        "meeting_id": "mercadoatlas-mtg-prev-002",
        "company_id": "mercado-atlas",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Diego, walking through public roadmap items relevant to your search workloads."},
            {"speaker": "Diego Alvarez (Mercado Atlas Search Tech Lead)", "text": "Start with vector search."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Dense vector with HNSW is GA; ELSER as a built-in sparse model is broadly available."},
            {"speaker": "Diego Alvarez (Mercado Atlas Search Tech Lead)", "text": "Cross cluster replication latency improvements?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Significantly improved in 8.13. We can share the benchmark."},
            {"speaker": "Diego Alvarez (Mercado Atlas Search Tech Lead)", "text": "Helpful. Anything on the security roadmap?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Attack surface management plus entity analytics expansions; happy to schedule a Security session."},
            {"speaker": "Diego Alvarez (Mercado Atlas Search Tech Lead)", "text": "Maybe later. Let's focus on search first."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Understood. I'll send the benchmark deck."},
        ],
    },

    # Searchlight Capital signals-rich
    {
        "meeting_id": "searchlight-mtg-prev-001",
        "company_id": "searchlightcap",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "Priya, James, thanks for the time. What is driving Searchlight Capital to look at Splunk alternatives now?"},
            {"speaker": "Priya Sharma (Searchlight Capital VP Platform)", "text": "Two converging deadlines. Our Splunk contract renews on March 15, 2027 - and the renewal lock-in window is sixty days from today. And we have a DORA audit coming in June for our portfolio companies."},
            {"speaker": "James Liu (Searchlight Capital Lead SRE)", "text": "On the technical side, Splunk storage costs at our 7-year audit retention are crushing the platform budget. We're at $1.2 million a year and growing."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Got it. Who owns the displacement decision?"},
            {"speaker": "Priya Sharma (Searchlight Capital VP Platform)", "text": "I sponsor it. Our CTO signs. James runs the technical evaluation. Sandra Park, our CFO, owns the commercial line."},
            {"speaker": "James Liu (Searchlight Capital Lead SRE)", "text": "Decision criteria: single platform for SIEM and observability, native vector for our compliance search use case, and DORA-ready dashboards for deployment frequency, MTTR, change failure rate, and lead time."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Timeline?"},
            {"speaker": "Priya Sharma (Searchlight Capital VP Platform)", "text": "We need a go/no-go in 30 days. Splunk renewal locks in 60. We need 90 days for migration if we displace."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "What would block this?"},
            {"speaker": "James Liu (Searchlight Capital Lead SRE)", "text": "We need a POC at our peak ingest of 2.4 TB/day across 14 indexes. If Elastic can't keep up at p99 under 200 ms query latency, we can't move."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "I'll send a POC plan covering 2.4 TB/day ingest, DORA dashboards out of the box, and a Splunk-to-Elastic TCO model. Can we target the technical deep dive next week?"},
            {"speaker": "Priya Sharma (Searchlight Capital VP Platform)", "text": "Please. James will lead. Loop in Sandra by week three so commercial doesn't slip."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Will do. I'll also draft the displacement narrative for your CTO and CFO before the next session."},
        ],
    },
    # Searchlight Capital vanilla
    {
        "meeting_id": "searchlight-mtg-prev-002",
        "company_id": "searchlightcap",
        "turns": [
            {"speaker": "Rodrigo (Elastic FE)", "text": "James, walking through the architecture options for the 2.4 TB/day ingest."},
            {"speaker": "James Liu (Searchlight Capital Lead SRE)", "text": "Start with sizing. We have 14 indexes, peaks at noon EST and at market close."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Hot tier on i3en nodes, warm on d3.2xlarge, frozen on S3 with searchable snapshots at 7-year retention."},
            {"speaker": "James Liu (Searchlight Capital Lead SRE)", "text": "What about query latency at the frozen tier? We pull the 18-month window for compliance audits."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Frozen searchable snapshots return in 2-5 seconds for that window with the right shard layout. We can show you the benchmark."},
            {"speaker": "James Liu (Searchlight Capital Lead SRE)", "text": "DORA dashboards out of the box?"},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Yes - deployment frequency, MTTR, change failure rate, lead time. Native in Elastic Observability with the GitLab integration."},
            {"speaker": "James Liu (Searchlight Capital Lead SRE)", "text": "Send the architecture diagram and the benchmark. I want to walk Sandra through the TCO at next week's review."},
            {"speaker": "Rodrigo (Elastic FE)", "text": "Sending today, with the Splunk-to-Elastic cost model and a 60-day displacement plan."},
        ],
    },
]


TICKETS = [
    # Northwind Pay
    {"company_id": "northwind", "subject": "Datadog cost forecast vs Splunk renewal scenarios",
     "status": "In Progress", "priority": "P2", "days_ago": 11,
     "description": "Finance asked for a 12 month forecast comparing Datadog renewal vs consolidation onto a single platform."},
    {"company_id": "northwind", "subject": "SIEM coverage gap surfaced by regulator prep",
     "status": "Open", "priority": "P1", "days_ago": 6,
     "description": "Auditor flagged absence of unified SIEM in security operations as part of EU banking licence audit prep."},
    {"company_id": "northwind", "subject": "Peak ingest spike during card-based promo campaigns",
     "status": "Resolved", "priority": "P2", "days_ago": 19,
     "description": "Datadog ingest spike during a card promo caused $80k overage on the previous month's bill."},

    # Mercado Atlas
    {"company_id": "mercado-atlas", "subject": "Search relevance plateau on marketplace",
     "status": "In Progress", "priority": "P1", "days_ago": 9,
     "description": "Marketplace conversion has been flat 4 quarters in a row. Semantic search pilot proposed to lift relevance."},
    {"company_id": "mercado-atlas", "subject": "Datadog cost growth trajectory",
     "status": "Open", "priority": "P2", "days_ago": 4,
     "description": "Procurement asked architecture for vendor consolidation options ahead of September 1 renewal."},
    {"company_id": "mercado-atlas", "subject": "Solr to Elasticsearch migration on legacy product search",
     "status": "Open", "priority": "P3", "days_ago": 17,
     "description": "Legacy Solr clusters are EOL on the team's schedule; migration to a single search platform is overdue."},

    # Searchlight Capital
    {"company_id": "searchlightcap", "subject": "Splunk renewal lock-in window: 60 days remaining",
     "status": "Open", "priority": "P1", "days_ago": 1,
     "description": "Splunk auto-renewal triggers in 60 days at $1.2M/year. CFO Sandra Park needs a TCO + displacement plan before the lock window expires."},
    {"company_id": "searchlightcap", "subject": "DORA audit prep - dashboards for deployment frequency, MTTR, change failure rate, lead time",
     "status": "In Progress", "priority": "P1", "days_ago": 12,
     "description": "June audit requires DORA-style operational resilience dashboards across all portfolio infrastructure. James Liu owns; Priya Sharma sponsors."},
    {"company_id": "searchlightcap", "subject": "Splunk storage tier costs at 7-year retention",
     "status": "Open", "priority": "P2", "days_ago": 20,
     "description": "Compliance retention drives a hot/warm storage bill of ~$340K/year inside Splunk. Architecture council asked for alternatives."},
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
