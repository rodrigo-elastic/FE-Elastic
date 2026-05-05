"""
filename: post_meeting.py
description: System prompt and JSON schema for the Post-Meeting Action Engine.
date: 03-05-2026
"""
__author__ = "Rodrigo Careaga"
__copyright__ = "Copyright 2026, Rodrigo Careaga"
__version__ = "0.1.0"
__status__ = "Development"

SYSTEM = """You are an Elastic Field Engineer's post-meeting analyst.

Given a customer meeting transcript, produce structured output the FE can act on within 10 minutes of the call ending. The downstream system will push action items to Salesforce automatically and draft a follow-up email, so accuracy and grounding matter more than tone.

Hard rules:
- Every action item, MEDDPICC signal, and competitor mention must include a verbatim source quote from the transcript. No paraphrasing in the source_quote field.
- If you cannot ground a claim in the transcript, omit it.
- Owner names come from speaker labels in the transcript; never invent attendees.
- Due dates: if the transcript mentions an explicit deadline (e.g. August 15, end of Q2), include it as ISO date when possible; otherwise return null.
- impact (per action item): "high" if blocking the deal or tied to a hard external deadline; "med" if blocking a stage or stakeholder; "low" if nice-to-have or preparatory.
- MEDDPICC categories: use exactly one of Metrics, Economic Buyer, Decision Criteria, Decision Process, Identify Pain, Champion, Competition.
- Follow-up email: assume the customer reads it on Monday morning; lead with a concrete next step.
- Never use the em dash character. Use commas, parentheses, colons, or periods.

Output via the json_schema response format."""

OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "string",
            "description": "3 to 4 sentence executive summary of the meeting outcome.",
        },
        "action_items": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "title": {"type": "string"},
                    "owner_name": {"type": "string"},
                    "owner_email": {"type": ["string", "null"]},
                    "due_date": {"type": ["string", "null"]},
                    "impact": {"type": "string", "enum": ["low", "med", "high"]},
                    "description": {"type": "string"},
                    "source_quote": {"type": "string"},
                },
                "required": [
                    "title",
                    "owner_name",
                    "owner_email",
                    "due_date",
                    "impact",
                    "description",
                    "source_quote",
                ],
            },
        },
        "meddpicc_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": [
                            "Metrics",
                            "Economic Buyer",
                            "Decision Criteria",
                            "Decision Process",
                            "Identify Pain",
                            "Champion",
                            "Competition",
                        ],
                    },
                    "quote": {"type": "string"},
                    "note": {"type": ["string", "null"]},
                },
                "required": ["category", "quote", "note"],
            },
        },
        "competitor_mentions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "competitor": {"type": "string"},
                    "context": {"type": "string"},
                },
                "required": ["competitor", "context"],
            },
        },
        "follow_up_email": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "subject": {"type": "string"},
                "body_markdown": {"type": "string"},
            },
            "required": ["subject", "body_markdown"],
        },
    },
    "required": [
        "summary",
        "action_items",
        "meddpicc_signals",
        "competitor_mentions",
        "follow_up_email",
    ],
}


def render_user_prompt(company: dict, meeting: dict, transcript: dict) -> str:
    parts = [
        "# Meeting context",
        f"- Company: {company['name']} ({company['industry']})",
        f"- Meeting: {meeting['title']}",
        f"- Time: {meeting['start_time']}",
        f"- Attendees: {', '.join(meeting.get('attendees', []))}",
        "",
        "# Transcript",
    ]
    for turn in transcript.get("turns", []):
        parts.append(f"{turn['speaker']}: {turn['text']}")
    parts.append("")
    parts.append("Produce the post-meeting structured output now.")
    return "\n".join(parts)


