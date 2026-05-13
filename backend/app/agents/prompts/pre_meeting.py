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
- If the customer uses Splunk: always include an AutoOps talking point in the Talking Points section. AutoOps is free for all Elastic tiers (Cloud and self-managed). Splunk has no equivalent native diagnostic - each cluster health check requires a Professional Services engagement (~$15k-25k). AutoOps monitors 100+ metrics continuously and surfaces root-cause fixes with ready-to-run commands. This is a concrete, immediate TCO proof point that does not require a POC.
- Never use the em dash character. Use commas, parentheses, colons, or periods.

Pre-sales frameworks (apply per vertical; the FE refers to these as the "Listen-Say-Ask" and "How NOT to Sell" cards):

A) When the deal is Search / AI retrieval (Elasticsearch, vector, ELSER, semantic, marketplace search, GenAI grounding):
   - Listen for: inconsistent relevance, scalability / performance issues, difficulty measuring success.
   - Say: "This isn't just search, it's the retrieval layer for AI." / "You control relevance, not the vendor."
   - Ask: "What happens today when search isn't optimized?"

B) When the deal is Observability / SIEM / APM:
   - Frame Elastic as a platform; do NOT lead with standalone features like Metrics, APM, or Case Management.
   - Refuse to let the deal become a price or feature bake-off. Anchor on platform consolidation and TCO.
   - Qualify hard: surface the owner, the pain, and the timeline. No owner, no pain, no timeline, no deal.

Brief structure (5 to 6 sections, each with 3 to 5 bullets):
1. Headline & strategic context (why this meeting matters now).
2. Recent signals from news (last 30 days).
3. Likely pain points (cite tickets, transcripts, news).
4. Discovery questions to validate the hypothesis. Include the "Ask" question from the framework above when relevant.
5. Talking points (Elastic value mapped to their stack and pain). Include the "Say" lines verbatim when the deal is Search; explicitly avoid feature bake-off framing when the deal is Observability.
6. Risks & open questions (include any internal blockers worth flagging).

Plus a separate `presales_playbook` object (NOT one of the sections above):
- Decide whether the deal is Search, Observability, or Both based on the dossier's tech stack, recent signals, and the meeting title.
- Fill the three playbook items for the chosen framework with content that could ONLY have been written for THIS customer. The headings are fixed; the body must read like an FE wrote it after reading this specific dossier.
- Every body MUST name at least two of: a specific incumbent tool from the dossier (Datadog, Splunk, Grafana, OpenSearch, etc.), a specific signal (open ticket, renewal date, audit deadline, board mandate, transcript line), a named stakeholder, a concrete workload (Kafka pipeline, Kubernetes pod logs, marketplace catalog, RAG over policy PDFs, etc.). Generic framework copy with the customer's name swapped in is NOT acceptable.

- For the Search framework: items use headings "Listen for", "Say", "Ask".
  - "Listen for" must enumerate the relevance / scale / measurement signals as they would appear in THIS customer's environment (cite incumbent tools, query languages, retention rules, the actual workflow the dossier hints at).
  - "Say" must adapt the Search 101 lines ("retrieval layer for AI" and "you control relevance, not the vendor") to the customer's specific use case. Re-write them so they speak to Northwind-style observability search, or Mercado-style marketplace relevance, or a RAG-grounding story, etc. Pure verbatim slide copy is a fail; the spirit of the line must survive but the wording must reflect this account.
  - "Ask" must rewrite "What happens today when search isn't optimized?" into a workflow-specific probe that names the customer's tool chain (e.g. API gateway -> Kafka -> Kubernetes pod logs, or catalog -> autocomplete -> checkout funnel) and ends in an answerable question.

- For the Observability framework: items use headings "Lead with the platform", "Avoid the bake-off", "Qualify hard".
  - "Lead with the platform" names this customer's specific point-tool fragmentation and the consolidation story across logs + metrics + traces + security.
  - "Avoid the bake-off" identifies the specific bake-off risk for THIS deal (e.g. "Datadog will respond with a renewal discount aimed at the $X/year line"), and gives the FE the pivot off feature checklist back to TCO / consolidation.
  - "Qualify hard" MUST explicitly state whether the dossier reveals an owner, a pain, and a timeline; name them when present, flag them as MISSING when absent. End with whether this is a real deal, an early conversation, or a fishing expedition.

- If the deal is genuinely Both (the dossier shows real signal on both sides, not just a tangential mention), emit a `secondary` block with the other framework's three items filled at the same level of specificity. Do NOT emit a secondary block just to fill space; if the deal is single-vertical, leave `secondary` out.

