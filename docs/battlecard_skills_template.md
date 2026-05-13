# Battlecard Skills Template

Canonical reference for provisioning per-competitor skills into Kibana Agent Builder
from `backend/data/seed/battlecards.json`. Aligns the FE Copilot conventions with the
upstream spec at https://github.com/elastic/agent-skills.

This document is the source of truth for:

1. The shape of the `SKILL.md` artifact (frontmatter + body) we produce per competitor.
2. The JSON payload we POST to `POST /api/agent_builder/skills` (the in-cluster
   representation of that same skill).
3. The FE Copilot conventions layered on top (id prefix, tool_ids, labels).

The `battlecard_skill_builder.py` helper at
`backend/app/services/battlecard_skill_builder.py` is the executable embodiment of
this template; the parallel provisioner script
(`backend/scripts/sync_battlecard_agents.py`) is its only consumer.

---

## 1. Canonical SKILL.md frontmatter (from elastic/agent-skills)

The upstream repo (https://github.com/elastic/agent-skills) defines a SKILL.md as a
Markdown file with a YAML frontmatter block. The spec is intentionally small: the
`description` field is "the sole trigger mechanism" the agent uses to decide whether
to activate the skill.

```yaml
---
name: elasticsearch-esql            # REQUIRED. Skill id. lowercase, hyphen-separated.
description: >                       # REQUIRED. Multi-line. Must say WHAT the skill
  Generate ES|QL queries against an  # does AND WHEN the agent should activate it.
  Elasticsearch cluster. Use when
  the user asks about SPL conversion,
  log search, or pipeline-style queries.
metadata:
  author: elastic                    # OPTIONAL. Free-form string.
  version: 0.1.1                     # REQUIRED. Semver.
  visibility: public                 # OPTIONAL. public | private. Defaults to public.
---

# Body content (Markdown)

Free-form instructions, examples, do/don't lists, links.
The body is what the LLM reads at activation time; keep it tight, action-oriented,
and grounded in concrete content (no fluff).
```

### Field-by-field (upstream)

| Field                  | Required | Notes                                                                                             |
|------------------------|----------|---------------------------------------------------------------------------------------------------|
| `name`                 | yes      | Slug. `{category}-{topic}`. Lowercase, hyphen-separated. Must be unique per cluster.              |
| `description`          | yes      | The activation trigger. Should answer "what does this do" + "when do I call it".                  |
| `metadata.version`     | yes      | Semver. Bump on every content change so the provisioner can dedupe upserts.                       |
| `metadata.author`      | no       | Free-form. We use `fe-copilot` for everything we provision.                                       |
| `metadata.visibility`  | no       | Defaults to `public`. Leave unset unless we have a reason to scope it.                            |
| Body (markdown)        | yes      | The agent reads it at activation time. Keep under ~6KB; cite tools the skill expects to invoke.   |

### Conventions NOT in the upstream spec but used by FE Copilot

The upstream `SKILL.md` schema does not include `tool_ids`, `labels`, or
`referenced_content` at the frontmatter level. Those live in the Kibana Agent Builder
**API payload** (the JSON we POST), not in the markdown artifact. Concretely:

- `tool_ids`: array of registered Agent Builder tool ids the skill is allowed to call.
  Validated server-side against the tool catalogue (see
  `backend/app/api/routes_agent_builder.py` line ~450). Unknown ids -> 400.
- `labels`: array of free-form tags. Used by the Agent Builder UI for filtering.
- `referenced_content`: not used by our deployment. The upstream repo bundles sub-files
  alongside SKILL.md (e.g. `node scripts/esql.js test`); the Kibana 9.x Agent Builder
  API in our cluster does not yet accept sub-file uploads, so we keep all content inline
  in the `content` field of the skill payload. If the API later adds sub-file support,
  add a `referenced_content: [{name, content}, ...]` array to the payload.

---

## 2. Kibana Agent Builder skill payload (what we POST)

`backend/app/integrations/agent_builder.py::upsert_skill()` sends this shape to
`POST /api/agent_builder/skills` (or `PUT /api/agent_builder/skills/{id}` when the
skill already exists).

```jsonc
{
  "id": "fec_battlecard_skill_<slug>",   // REQUIRED. Unique per cluster.
  "name": "Battlecard: <Competitor>",    // REQUIRED. Human-readable.
  "description": "...",                  // REQUIRED. Activation trigger.
  "content": "<markdown body>",          // REQUIRED. The skill body. Mirrors SKILL.md body.
  "tool_ids": ["fec_compare", ...],      // OPTIONAL but strongly recommended.
  "labels": ["competitive", ...],        // OPTIONAL. Free-form tags.
  "metadata": {                          // OPTIONAL. Mirrors the SKILL.md frontmatter.
    "author": "fe-copilot",
    "version": "0.1.0",
    "visibility": "public",
    "competitor": "<Competitor>",
    "vertical": "<vertical>",
    "industries": ["..."],
    "is_main_competitor": true
  }
}
```

The `upsert_skill()` helper already handles create-vs-update, so the provisioner just
builds the dict (with the helper described below) and calls `upsert_skill(payload)`.

---

## 3. FE Copilot conventions for competitor battlecard skills

### 3.1 Id

- Prefix: `fec_battlecard_skill_`
- Suffix: `competitor_slug` from the battlecard, lowercased, non-alphanumerics replaced
  with `_`. e.g. `fec_battlecard_skill_splunk`, `fec_battlecard_skill_datadog`,
  `fec_battlecard_skill_aws_opensearch`.
- The companion **agent** (separate object) uses `fec_battlecard_<slug>`. Do not confuse
  the two ids.

### 3.2 Name

- `Battlecard: <Competitor>` (use the original casing from `competitor`, e.g. "Splunk",
  "Datadog", "AWS OpenSearch").

### 3.3 Description (the activation trigger)

Single sentence. Pattern:

> "Activate when the user asks about Elastic versus `<Competitor>`, references
> `<Competitor>`-specific terminology, or needs talking points / objection handling
> for a `<Competitor>` replacement. Grounded in the `<id>` battlecard."

### 3.4 Labels

Always include:

- `"competitive"` (so the Agent Builder UI groups battlecard skills together).
- The card's `vertical` (e.g. `"observability_logs"`, `"search"`, `"security"`).
- Each entry of `industries` (e.g. `"fsi-banking"`, `"gov-federal"`).
- `"main-competitor"` only when `is_main_competitor` is `true`.

### 3.5 tool_ids (the four canonical ones)

Every competitive battlecard skill should declare these four tool_ids so the agent can
chain to richer flows when needed. They are validated against the Agent Builder tool
catalogue at provisioning time (see `routes_agent_builder.py:450`).

| Tool id              | Why it's wired into every battlecard skill                                          |
|----------------------|-------------------------------------------------------------------------------------|
| `fec_compare`        | Deep technical / cost head-to-head. Always the primary follow-up.                   |
| `fec_cost_calc`      | TCO modeling when the conversation pivots to pricing.                                |
| `fec_proposal`       | One-page customer-ready output when the rep wants to close the loop.                 |
| `fec_knowledge_search` | Backstop for product-specific questions the battlecard does not cover.             |

Do not add other tool_ids unless a battlecard explicitly needs them.

### 3.6 metadata

- `author`: always `"fe-copilot"`.
- `version`: start at `"0.1.0"`. Bump the patch on every content change (the
  provisioner will diff content and bump if needed in a future iteration).
- `visibility`: omit (defaults to `public`).
- Mirror `competitor`, `vertical`, `industries`, `is_main_competitor` into metadata so
  the Kibana UI can filter.

### 3.7 Body content

Section order, kept tight and action-oriented:

1. `# When to use this skill` - one paragraph echoing the description.
2. `# Tagline` - one line, pulled verbatim from the battlecard.
3. `# Key pain` - one paragraph from `key_pain`.
4. `# Talking points` - bullets, each with angle / claim / proof from `talking_points`.
5. `# Elastic advantages` - bullets from `elastic_advantages`.
6. `# Common objections` - Q/A pairs from `common_objections`.
7. `# Discovery questions` - bullets from `discovery_questions`.
8. `# Follow-up tools` - one line per `tool_id` with a short rationale.
9. `# Style` - one-liner forbidding em dashes and reminding the agent to cite the
   battlecard id (`battlecard-<slug>`) in `sources`.

---

## 4. Gold-standard example: Splunk

The Splunk battlecard is the richest entry in `battlecards.json`
(`is_main_competitor: true`, 10 industries). The provisioner output for it should
exactly equal this payload (modulo whitespace).

```json
{
  "id": "fec_battlecard_skill_splunk",
  "name": "Battlecard: Splunk",
  "description": "Activate when the user asks about Elastic versus Splunk, references Splunk-specific terminology (SPL, Splunk Enterprise Security, Splunk Observability Cloud), or needs talking points / objection handling for a Splunk replacement. Grounded in the battlecard-splunk battlecard.",
  "tool_ids": ["fec_compare", "fec_cost_calc", "fec_proposal", "fec_knowledge_search"],
  "labels": [
    "competitive",
    "main-competitor",
    "observability_logs",
    "fsi-banking",
    "fsi-insurance",
    "fsi-capital-markets",
    "gov-federal",
    "gov-state-local",
    "telco",
    "media-streaming",
    "tech-saas",
    "energy-utilities",
    "healthcare-payers"
  ],
  "metadata": {
    "author": "fe-copilot",
    "version": "0.1.0",
    "competitor": "Splunk",
    "vertical": "observability_logs",
    "industries": [
      "fsi-banking", "fsi-insurance", "fsi-capital-markets",
      "gov-federal", "gov-state-local", "telco",
      "media-streaming", "tech-saas", "energy-utilities", "healthcare-payers"
    ],
    "is_main_competitor": true
  },
  "content": "# When to use this skill\nActivate when the user asks about Elastic versus Splunk, references Splunk-specific terminology, or needs talking points / objection handling for a Splunk replacement. Grounded in the battlecard-splunk battlecard.\n\n# Tagline\nCost-effective alternative for log analytics at audit-grade retention.\n\n# Key pain\nLicense plus storage costs are punitive at compliance retention windows. Index-time pricing scales linearly with ingest, not value.\n\n# Talking points\n- TCO - Frozen tier on object storage cuts long-retention costs 60 to 80 percent. (Proof: Searchable snapshots on S3 / GCS / Azure Blob: pay storage rates, not warm-tier hot rates. Typical 18 month audit retention drops from $X to $X/4.)\n- Single platform - Logs, metrics, APM, and Security in one cluster on one license. (Proof: Eliminates Splunk Observability Cloud upsell + Splunk Enterprise Security add-on. Same data plane for ops + sec teams.)\n- Open data format - ECS plus Lucene index files are documented and exportable. No proprietary lock-in. (Proof: Customers can read raw index files; no vendor egress fee to leave Elastic.)\n\n# Elastic advantages\n- Frozen tier on object storage at retention scale\n- Native cross-cluster search and replication included\n- Built-in ML anomaly detection (no separate license)\n- Open inference API for vector and sparse retrieval (ELSER)\n- Marketplace billing on AWS / GCP / Azure\n\n# Common objections\n- Q: We have years of SPL queries; rewriting is a non-starter.\n  A: ES|QL went GA in 8.13. SPL to ES|QL conversion docs are public; most queries map mechanically. Splunk-style pipe syntax is preserved.\n- Q: Splunk Enterprise Security is more mature for SIEM.\n  A: Elastic Security ships MITRE ATT&CK coverage with prebuilt detections, plus a purpose-built threat-hunting workspace. Dashboarding parity since 8.x.\n- Q: Migration risk on a critical observability platform.\n  A: Side-by-side dual-ingest period via Logstash or Filebeat outputs both targets. POV path validates parity before cutover.\n\n# Discovery questions\n- What is your audit retention requirement and what does the storage cost line look like today?\n- How many license tiers are you paying for across Splunk Core, Observability, and Enterprise Security?\n- If you had to consolidate to one platform in 12 months, what's the blocker?\n\n# Follow-up tools\n- fec_compare: structured technical and cost head-to-head Elastic vs Splunk.\n- fec_cost_calc: TCO model when the conversation pivots to pricing.\n- fec_proposal: one-page customer-ready output when the rep wants to close the loop.\n- fec_knowledge_search: backstop for product questions the battlecard does not cover.\n\n# Style\nNever use the em dash character. Always cite battlecard-splunk in the sources array when this skill grounded the answer."
}
```

---

## 5. Minimum-content example: Honeycomb

For a non-flagship competitor the structure is identical but the labels list is
shorter and `is_main_competitor` is `false`. This is the bar a generated skill needs
to clear at minimum.

```json
{
  "id": "fec_battlecard_skill_honeycomb",
  "name": "Battlecard: Honeycomb",
  "description": "Activate when the user asks about Elastic versus Honeycomb, references Honeycomb-specific terminology (BubbleUp, wide events), or needs talking points / objection handling for a Honeycomb replacement. Grounded in the battlecard-honeycomb battlecard.",
  "tool_ids": ["fec_compare", "fec_cost_calc", "fec_proposal", "fec_knowledge_search"],
  "labels": [
    "competitive",
    "observability_logs",
    "tech-saas",
    "retail-ecommerce",
    "fsi-insurance"
  ],
  "metadata": {
    "author": "fe-copilot",
    "version": "0.1.0",
    "competitor": "Honeycomb",
    "vertical": "observability_logs",
    "industries": ["tech-saas", "retail-ecommerce", "fsi-insurance"],
    "is_main_competitor": false
  },
  "content": "# When to use this skill\nActivate when the user asks about Elastic versus Honeycomb, references Honeycomb-specific terminology, or needs talking points / objection handling for a Honeycomb replacement. Grounded in the battlecard-honeycomb battlecard.\n\n# Tagline\nWide-event observability with logs, metrics and security on the same cluster.\n\n# Key pain\nHoneycomb's event model and BubbleUp are excellent for high-cardinality debugging, but the platform is traces and events only. No logs, no metrics-as-first-class, no security. Customers buy Honeycomb plus another tool.\n\n# Talking points\n- Scope of platform - Honeycomb is APM-adjacent; Elastic covers logs, metrics, APM, RUM and Security. (Proof: Customers running Honeycomb almost always pair it with a separate log tool. Consolidating reduces the bill and the context-switch cost.)\n- OpenTelemetry parity - Both Honeycomb and Elastic are OTel-native; no instrumentation rewrite required. (Proof: Customers can ship OTel data to Elastic via OTLP; the EDOT distribution adds value-add processors.)\n- BubbleUp equivalent - Elastic ML anomaly detection plus Lens 'top contributors' covers the high-cardinality slice analysis. (Proof: The workflow is different but the outcome is the same.)\n\n# Elastic advantages\n- Logs, metrics, APM and security on one cluster\n- OTel-native ingest with EDOT\n- Frozen tier for long event retention\n- ML anomaly detection across all signals\n- Self-hosted, cloud or air-gapped\n\n# Common objections\n- Q: Honeycomb's BubbleUp is faster than anything else for high-cardinality root cause.\n  A: On their core workflow, true. The question is whether the rest of the stack is worth the second tool.\n- Q: Honeycomb's query latency on wide events is sub-second.\n  A: Elastic with hot-tier nodes hits sub-second on similar workloads. Worth benchmarking with the customer's actual queries during the POV.\n- Q: Our team likes the tracing-first mental model.\n  A: Elastic APM has the same trace-first views. Discover and Lens are available when the team needs to leave the trace context.\n\n# Discovery questions\n- What other observability tools sit alongside Honeycomb today?\n- Is your team primarily SRE/dev or does Platform/Security need access too?\n- How are you handling logs and what is that bill?\n- How much of your Honeycomb spend is event volume versus retention?\n\n# Follow-up tools\n- fec_compare: structured technical and cost head-to-head Elastic vs Honeycomb.\n- fec_cost_calc: TCO model when the conversation pivots to pricing.\n- fec_proposal: one-page customer-ready output when the rep wants to close the loop.\n- fec_knowledge_search: backstop for product questions the battlecard does not cover.\n\n# Style\nNever use the em dash character. Always cite battlecard-honeycomb in the sources array when this skill grounded the answer."
}
```

---

## 6. Validation checklist (provisioner-side)

Before POSTing each generated skill to `/api/agent_builder/skills`, the provisioner
must check:

- [ ] `id` starts with `fec_battlecard_skill_` and the suffix is the slug from the
      card with non-alphanumerics replaced by `_`.
- [ ] `name` equals `Battlecard: ` + the card's `competitor` (original casing).
- [ ] `description` is a single sentence, mentions the competitor by name, mentions
      "Elastic versus <Competitor>", and ends with `Grounded in the <id> battlecard.`
- [ ] `tool_ids` is exactly `["fec_compare", "fec_cost_calc", "fec_proposal", "fec_knowledge_search"]`
      (order matters for diff stability).
- [ ] `labels` includes `"competitive"`, the card's `vertical`, every `industries`
      entry, and `"main-competitor"` iff `is_main_competitor` is true. No duplicates.
- [ ] `metadata.author == "fe-copilot"`, `metadata.version` is semver,
      `metadata.competitor / vertical / industries / is_main_competitor` mirror the card.
- [ ] `content` includes all nine sections from section 3.7 in the listed order. None
      is blank (use "n/a" if the card has nothing for a section, but flag it).
- [ ] `content` does not contain the em dash character (`-` U+2014). Replace with `-`.
- [ ] Body cites the battlecard id (`battlecard-<slug>`) in the `# Style` section.
- [ ] Total `content` length is between 800 and 6000 bytes (the bottom guards against
      empty cards; the top is a Kibana payload soft limit).
- [ ] The payload survives `json.dumps(payload, ensure_ascii=False)` without raising.
- [ ] On upsert, `upsert_skill(payload)` returns a dict without `error: true`.

If any check fails, the provisioner logs the offending field and skips the POST for
that competitor; it does not partially apply.