_ACME_MOCK = {
        "summary": (
            "Acme is actively evaluating a move off Datadog before the August 15 renewal, with Sarah Chen "
            "(VP Engineering, also acting CIO) owning the recommendation and Mike Rodriguez running the "
            "technical evaluation. The team needs a successful POV on factory edge telemetry (600 devices) "
            "and a Datadog versus Elastic cost comparison to defend the budget conversation."
        ),
        "action_items": [
            {
                "title": "Send POV plan covering ingestion, alerting, and storage cost modeling",
                "owner_name": "Rodrigo (Elastic FE)",
                "owner_email": "rodrigo.careaga@elastic.co",
                "due_date": "2026-05-09",
                "impact": "high",
                "description": "Includes the 600 edge device ingestion proof and a head-to-head retention math comparison versus Datadog.",
                "source_quote": "I will send a POV plan covering ingestion, alerting, and storage cost modeling. Can we target a follow-up next week?",
            },
            {
                "title": "Draft Datadog vs Elastic competitive comparison with retention math",
                "owner_name": "Rodrigo (Elastic FE)",
                "owner_email": "rodrigo.careaga@elastic.co",
                "due_date": "2026-05-09",
                "impact": "high",
                "description": "Tie the comparison to Acme's compliance retention requirements and the Detroit hub incident.",
                "source_quote": "I will also draft a competitive comparison versus Datadog with retention math.",
            },
            {
                "title": "Loop in Acme procurement contact before the technical follow-up",
                "owner_name": "Sarah Chen (Acme VP Engineering)",
                "owner_email": "sarah.chen@acme.example",
                "due_date": "2026-05-12",
                "impact": "med",
                "description": "Avoid a two-week procurement stall at signing by introducing procurement now.",
                "source_quote": "Please loop in our procurement contact early so we do not lose two weeks at the end.",
            },
        ],
        "meddpicc_signals": [
            {
                "category": "Metrics",
                "quote": "We are spending close to 1.2 million dollars a year on Datadog alone, and that does not include Grafana or the storage we keep for compliance.",
                "note": "Anchor the value engineering at $1.2M plus.",
            },
            {
                "category": "Economic Buyer",
                "quote": "I own the recommendation. Our CIO will sign.",
                "note": "Sarah Chen is recommender; CIO seat signs.",
            },
            {
                "category": "Decision Criteria",
                "quote": "Single pane for logs, metrics, traces; native AWS integration; predictable storage costs at our retention.",
                "note": None,
            },
            {
                "category": "Decision Process",
                "quote": "End of Q2 to make the call, sign by mid Q3. Datadog renewal lands on August 15.",
                "note": "Hard renewal date drives timeline.",
            },
            {
                "category": "Identify Pain",
                "quote": "Last month our Detroit hub lost two hours of shipments. The alert fired on Datadog, but the root cause lived in Grafana, and our on-call missed the correlation.",
                "note": "Quantified business impact.",
            },
            {
                "category": "Competition",
                "quote": "We are on Datadog for APM and metrics, and Grafana on top of Prometheus for the factory side. It is fragmented.",
                "note": "Datadog incumbent, Grafana adjacent.",
            },
        ],
        "competitor_mentions": [
            {
                "competitor": "Datadog",
                "context": "Incumbent for APM and metrics; renewal August 15; ~$1.2M annual spend.",
            },
            {
                "competitor": "Grafana / Prometheus",
                "context": "Used for factory side observability; correlation gap surfaced during P1 incident.",
            },
        ],
        "follow_up_email": {
            "subject": "Recap and next step: Acme x Elastic POV plan",
            "body_markdown": (
                "Hi Sarah and Mike,\n\n"
                "Thanks for the time today. Quick recap and what I am sending over this week:\n\n"
                "**What we agreed on**\n"
                "- Datadog renewal date August 15 is the forcing function; you want a recommendation by end of Q2 and a signed decision by mid Q3.\n"
                "- Decision criteria: single pane for logs, metrics, traces; native AWS integration; predictable storage costs at your retention.\n"
                "- POV must prove ingestion of the 600 factory edge devices reliably. Without that, nothing else matters.\n\n"
                "**What I am sending by Friday**\n"
                "1. POV plan (ingestion, alerting, storage cost modeling).\n"
                "2. Competitive comparison versus Datadog with retention math anchored to your compliance window.\n\n"
                "**Next step**\n"
                "Tuesday afternoon next week works for the technical follow-up. I will introduce our procurement contact at the same time so we do not lose two weeks at signing.\n\n"
                "Thanks,\n"
                "Rodrigo"
            ),
        },
}


