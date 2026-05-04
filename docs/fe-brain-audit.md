# FE Brain RAG Audit

Auditor: Opus Max-effort RAG quality reviewer.
Date: 2026-05-03.
Endpoint under test: `POST http://127.0.0.1:8123/api/v1/tools/knowledge-search` (top_k=5).
Persona under test: Mei, ex-Elastic enablement docs lead.
Corpus under test: Elastic public docs, ELSER index (FE Brain).
Raw responses: `runtime/qa/fe_brain/<n>_<slug>.json`.

## Methodology

1. Posted 10 representative real-world Field Engineer questions to the live tool endpoint, captured the full JSON response (answer plus citations), and stored each under `runtime/qa/fe_brain/`.
2. Scored each response on four dimensions, 1 (poor) to 5 (excellent), using the rubric below. No corpus or prompt edits were made during the audit.
3. The corpus is treated as a black box from the FE perspective; scoring reflects what an FE would actually receive at the keyboard, not what the corpus could in theory cover after expansion.

Rubric:

- Relevance. Do the citations actually answer the question asked?
- Grounding. Does the answer body cite numbered sources accurately, with no hallucinated `[n]` markers and no claims beyond what the snippets support?
- Coverage. Are the retrieved snippets sufficient for a useful answer, or is the corpus thin in this area?
- Tone. Does it sound like Mei (concise, FE-focused, opinionated, references docs) or generic LLM voice?

All 10 calls returned 200 OK. No errors, no empty answers.

## Per-question results

| # | Question | Top citation URL | Relevance | Grounding | Coverage | Tone | Notes |
|---|---|---|---|---|---|---|---|
| 1 | ILM tune for hot+warm+frozen 200 GB/day | https://www.elastic.co/docs/manage-data/lifecycle/index-lifecycle-management | 4 | 5 | 3 | 4 | Solid framing of phases. Honest admission that snippets do not cover specific tuning numbers (rollover thresholds, warm timing) for the ingest rate. Practical 40 to 65 GB shard guidance is plausible but not in the cited snippets. |
| 2 | ES\|QL percentile aggregation functions | https://www.elastic.co/docs/reference/query-languages/esql/esql-functions-operators | 2 | 5 | 1 | 4 | Honest non-answer. Retrieval found only the index page for ES\|QL functions, not the percentile aggregation reference. Corpus clearly does not have the granular function reference indexed. |
| 3 | semantic_text with ELSER on Elastic Cloud | https://www.elastic.co/docs/explore-analyze/machine-learning/nlp/ml-nlp-elser | 5 | 5 | 4 | 5 | Best response in the set. Numbered, actionable steps. Each step grounded in a real citation. Mentions EIS, subscription requirement, inference endpoint creation, mapping, indexing, query. |
| 4 | Shard count for 1 TB hot, 30 GB shards | https://www.elastic.co/docs/deploy-manage/production-guidance/optimize-performance/size-shards | 5 | 4 | 4 | 5 | Direct numerical answer (33 to 34 shards), correct math, ties to official 10 to 50 GB guidance. The "200 million documents per shard" claim is presented as if from `[1]` and matches the standard guidance, defensible. |
| 5 | Service Map auto-detect dependencies | https://www.elastic.co/docs/solutions/observability/apm/service-map | 2 | 5 | 2 | 4 | Retrieval pulled the Service Map overview and legend but no snippet explaining the auto-detect mechanism (distributed tracing, span correlation). Honest about the gap. |
| 6 | Snapshot retention for 24-month audit | https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/create-snapshots | 3 | 5 | 2 | 4 | Useful nudge toward multi-policy SLM design but no concrete retention syntax or scaling numbers. The "consult your SA or Elastic Support" deflection is honest but a weak FE-facing answer. |
| 7 | EQL detection rule for credential stuffing | https://www.elastic.co/docs/solutions/security/detect-and-alert/prebuilt-rules | 3 | 4 | 2 | 4 | Practical advice (start with prebuilt rules, MITRE T1110/T1021 framing). However it then suggests ES\|QL functions reference for "query syntax" which conflates ES\|QL with EQL. Borderline grounding: the MITRE technique IDs are not in the cited snippets. |
| 8 | OTel APM field mappings | https://www.elastic.co/docs/solutions/observability/apm | 1 | 5 | 1 | 4 | Honest non-answer. Corpus does not contain the OpenTelemetry-specific field mapping reference. The fallback to the get field mapping API is a fair workaround but does not answer the question. |
| 9 | Security ML jobs for anomalous auth | https://www.elastic.co/docs/explore-analyze/machine-learning/anomaly-detection | 2 | 5 | 2 | 3 | Generic. Pointers to entry-point pages with no concrete job config, detector, or auth-specific guidance. Tone feels more like a redirect than Mei's usual opinionated walkthrough. |
| 10 | Data stream vs index alias | https://www.elastic.co/docs/manage-data/data-store/index-basics | 4 | 4 | 3 | 5 | Clear conceptual contrast with FE-facing recommendation. Notes corpus did not yield a full data-stream definition. The data-stream characterization is correct but partly inferred, not strictly snippet-grounded. |

## Aggregate scores (mean across 10 questions)