Output the structured object via the json_schema response format. The FE will see exactly what you write."""

_PLAYBOOK_ITEM = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "heading": {
            "type": "string",
            "description": "Fixed framework heading (e.g. 'Listen for', 'Say', 'Ask', 'Lead with the platform', 'Avoid the bake-off', 'Qualify hard').",
        },
        "body": {
            "type": "string",
            "description": "Account-specific content. Cite this customer's stack, signals, tickets, and named stakeholders. Do not echo the generic framework prompt.",
        },
    },
    "required": ["heading", "body"],
}

_PLAYBOOK_BLOCK = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "framework": {
            "type": "string",
            "enum": ["search", "observability"],
            "description": "Which framework these three items belong to.",
        },
        "items": {
            "type": "array",
            "items": _PLAYBOOK_ITEM,
            "description": "Exactly three items, in the canonical heading order for the chosen framework.",
        },
    },
    "required": ["framework", "items"],
}

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
        "presales_playbook": {
            "type": "object",
            "additionalProperties": False,
            "description": "Per-account application of the SKO 2026 pre-sales frameworks. The headings are fixed; the agent fills the body of each item with content specific to this customer.",
            "properties": {
                "primary": _PLAYBOOK_BLOCK,
                "secondary": _PLAYBOOK_BLOCK,
            },
            "required": ["primary"],
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
        "presales_playbook": {
            "primary": {
                "framework": "observability",
                "items": [
                    {
                        "heading": "Lead with the platform",
                        "body": "Northwind already runs Splunk for SIEM, Datadog for APM, and Grafana for dashboards. Anchor on the consolidation story: one cluster for logs, metrics, traces, plus EU-banking SIEM. Do not open with Metrics or APM in isolation; the buyer (Mike) is fighting three-tool fatigue, not shopping for a fourth point tool.",
                    },
                    {
                        "heading": "Avoid the bake-off",
                        "body": "Datadog will push a price cut on renewal; refuse the feature checklist trap. Frame the conversation around 7-year audit retention TCO (Datadog index-rate vs Elastic frozen tier on S3) and EU banking SIEM scope, both of which Datadog cannot match natively.",
                    },
                    {
                        "heading": "Qualify hard",
                        "body": "Owner: Mike (Director of Platform Engineering) is the technical buyer; AE confirmed CFO sign-off needed above $2M. Pain: open P1 ticket on SIEM coverage gap surfaced by EU banking audit prep; $80k Datadog overage last month. Timeline: Datadog renewal November 1 is the hard date. All three qualifiers present; this is a real deal, not a fishing expedition.",
                    },
                ],
            },
        },
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
        "presales_playbook": {
            "primary": {
                "framework": "search",
                "items": [
                    {
                        "heading": "Listen for",
                        "body": "Mercado Atlas's marketplace conversion has been flat 4 quarters: that is the inconsistent-relevance signal. Solr (legacy) + Elasticsearch (new surfaces) split is the scalability tell. The board's 30 percent cost mandate plus the open P1 ticket on search relevance plateau are the difficulty-measuring-success signals.",
                    },
                    {
                        "heading": "Say",
                        "body": "Open the relevance conversation with: \"This isn't just search, it's the retrieval layer for AI.\" When Diego pushes on tuning autonomy, follow with: \"You control relevance, not the vendor.\" Both lines map to ELSER plus learning-to-rank giving them a production semantic stack without rolling their own vector pipeline.",
                    },
                    {
                        "heading": "Ask",
                        "body": "Lead Lucia (architecture council) with: \"What happens today when search isn't optimized?\" Tie her answer to the marketplace conversion number and the Sao Paulo to Buenos Aires cross-region latency she already named as a constraint.",
                    },
                ],
            },
            "secondary": {
                "framework": "observability",
                "items": [
                    {
                        "heading": "Lead with the platform",
                        "body": "Datadog renewal at $6M/year and the Solr + Elasticsearch split tee up the platform story: one cluster owns search relevance + observability + ML retrieval. Do not lead with APM or Metrics standalone; Lucia has already seen those decks from Datadog.",
                    },
                    {
                        "heading": "Avoid the bake-off",
                        "body": "Datadog will counter with a 20-30 percent renewal discount. Refuse the feature checklist. Anchor on the board's 30 percent cost target plus the latency story which Datadog has no answer for cross-region.",
                    },
                    {
                        "heading": "Qualify hard",
                        "body": "Owner: Lucia owns architecture council, Diego owns search engineering, both named on the meeting invite. Pain: marketplace conversion plateau is board-level. Timeline: Datadog renewal September 1 plus board-mandated cost review same quarter. Three qualifiers present.",
                    },
                ],
            },
        },
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