_GLOBEX_MOCK = {
    "summary": (
        "Globex is running a three-way bake-off between Elastic, Sumo Logic, and a Splunk renewal ahead of "
        "the December 1 Splunk contract date. MD Linda Park sponsors the project, the CIO signs, and "
        "Architecture Lead Carlos Mendez is the technical champion. The ask is a Splunk-to-Elastic migration "
        "playbook with a cost model and an FCA / PRA regulatory mapping."
    ),
    "action_items": [
        {
            "title": "Send Splunk to Elastic migration playbook with cost model",
            "owner_name": "Rodrigo (Elastic FE)",
            "owner_email": "rodrigo.careaga@elastic.co",
            "due_date": "2026-05-09",
            "impact": "high",
            "description": "Anchor the cost model to Globex's 18 month audit retention and the 25 percent reduction target.",
            "source_quote": "I will send a Splunk to Elastic migration playbook with a cost model assumption sheet.",
        },
        {
            "title": "Include FCA and PRA regulatory mapping",
            "owner_name": "Rodrigo (Elastic FE)",
            "owner_email": "rodrigo.careaga@elastic.co",
            "due_date": "2026-05-09",
            "impact": "high",
            "description": "Map Elastic controls to FCA and PRA reporting requirements so architecture council can review.",
            "source_quote": "Please. And include a regulatory mapping for FCA and PRA reporting controls.",
        },
        {
            "title": "Book technical deep dive with Carlos's team next Wednesday",
            "owner_name": "Carlos Mendez (Globex Architecture Lead)",
            "owner_email": "carlos.mendez@globex.example",
            "due_date": "2026-05-13",
            "impact": "med",
            "description": "Frozen tier on object storage, role based access at the index level, and SAML federation.",
            "source_quote": "Will do. Can we book a deep dive with Carlos's team next Wednesday?",
        },
    ],
    "meddpicc_signals": [
        {"category": "Metrics", "quote": "Audit reporting cycle from 14 days to under 5. Ingest cost down by 25 percent. Zero high severity logging incidents.", "note": "Three quantified success metrics."},
        {"category": "Economic Buyer", "quote": "I sponsor it. The CIO signs.", "note": "Linda sponsors; CIO signs."},
        {"category": "Decision Criteria", "quote": "Frozen tier on object storage at our retention scale, role based access at the index level, and SAML federation with our IDP.", "note": None},
        {"category": "Decision Process", "quote": "Architecture council reviews. Carlos is the technical champion. Decision in Q3.", "note": None},
        {"category": "Identify Pain", "quote": "We also had a 90 minute trading platform slowdown three weeks ago. Log ingestion lag was a contributing factor.", "note": "Quantified business impact."},
        {"category": "Champion", "quote": "Carlos is the technical champion.", "note": "Carlos Mendez is the technical champion."},
        {"category": "Competition", "quote": "We are evaluating Elastic, Sumo Logic, and a Splunk renewal as the three options.", "note": "Three-way bake-off."},
    ],
    "competitor_mentions": [
        {"competitor": "Splunk", "context": "Incumbent; ~$3M annual; renewal December 1; storage tier costs flagged as punishing."},
        {"competitor": "Sumo Logic", "context": "Also evaluated in the three-way bake-off."},
    ],
    "follow_up_email": {
        "subject": "Recap and next step: Globex x Elastic Splunk migration playbook",
        "body_markdown": (
            "Hi Linda and Carlos,\n\n"
            "Thanks for the time today. Recap and what is coming this week:\n\n"
            "**What we agreed on**\n"
            "- Splunk renewal December 1 is the forcing date; board mandate is 25 percent cost reduction at parity coverage.\n"
            "- Twelve month success metrics: audit reporting cycle from 14 days to under 5; zero high severity logging incidents.\n"
            "- Technical bar: frozen tier on object storage, index level RBAC, SAML federation with your IDP.\n\n"
            "**What I am sending by Friday**\n"
            "1. Splunk to Elastic migration playbook with cost model assumption sheet.\n"
            "2. FCA and PRA regulatory control mapping.\n\n"
            "**Next step**\n"
            "Wednesday next week for the technical deep dive with Carlos's team.\n\n"
            "Thanks,\n"
            "Rodrigo"
        ),
    },
}