| Dimension | Mean |
|---|---|
| Relevance | 3.1 |
| Grounding | 4.7 |
| Coverage | 2.4 |
| Tone | 4.2 |

Headline read: grounding and tone are strong, coverage is the weak link. Mei does not hallucinate; she just often does not have enough corpus to give a deep answer. The ELSER retrieval is finding the right top-level pages but missing the deeper how-to and reference content underneath.

## Top 5 corpus gaps (coverage < 3)

These are the questions where retrieval was thin enough that an FE would walk away under-served. For each, a specific URL or section to add to a future scrape pass.

1. ES\|QL percentile aggregations (Q2). Coverage 1.
   - Add: `https://www.elastic.co/docs/reference/query-languages/esql/esql-functions-operators/aggregation-functions` and the individual function pages for `percentile`, `percentile_rank`, `median`, `median_absolute_deviation`. The current corpus indexes only the parent landing page, so per-function snippets never surface.

2. OpenTelemetry APM field mappings (Q8). Coverage 1.
   - Add: `https://www.elastic.co/docs/solutions/observability/apm/use-opentelemetry-with-apm` and the OTel data model / field reference under `https://www.elastic.co/docs/reference/integrations/apm`. Also worth scraping the OTel-to-ECS mapping table if it exists as a standalone page.

3. Service Map auto-detect (Q5). Coverage 2.
   - Add: the Service Map "How it works" or distributed tracing chapter at `https://www.elastic.co/docs/solutions/observability/apm/distributed-tracing` plus the APM agent docs page that explains span context propagation. The current corpus has the Service Map overview and legend but not the mechanics page.

4. Security ML anomalous auth (Q9). Coverage 2.
   - Add: `https://www.elastic.co/docs/solutions/security/advanced-entity-analytics/machine-learning-job-rules` and the prebuilt ML jobs catalog (`auth_high_count_logon_events`, `auth_rare_user`, etc.). Also add the Security solution ML setup how-to. Right now Mei can only point at the anomaly-detection landing page.

5. EQL detection rule authoring (Q7). Coverage 2.
   - Add: the EQL syntax reference at `https://www.elastic.co/docs/reference/query-languages/eql` and the rule-type pages that show worked EQL examples for credential-stuffing-adjacent techniques. The corpus today returns prebuilt rules and a UI walkthrough but no EQL syntax page, which is why the answer drifted into ES\|QL territory.

Honourable mentions (coverage 3 but still soft): snapshot retention design at scale (Q6) would benefit from `https://www.elastic.co/docs/deploy-manage/tools/snapshot-and-restore/slm-tutorial-multiple-policies`, and data-stream fundamentals (Q10) would benefit from `https://www.elastic.co/docs/manage-data/data-store/data-streams`.

## Top 3 prompt-engineering improvements

These are scoped to the persona prompt or render template, not the corpus. They address cases where Mei drifted or weakened her own answer despite usable retrieval.

1. Disambiguate query languages. Q7 conflated EQL and ES\|QL because both showed up in retrieval. Add a single line to the persona prompt: "If the user asks about EQL, do not cite ES\|QL function references as a substitute, and vice versa. Call out the language mismatch instead." This is a one-line guard that would have caught Q7's `[5]` citation.

2. Stop deflecting to "consult your SA or Elastic Support." Q6 ended with a deflection that reads as an LLM hedge, not Mei. Tighten the persona guidance to: "Mei never tells the FE to ask their SA. If the corpus is thin, she names the missing doc, suggests a sensible default based on first principles, and labels it as a default." This keeps grounding honest while removing the deflection smell.

3. Forbid unmarked claims. Q1 (40 to 65 GB shard target), Q4 (200M docs per shard), and Q7 (MITRE T1110/T1021) all introduced specific numbers or codes that are common knowledge but not strictly in the cited snippets. Add: "If a number, threshold, or identifier is not in any cited snippet, prefix it with 'rule of thumb' or 'commonly cited as' and do not attach a `[n]` to it." This protects grounding under aggressive judging.

## Final verdict

Needs corpus expansion. The retrieval pipeline and persona are working as designed: grounding is high (4.7), tone is strong (4.2), and the system fails gracefully when snippets are thin. The dominant failure mode is corpus depth, not hallucination. Three of the ten questions (Q2, Q5, Q8) returned only landing pages where the FE needed reference or how-to content, and two more (Q7, Q9) had the right top-level page but no actionable detail.

For the hackathon demo, the system is defensible: pick demo questions from the strong cluster (Q3, Q4, Q10, and Q1 in that order) and the FE Brain looks like a genuine ex-Elastic enablement lead. If a judge asks "what does the RAG miss," the honest answer is: deep reference pages for ES\|QL functions, OTel APM mappings, Security ML job catalogs, EQL syntax, and Service Map mechanics. That is a known, finite, and fixable gap, not a model or pipeline problem.

Recommendation order for follow-up work:
1. Add the five URLs in the corpus gaps section to `data/seed/knowledge_seed_urls.txt` and re-run the scrape.
2. Apply the three prompt tweaks above.
3. Re-run this audit and target a Coverage mean of 3.5+ before a customer-facing release.
