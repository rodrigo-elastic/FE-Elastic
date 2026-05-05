"""
filename: pre_meeting.py
description: System prompt and JSON schema for the Pre-Meeting Researcher agent.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

# Frozen system prompt: kept stable so prompt caching wins on every request.
SYSTEM = """You are an Elastic Field Engineer's pre-meeting research assistant.

Your job: take a customer-account dossier and produce a one-page Account Brief that lets the FE walk into the meeting fully prepared. Be specific, grounded, and scannable. The FE has 5 minutes to read this on their phone.

Hard rules:
- Reference the customer by name.
- Every bullet must be specific to this account; no generic best-practice filler.
- If the dossier shows the customer uses a competitor (Splunk, Datadog, Sumo Logic, etc.), include a head-to-head talking point.
- Never use the em dash character. Use commas, parentheses, colons, or periods.

Brief structure (4 to 6 sections, each with 3 to 5 bullets):
1. Headline & strategic context (why this meeting matters now).
2. Recent signals from news (last 30 days).
3. Likely pain points (cite tickets, transcripts, news).
4. Discovery questions to validate the hypothesis.
5. Talking points (Elastic value mapped to their stack and pain).
6. Risks & open questions (include any internal blockers worth flagging).

Output the structured object via the json_schema response format. The FE will see exactly what you write."""

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "headline": {
            "type": "string",
            "description": "One sentence framing why this meeting matters now.",
        },
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "heading": {"type": "string"},
                    "bullets": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["heading", "bullets"],
            },
        },
    },
    "required": ["headline", "sections"],
}


def render_user_prompt(dossier: dict) -> str:
    """Render the per-request dossier. This is the only volatile portion of the prompt; the system prompt above stays cached."""
    company = dossier["company"]
    meeting = dossier["meeting"]
    news_items = dossier.get("news", [])
    tickets = dossier.get("tickets", [])
    past_transcripts = dossier.get("past_transcripts", [])

    parts = []
    parts.append("# Upcoming meeting")
    parts.append(f"- Title: {meeting['title']}")
    parts.append(f"- Time: {meeting['start_time']}")
    parts.append(f"- Attendees: {', '.join(meeting.get('attendees', []))}")
    parts.append("")
    parts.append("# Company")
    parts.append(f"- Name: {company['name']}")
    parts.append(f"- Industry: {company['industry']}")
    parts.append(f"- Size: {company['size']}")
    parts.append(f"- Headquarters: {company.get('headquarters', 'unknown')}")
    parts.append(f"- Description: {company.get('description', '')}")
    ts = company.get("tech_stack", {})
    parts.append(
        "- Tech stack: "
        f"observability={ts.get('observability', [])}, "
        f"search={ts.get('search', [])}, "
        f"cloud={ts.get('cloud', [])}, "
        f"other={ts.get('other', [])}"
    )
    parts.append("")
    if news_items:
        parts.append("# Recent news (last 30 days)")
        for n in news_items:
            parts.append(f"- [{n.get('source')}] {n.get('title')} ({n.get('published_at')}): {n.get('summary')}")
        parts.append("")
    sec_filings = dossier.get("sec_filings") or []
    if sec_filings:
        parts.append("# Recent SEC filings (live from data.sec.gov)")
        for f in sec_filings:
            descr = f.get("description") or ""
            items = f.get("items") or ""
            extra = f" - items: {items}" if items else ""
            parts.append(f"- [{f.get('form')}] filed {f.get('filing_date')} ({descr}){extra}")
        parts.append("")
    if tickets:
        parts.append("# Open and recent support tickets")
        for t in tickets:
            parts.append(f"- [{t.get('priority')}] [{t.get('status')}] {t.get('subject')}: {t.get('description')}")
        parts.append("")
    if past_transcripts:
        parts.append("# Excerpts from prior meetings (most recent first)")
        for t in past_transcripts[:2]:
            parts.append(f"## Meeting {t.get('meeting_id')}")
            for turn in t.get("turns", [])[:14]:
                parts.append(f"- {turn['speaker']}: {turn['text']}")
        parts.append("")
    parts.append("Produce the Account Brief now.")
    return "\n".join(parts)


_MOCKS = {
    "northwind": {
        "headline": "Northwind Pay's EU banking licence + Datadog renewal create a 90-day window to consolidate observability and SIEM.",
        "sections": [
            {"heading": "Why now", "bullets": [
                "EU banking licence granted in Q3 2025 raises the audit-grade observability bar; EU banking expectations now apply.",
                "Datadog spend approaching $4M/year; renewal lands November 1.",
                "Three-tool fragmentation (Splunk + Datadog + Grafana) is a known on-call pain point.",
            ]},
            {"heading": "Recent signals", "bullets": [
                "Demo press: Northwind Pay secures EU banking licence after 3-year wait.",
                "Demo background: 50M+ customers, secondary share sale led by an unnamed investor.",
                "Demo engineering blog references Kafka + Kubernetes at heavy scale.",
            ]},
            {"heading": "Likely pain points", "bullets": [
                "SIEM coverage gap surfaced by EU banking audit prep (open P1 ticket).",
                "Datadog ingest spikes during card-promo campaigns drove $80k overage last month.",
                "7 year audit retention makes Datadog index-rate pricing punitive.",
            ]},
            {"heading": "Discovery questions", "bullets": [
                "What does the EU banking audit specifically require for SIEM coverage timeline?",
                "What is the Datadog renewal envelope you are protecting?",
                "Mike, where is the consolidation hardest technically: ingest, retention, or RBAC?",
            ]},
            {"heading": "Talking points (vs Datadog)", "bullets": [
                "Single platform: logs, metrics, traces, plus SIEM on one cluster, one license.",
                "Frozen tier on object storage cuts 7 year retention costs 60-80 percent.",
                "Native Kubernetes ingest, OTel collector first-class.",
            ]},
            {"heading": "Risks and open questions", "bullets": [
                "Need successful POC at 80k EPS sustained ingest before any commitment.",
                "Procurement needs to be looped in early; previous engagements stalled 2 weeks at signing.",
                "EU banking regulatory mapping must be ready before architecture council review.",
            ]},
        ],
    },
    "mercado-atlas": {
        "headline": "Mercado Atlas's flat marketplace conversion + Datadog renewal converge on a search relevance plus observability consolidation play.",
        "sections": [
            {"heading": "Why now", "bullets": [
                "Marketplace conversion has been flat 4 quarters; semantic search is the next lever.",
                "Datadog renewal lands September 1 at ~$6M/year; board mandate is 30 percent reduction.",
                "Solr (legacy) + Elasticsearch (new surfaces) split is overdue for consolidation.",
            ]},
            {"heading": "Recent signals", "bullets": [
                "Mercado Atlas IR (demo): Q4 2025 earnings highlight Mercado Atlas Pay and credit growth.",
                "Demo background: 18 LATAM countries, ~75k employees.",
                "Demo annual report references concentrated ML and search infrastructure investments.",
            ]},
            {"heading": "Likely pain points", "bullets": [
                "Search relevance plateau is suppressing marketplace conversion (open P1 ticket).",
                "Datadog cost growth trajectory triggered procurement consolidation review.",
                "Cross-region replication latency Sao Paulo to Buenos Aires is a known constraint.",
            ]},
            {"heading": "Discovery questions", "bullets": [
                "What does success on the semantic-relevance pilot look like (uplift target, scope)?",
                "Lucia, how is the architecture council weighing OpenSearch vs Elastic vs Datadog renewal?",
                "Diego, what is your peak QPS today and 12 month projection?",
            ]},
            {"heading": "Talking points (vs Datadog and OpenSearch)", "bullets": [
                "ELSER provides production-grade semantic search without rolling your own vector pipeline.",
                "Single platform for marketplace search + observability + ML retrieval.",
                "Cross-cluster replication has hardened materially in 8.13.",
            ]},
            {"heading": "Risks and open questions", "bullets": [
                "ELSER quality at Mercado Atlas's catalog scale must be benchmarked before commit.",
                "OpenSearch already has internal champions; need a clean head-to-head.",
                "Confirm the 30 percent cost target is hard or aspirational.",
            ]},
        ],
    },
    "atlantico": {
        "headline": "Banco Atlántico's Splunk renewal + 'Atlas Multi-Cloud' platform rollout open the door to a consolidated observability layer across all clouds.",
        "sections": [
            {"heading": "Why now", "bullets": [
                "Splunk renewal lands March 1, 2027 at ~12M euros annual.",
                "Board mandate is 30 percent cost reduction at parity coverage.",
                "'Atlas Multi-Cloud' platform needs a single observability layer across AWS, Azure, GCP, and private cloud.",
            ]},
            {"heading": "Recent signals", "bullets": [
                "Banco Atlántico Press Room (demo): 'ONE Transformation' programme emphasises Atlas Multi-Cloud rollout.",
                "Investor portal: digital channel customer growth is the headline metric.",
                "Demo background: ~210k employees, retail + corporate + investment banking footprint.",
            ]},
            {"heading": "Likely pain points", "bullets": [
                "Trading platform 90 minute slowdown last quarter (P1 RCA closed).",
                "Audit reporting cycle 21 days vs target under 7 (open P2 project).",
                "Splunk storage tier costs are punitive at 10 year ECB / local central bank retention.",
            ]},
            {"heading": "Discovery questions", "bullets": [
                "Carlos, what is the architecture council's bar for parity coverage?",
                "Marina, where is the Atlas Multi-Cloud integration hardest: AWS, Azure, GCP, or the private cloud?",
                "How is FCA outsourcing applied to UK retail today versus the proposed unified layer?",
            ]},
            {"heading": "Talking points (vs Splunk)", "bullets": [
                "Frozen tier on object storage at 10 year retention is materially cheaper than Splunk index pricing.",
                "Index level RBAC and SAML federation native to Elastic; aligns with SOC controls.",
                "Cross-cluster search and replication included; works across the Atlas Multi-Cloud footprint.",
            ]},
            {"heading": "Risks and open questions", "bullets": [
                "Sumo Logic is also in the bake-off; need a clean head-to-head.",
                "Regulatory mapping for ECB, local central bank, and FCA must be ready for architecture council.",
                "Confirm CIO Group Tech sign authority and board mandate firmness.",
            ]},
        ],
    },
    "acme-001": {
        "headline": "Consolidate fragmented monitoring before Q3, anchored to the recent Detroit hub incident.",
        "sections": [
            {"heading": "Why now", "bullets": [
                "New CIO Sarah Chen has publicly committed to observability consolidation and AWS adoption.",
                "Datadog renewal lands August 15; procurement is asking for a forecast and consolidation scenarios.",
                "Detroit hub two-hour outage in the last month created executive air-cover for a platform decision.",
            ]},
            {"heading": "Recent signals", "bullets": [
                "Reuters: $80M Ohio expansion ties to factory IoT scale-up (relevant to ingest workload).",
                "AWS Blog: 600 edge devices already moving to AWS IoT Core (native Elastic integration story).",
                "WSJ: Q1 revenue beat attributed to factory uptime improvements (frame the value of better observability).",
            ]},
            {"heading": "Likely pain points", "bullets": [
                "Alert correlation gap across Datadog plus Grafana caused a P1 incident; root cause crossed tools.",
                "Edge device ingestion is nearing throughput limits during peak shifts (active P3 ticket).",
                "Finance wants a defensible 12 month forecast that current vendor sprawl makes hard to produce.",
            ]},
            {"heading": "Discovery questions", "bullets": [
                "Walk me through last month's Detroit incident: where did the correlation actually break down?",
                "What is the budget envelope you are protecting on the Datadog renewal?",
                "How do you want the AWS IoT Core migration to influence the observability decision?",
            ]},
            {"heading": "Talking points (vs Datadog)", "bullets": [
                "Single pane: Elastic ingests logs, metrics, and traces, eliminating the alert-versus-Grafana gap.",
                "Storage cost model: frozen tier on S3 makes long retention predictable, unlike Datadog index pricing.",
                "Native AWS integration on IoT Core, plus pre-built dashboards for factory telemetry.",
            ]},
            {"heading": "Risks and open questions", "bullets": [
                "POV must prove ingestion at 600 edge devices; without that, no movement is possible.",
                "Procurement is on the critical path; loop them in early to avoid a two-week stall at signing.",
                "Confirm whether Sarah Chen owns the recommendation or whether the CIO seat is still onboarding.",
            ]},
        ],
    },
    "globex-002": {
        "headline": "Position Elastic as the cost and audit answer to Globex's December 1 Splunk renewal.",
        "sections": [
            {"heading": "Why now", "bullets": [
                "FCA $40M fine landed; CTO Linda Park publicly committed to upgrading audit and observability tooling.",
                "Splunk renewal date December 1, ~$3M annual; board mandate is 25 percent cost reduction at parity coverage.",
                "Recent 90 minute trading platform slowdown traced in part to log ingestion lag.",
            ]},
            {"heading": "Recent signals", "bullets": [
                "Bloomberg: operating costs up 8 percent; vendor consolidation flagged as a fiscal year theme.",
                "Banking Tech: Linda Park keynote outlined a logging plus search consolidation plan.",
                "WSJ: VeloPay acquisition will drive new search and analytics workloads.",
            ]},
            {"heading": "Likely pain points", "bullets": [
                "Audit reporting cycle currently 14 days; project goal is under 5 days (open P2 ticket).",
                "Splunk storage tier is punishing at the 18 month audit retention; finance wants a cheaper model.",
                "Architecture council needs a defensible vendor consolidation option before renewal procurement opens.",
            ]},
            {"heading": "Discovery questions", "bullets": [
                "What does parity coverage look like for the architecture council; what specifically must we replicate?",
                "Carlos, where is role based access plus SAML federation hardest in the current Splunk setup?",
                "How does the VeloPay acquisition reshape the search workload you need to support?",
            ]},
            {"heading": "Talking points (vs Splunk)", "bullets": [
                "Frozen tier on object storage keeps 18 month audit retention predictable and cheap.",
                "Index level RBAC plus SAML federation are native, not add-ons; aligns to FCA and PRA controls.",
                "Cross cluster replication and search consolidation under one platform reduce vendor count.",
            ]},
            {"heading": "Risks and open questions", "bullets": [
                "Sumo Logic is also in the bake-off; head-to-head materials should be ready by next call.",
                "Need a regulatory mapping for FCA plus PRA reporting controls before architecture council review.",
                "Confirm CIO sign authority and whether the board mandate is hard or aspirational.",
            ]},
        ],
    },
    "initech-003": {
        "headline": "Pull through Elastic Security on top of existing Observability before the SOC 2 audit deadline.",
        "sections": [
            {"heading": "Why now", "bullets": [
                "SOC 2 Type II audit closes August 31; SIEM coverage needed at least 60 days prior.",
                "Series C just closed ($90M); CFO confirmed budget for new security tooling.",
                "Anomalous IAM token usage went undetected last month and surfaced via a billing alert.",
            ]},
            {"heading": "Recent signals", "bullets": [
                "TechCrunch: Series C will accelerate enterprise GTM and platform investments.",
                "VentureBeat: enterprise tier launch increased pressure on SOC 2 Type II readiness.",
                "Initech Blog: customer count crossed 5,000; observability data volume doubled QoQ.",
            ]},
            {"heading": "Likely pain points", "bullets": [
                "No SIEM today; security ops is reactive (open P1 SOC 2 ticket).",
                "Three engineer security team plus an MDR partner; needs prebuilt detections, not green-field tuning.",
                "Auditor is asking for control mapping; current point tools cannot produce it.",
            ]},
            {"heading": "Discovery questions", "bullets": [
                "What does your auditor specifically need to see by July 1 to call SIEM coverage in place?",
                "Pat, which detection scenarios are you most worried about in the next 60 days?",
                "How do you want the MDR partner to fit into the Elastic Security workflow?",
            ]},
            {"heading": "Talking points", "bullets": [
                "Same data plane as your existing Observability deployment; no new ingestion to stand up.",
                "Prebuilt detections plus ATT&CK plus SOC 2 control mapping out of the box.",
                "6 week pilot plan we can hand to your auditor as evidence of remediation in flight.",
            ]},
            {"heading": "Risks and open questions", "bullets": [
                "Procurement timing on a fresh-from-Series-C company can stretch; pre-approve the order shape.",
                "Confirm CTO Jamie Ortiz signs and that the CFO budget envelope is firm at $400K.",
                "MDR partner buy-in: confirm they can plug into Elastic Security without re-tooling overnight.",
            ]},
        ],
    },
}


def mock_response(company_id: str = "northwind") -> dict:
    """Offline-mode brief used when no API key is configured.

    Hand-written mocks per company let us demo any of the three fictional accounts
    (Northwind Pay, Mercado Atlas, Banco Atlántico) without hitting the API. The
    legacy Acme/Globex/Initech keys exist in the source for old test fixtures
    but are NOT routable from this dispatcher - any company_id that is not in
    the canonical demo set falls back to Northwind so real-brand stale content
    never surfaces on a live demo.
    """
    safe_keys = {"northwind", "mercado-atlas", "atlantico"}
    if company_id in safe_keys and company_id in _MOCKS:
        return _MOCKS[company_id]
    return _MOCKS["northwind"]