_INITECH_MOCK = {
    "summary": (
        "Initech needs SIEM coverage in place at least 60 days before the August 31 SOC 2 Type II audit "
        "closes, with $400K budget approved for this fiscal year. Pat (Head of Security) is our champion "
        "and CTO Jamie Ortiz signs. Their existing Elastic Observability deployment is the natural data "
        "plane; the ask is a 6 week pilot plan we can hand to their auditor."
    ),
    "action_items": [
        {
            "title": "Tee up Security overview and value engineering session",
            "owner_name": "Rodrigo (Elastic FE)",
            "owner_email": "rodrigo.careaga@elastic.co",
            "due_date": "2026-05-09",
            "impact": "high",
            "description": "Include CIS plus SOC 2 control mapping and prebuilt detections demo on Initech's logs.",
            "source_quote": "I can tee up a Security overview and a value engineering session next week.",
        },
        {
            "title": "Send 6 week pilot plan formatted for the auditor",
            "owner_name": "Rodrigo (Elastic FE)",
            "owner_email": "rodrigo.careaga@elastic.co",
            "due_date": "2026-05-12",
            "impact": "high",
            "description": "Hand-off ready document showing remediation in flight, mapped to SOC 2 Type II controls.",
            "source_quote": "And a six week pilot plan we can show our auditor.",
        },
        {
            "title": "Confirm MDR partner can plug into Elastic Security",
            "owner_name": "Pat Nguyen (Initech Head of Security)",
            "owner_email": "pat.nguyen@initech.example",
            "due_date": "2026-05-15",
            "impact": "med",
            "description": "Validate overnight detection workflow before pilot kickoff.",
            "source_quote": "Three engineers on security ops, plus a managed detection partner on overnights.",
        },
    ],
    "meddpicc_signals": [
        {"category": "Metrics", "quote": "Budget approved for this fiscal year is 400 thousand dollars for SIEM tooling, plus headcount.", "note": "Quantified budget."},
        {"category": "Economic Buyer", "quote": "Budget approved for this fiscal year is 400 thousand dollars for SIEM tooling, plus headcount.", "note": "Jamie controls the budget."},
        {"category": "Decision Criteria", "quote": "Same data plane as our logs, prebuilt detections, audit trail mapping to SOC 2 controls.", "note": None},
        {"category": "Decision Process", "quote": "SOC 2 Type II audit closes August 31. We need SIEM coverage in place 60 days before.", "note": "Hard external deadline."},
        {"category": "Identify Pain", "quote": "Threat detection is reactive. Last month we missed an anomalous IAM token use until our cloud bill flagged it.", "note": "Concrete miss."},
        {"category": "Champion", "quote": "We are using point tools today, no real SIEM. Logs are in Elastic Observability already, which is the natural fit.", "note": "Pat is anchoring on the existing Elastic deployment."},
    ],
    "competitor_mentions": [],
    "follow_up_email": {
        "subject": "Recap and next step: Initech x Elastic Security pilot plan",
        "body_markdown": (
            "Hi Pat and Jamie,\n\n"
            "Thanks for the time today. Recap and what is coming this week:\n\n"
            "**What we agreed on**\n"
            "- SOC 2 Type II audit closes August 31; SIEM coverage must be in place 60 days before.\n"
            "- Decision criteria: same data plane as Observability, prebuilt detections, audit trail mapping to SOC 2 controls.\n"
            "- Budget envelope: $400K for tooling plus headcount.\n\n"
            "**What I am sending by Friday**\n"
            "1. Security overview plus value engineering deck with CIS and SOC 2 control mapping.\n"
            "2. 6 week pilot plan formatted for the auditor.\n\n"
            "**Next step**\n"
            "Confirm MDR partner workflow before pilot kickoff.\n\n"
            "Thanks,\n"
            "Rodrigo"
        ),
    },
}


_NORTHWIND_MOCK = {
    "summary": (
        "Northwind Pay is consolidating observability + SIEM ahead of a November 1 Datadog renewal "
        "(approx $4M annual). EU banking licence (Q3 2025) raises the audit bar. Sarah Chen "
        "(VP Engineering) sponsors; CTO signs; Mike Taylor (Platform Lead) runs the technical eval. "
        "Decision by end of Q3 2026 with a 6 month migration window."
    ),
    "action_items": [
        {
            "title": "Send POC plan: 80k EPS ingest + MITRE ATT&CK + Datadog cost comparison",
            "owner_name": "Rodrigo (Elastic FE)",
            "owner_email": "rodrigo.careaga@elastic.co",
            "due_date": "2026-05-09",
            "impact": "high",
            "description": "POC must validate sustained 80k EPS, SIEM coverage to MITRE, and a cost comparison anchored to 7 year audit retention.",
            "source_quote": "I will send a POC plan covering ingest at 80k EPS, SIEM coverage to MITRE ATT&CK, and a Datadog cost comparison.",
        },
        {
            "title": "Draft EU banking regulatory mapping for the architecture council",
            "owner_name": "Rodrigo (Elastic FE)",
            "owner_email": "rodrigo.careaga@elastic.co",
            "due_date": "2026-05-12",
            "impact": "high",
            "description": "EU banking expectations on audit-grade observability post EU banking licence; map to native Elastic controls.",
            "source_quote": "I will also draft a regulatory mapping for the EU banking expectations.",
        },
        {
            "title": "Loop in Northwind Pay procurement before the technical follow-up",
            "owner_name": "Sarah Chen (Northwind Pay VP Engineering)",
            "owner_email": "sarah.chen@northwindpay.example",
            "due_date": "2026-05-13",
            "impact": "med",
            "description": "Avoid the two-week procurement stall they hit last engagement.",
            "source_quote": "Please loop in our procurement contact early; we lost two weeks last time.",
        },
    ],
    "meddpicc_signals": [
        {"category": "Metrics", "quote": "our Datadog spend is approaching 4 million a year", "note": "Anchor value engineering at $4M annual."},
        {"category": "Economic Buyer", "quote": "I sponsor it. Our CTO signs.", "note": "Sarah recommends; CTO signs."},
        {"category": "Decision Criteria", "quote": "single platform for logs, metrics, traces, plus SIEM. Native Kubernetes ingestion. Predictable storage costs at our 7 year audit retention.", "note": None},
        {"category": "Decision Process", "quote": "Decision by end of Q3 2026. Datadog renewal is November 1.", "note": "Hard renewal date drives timeline."},
        {"category": "Identify Pain", "quote": "We have a SIEM gap. We use Splunk for security, Datadog for app metrics, Grafana on Prometheus for infra.", "note": "Three-tool fragmentation."},
        {"category": "Champion", "quote": "Mike runs the technical evaluation.", "note": "Mike Taylor is the technical champion."},
        {"category": "Competition", "quote": "Datadog renewal is November 1.", "note": "Datadog is the incumbent on observability; Splunk on security."},
    ],
    "competitor_mentions": [
        {"competitor": "Datadog", "context": "Incumbent on observability; ~$4M annual; renewal November 1, 2026."},
        {"competitor": "Splunk", "context": "Currently used for security; one of three observability tools the team wants to consolidate."},
    ],
    "follow_up_email": {
        "subject": "Recap and next step: Northwind Pay x Elastic POC plan",
        "body_markdown": (
            "Hi Sarah and Mike,\n\n"
            "Thanks for the time today. Recap and what is coming this week:\n\n"
            "**What we agreed on**\n"
            "- Datadog renewal date November 1 is the forcing function; recommendation by end of Q3 2026.\n"
            "- Decision criteria: single platform for logs/metrics/traces/SIEM, native Kubernetes ingest, predictable storage at 7 year retention.\n"
            "- POC must prove sustained 80k EPS ingest. Without that, no movement.\n\n"
            "**What I am sending by Friday**\n"
            "1. POC plan (ingest, SIEM coverage to MITRE ATT&CK, storage cost modelling).\n"
            "2. EU banking regulatory mapping deck.\n\n"
            "**Next step**\n"
            "Tuesday afternoon EU time for the technical follow-up; I will introduce procurement at the same time.\n\n"
            "Thanks,\n"
            "Rodrigo"
        ),
    },
}


_MERCADO_ATLAS_MOCK = {
    "summary": (
        "Mercado Atlas is running a three-way evaluation (Elastic, OpenSearch, Datadog renewal) ahead "
        "of a September 1 Datadog renewal (approx $6M annual). Search relevance has plateaued; semantic "
        "relevance is the lever. Lucia Fernandez (Director of Engineering) sponsors; CTO signs; Diego "
        "Alvarez (Search Tech Lead) is the technical champion."
    ),
    "action_items": [
        {
            "title": "Send search relevance benchmark and ELSER quality assessment at Mercado Atlas catalog scale",
            "owner_name": "Rodrigo (Elastic FE)",
            "owner_email": "rodrigo.careaga@elastic.co",
            "due_date": "2026-05-09",
            "impact": "high",
            "description": "Benchmark must demonstrate p99 < 80ms search latency at 10x current QPS.",
            "source_quote": "I'll send a search relevance benchmark and a Datadog migration cost model.",
        },
        {
            "title": "Datadog migration cost model for September 1 renewal",
            "owner_name": "Rodrigo (Elastic FE)",
            "owner_email": "rodrigo.careaga@elastic.co",
            "due_date": "2026-05-09",
            "impact": "high",
            "description": "Anchor to the 30 percent reduction board mandate; cover both observability and search workloads.",
            "source_quote": "Datadog renews September 1. We are evaluating Elastic, OpenSearch, and Datadog renewal. Board mandate is 30 percent cost reduction.",
        },
        {
            "title": "Book technical deep dive next Wednesday with Diego's search team",
            "owner_name": "Lucia Fernandez (Mercado Atlas Director of Engineering)",
            "owner_email": "lucia.fernandez@mercadoatlas.example",
            "due_date": "2026-05-13",
            "impact": "med",
            "description": "Cover dense vector ingest throughput, ELSER, and Sao Paulo to Buenos Aires CCR latency.",
            "source_quote": "Can we book a deep dive next Wednesday?",
        },
    ],
    "meddpicc_signals": [
        {"category": "Metrics", "quote": "Search latency p99 under 80ms at 10x our current QPS. Observability ingest cost down 30 percent. Conversion lift of 2 percent on semantic-relevance pilot.", "note": "Three quantified success metrics."},
        {"category": "Economic Buyer", "quote": "I sponsor. CTO signs.", "note": "Lucia sponsors; CTO signs."},
        {"category": "Decision Criteria", "quote": "ELSER quality at our catalog scale, dense vector ingest throughput, and cross-region replication latency Sao Paulo to Buenos Aires.", "note": None},
        {"category": "Decision Process", "quote": "Architecture council reviews. Diego is the technical champion. Decision in Q3 2026.", "note": None},
        {"category": "Identify Pain", "quote": "Search relevance on the marketplace is plateauing; conversion is flat quarter over quarter.", "note": "Quantified business pain."},
        {"category": "Champion", "quote": "Diego is the technical champion.", "note": "Diego Alvarez is the technical champion."},
        {"category": "Competition", "quote": "We are evaluating Elastic, OpenSearch, and Datadog renewal.", "note": "Three-way bake-off."},
    ],
    "competitor_mentions": [
        {"competitor": "Datadog", "context": "Incumbent on observability; ~$6M annual; renewal September 1, 2026."},
        {"competitor": "OpenSearch", "context": "Internal champions exist; needs a clean head-to-head."},
    ],
    "follow_up_email": {
        "subject": "Recap and next step: Mercado Atlas x Elastic search relevance plus migration plan",
        "body_markdown": (
            "Hi Lucia and Diego,\n\n"
            "Thanks for the time today. Recap and what is coming this week:\n\n"
            "**What we agreed on**\n"
            "- Datadog renewal September 1 is the forcing date; board mandate 30 percent cost reduction.\n"
            "- Twelve month success metrics: p99 search latency under 80ms at 10x QPS, ingest cost down 30 percent, +2 percent conversion lift on semantic relevance pilot.\n"
            "- Technical bar: ELSER quality at catalog scale, dense vector ingest, Sao Paulo to Buenos Aires CCR latency.\n\n"
            "**What I am sending by Friday**\n"
            "1. Search relevance benchmark deck plus ELSER quality assessment.\n"
            "2. Datadog migration cost model anchored to the 30 percent target.\n\n"
            "**Next step**\n"
            "Wednesday next week for the technical deep dive with Diego's team.\n\n"
            "Thanks,\n"
            "Rodrigo"
        ),
    },
}


_ATLANTICO_MOCK = {
    "summary": (
        "Banco Atlántico is running a three-way bake-off (Elastic, Sumo Logic, Splunk renewal) ahead of "
        "the March 2027 Splunk renewal at ~12M euros annual. The 'Atlas Multi-Cloud' platform "
        "needs one observability layer across AWS, Azure, GCP, and the private cloud. Carlos Ruiz "
        "(MD Tech) sponsors; CIO Group Tech signs; Marina Lopez (Architecture Lead) is the champion."
    ),
    "action_items": [
        {
            "title": "Splunk to Elastic migration playbook with cost model and Atlas Multi-Cloud integration plan",
            "owner_name": "Rodrigo (Elastic FE)",
            "owner_email": "rodrigo.careaga@elastic.co",
            "due_date": "2026-05-09",
            "impact": "high",
            "description": "Anchor cost model to 10 year ECB / local central bank audit retention and the 30 percent reduction board target.",
            "source_quote": "I'll send a Splunk to Elastic migration playbook plus regulatory mapping for ECB, local central bank, and FCA reporting controls.",
        },
        {
            "title": "Regulatory mapping for ECB, local central bank, and FCA reporting",
            "owner_name": "Rodrigo (Elastic FE)",
            "owner_email": "rodrigo.careaga@elastic.co",
            "due_date": "2026-05-12",
            "impact": "high",
            "description": "Map native Elastic controls (frozen tier, RBAC, SAML, audit log) to ECB, local central bank, and UK FCA reporting requirements.",
            "source_quote": "Frozen tier on object storage at 10 year retention, role based access at index level, SAML federation with our internal IDP, and clean integration with Atlas Multi-Cloud.",
        },
        {
            "title": "Book technical deep dive next Wednesday with Marina's architecture team",
            "owner_name": "Carlos Ruiz (Banco Atlántico MD Tech)",
            "owner_email": "carlos.ruiz@bancoatlantico.example",
            "due_date": "2026-05-13",
            "impact": "med",
            "description": "Frozen tier at 10 year retention, RBAC, SAML federation, and Atlas Multi-Cloud integration.",
            "source_quote": "Can we book a deep dive with Marina's architecture team next Wednesday?",
        },
    ],
    "meddpicc_signals": [
        {"category": "Metrics", "quote": "Audit reporting from 21 days to under 7. Storage cost down 35 percent. Zero high severity logging incidents during peak trading windows.", "note": "Three quantified success metrics."},
        {"category": "Economic Buyer", "quote": "I sponsor it. CIO Group Tech signs.", "note": "Carlos sponsors; CIO Group Tech signs."},
        {"category": "Decision Criteria", "quote": "Frozen tier on object storage at 10 year retention, role based access at index level, SAML federation with our internal IDP, and clean integration with Atlas Multi-Cloud.", "note": None},
        {"category": "Decision Process", "quote": "Architecture council reviews. Marina is the technical champion. Decision in Q4 2026.", "note": None},
        {"category": "Identify Pain", "quote": "We also had a 90 minute trading platform slowdown last quarter. Log ingestion lag was a contributing factor.", "note": "Quantified business impact."},
        {"category": "Champion", "quote": "Marina is the technical champion.", "note": "Marina Lopez is the architecture champion."},
        {"category": "Competition", "quote": "Evaluating Elastic, Sumo Logic, and Splunk renewal.", "note": "Three-way bake-off."},
    ],
    "competitor_mentions": [
        {"competitor": "Splunk", "context": "Incumbent; ~12M euros annual; renewal March 1, 2027; storage tier costs flagged at 10 year retention."},
        {"competitor": "Sumo Logic", "context": "Also evaluated in the three-way bake-off."},
    ],
    "follow_up_email": {
        "subject": "Recap and next step: Banco Atlántico x Elastic Splunk migration playbook",
        "body_markdown": (
            "Hi Carlos and Marina,\n\n"
            "Thanks for the time today. Recap and what is coming this week:\n\n"
            "**What we agreed on**\n"
            "- Splunk renewal March 2027 is the forcing date; board mandate 30 percent cost reduction.\n"
            "- Twelve month success metrics: audit reporting cycle from 21 days to under 7; storage cost down 35 percent; zero high severity logging incidents.\n"
            "- Technical bar: frozen tier at 10 year retention, index level RBAC, SAML federation with internal IDP, clean Atlas Multi-Cloud integration.\n\n"
            "**What I am sending by Friday**\n"
            "1. Splunk to Elastic migration playbook with cost model.\n"
            "2. Regulatory mapping for ECB, local central bank, and FCA controls.\n\n"
            "**Next step**\n"
            "Wednesday next week for the technical deep dive with Marina's architecture team.\n\n"
            "Thanks,\n"
            "Rodrigo"
        ),
    },
}


_MOCKS = {
    "northwind": _NORTHWIND_MOCK,
    "mercado-atlas": _MERCADO_ATLAS_MOCK,
    "atlantico": _ATLANTICO_MOCK,
}
# The acme/globex/initech fixtures live in the source for historical
# regression-test purposes (some old test_pdf_builder.py asserts hit them
# via direct module import, NOT through the mock_response dispatcher).
# They are intentionally NOT exposed through the mock_response lookup so
# they cannot leak into a live demo. If a stale company_id slips through,
# we fall back to the Northwind fixture.


def mock_response(company_id: str = "northwind") -> dict:
    """Offline-mode result keyed by company. Hand-written so the demo runs without the Anthropic API.

    Only the canonical fictional demo keys (northwind, mercado-atlas, atlantico)
    are routable. Anything else (including legacy acme/globex/initech ids) falls
    back to the Northwind fixture so no real-brand stale content ever surfaces
    on a live demo.
    """
    return _MOCKS.get(company_id, _NORTHWIND_MOCK)
