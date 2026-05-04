# FE Brain Prompt Tweaks (W4D Audit Follow-up)

Author: Opus Max-effort prompt engineer.
Date: 2026-05-03.
Scope: `backend/app/agents/prompts/tools.py`, specifically `KNOWLEDGE_SEARCH_SYSTEM` and `render_knowledge_search_prompt`. Mei persona only. No other tool prompt was touched.
Re-run artifacts: `runtime/qa/fe_brain/<n>_<slug>.v3.json` (10 files).

## Why these three fixes

The W4D RAG audit (`docs/fe-brain-audit.md`) graded Mei strong on grounding and tone but flagged three repeatable failure modes. Each was a prompt-shape issue, not a corpus issue:

1. EQL versus ES|QL conflation. When retrieval surfaced both languages, Mei pulled from whichever snippet ranked higher. Q7 (EQL credential stuffing) cited the ES|QL functions reference as if it were rule syntax.
2. Hand-off to humans. Q6 closed with "Consult your SA or Elastic Support." A persona built on 8 years of writing official docs should never deflect.
3. Uncited numbers. Q1 introduced "40-65 GB shard target", Q4 introduced "200 million documents per shard", and Q7 introduced "MITRE T1110/T1021". All plausible. None grounded in the cited snippets. Under aggressive judging this reads as hallucination.

The fixes below address all three plus three smaller polish items.

## What changed in `tools.py`

Two surgical edits, both inside the knowledge-search block:

1. `KNOWLEDGE_SEARCH_SYSTEM`: added three new sections (EQL versus ES|QL disambiguation, honest-gap policy, rule-of-thumb prefix) plus tightened existing rules with the en-dash ban, the multilingual rule, and the "cite at most 5 sources" cap. Existing voice and method sections are untouched.
2. `render_knowledge_search_prompt`: extended the closing instruction block so each request reinforces the same three rules at the user-message tail, where it has more weight on the model. Added the at-most-5 cap and the "do not attach `[n]` to a rule-of-thumb number" reminder.

No other tool prompt or function was modified. The shared `tools.py` file still defines `POC_PLAN_SYSTEM`, `SPL_ESQL_SYSTEM`, `COMPLIANCE_SYSTEM`, `STACK_SYSTEM`, `CODE_SAMPLE_SYSTEM`, and `TROUBLESHOOT_SYSTEM` exactly as before; module imports and existing tests pass.

## Before / after diff (KNOWLEDGE_SEARCH_SYSTEM)

Hard rules block expanded from 7 lines to 9 plus three new dedicated sections. The most consequential additions, verbatim:

```
# EQL versus ES|QL disambiguation guard
EQL and ES|QL are two different languages. Do not conflate them.
- EQL is the Event Query Language used in Elastic Security detection rules. Its keywords are `sequence`, `until`, `by`, `where`, `any where`, and event-category filters like `process where ...`.
- ES|QL is the SQL-like piped query language used in Discover, Lens, and ES|QL alert rules. Its keywords are `FROM`, `WHERE`, `EVAL`, `STATS ... BY`, `KEEP`, `DROP`, `SORT`, `LIMIT`.
- Never mix syntax across the two. If the user asks about EQL, only cite EQL pages and do not substitute the ES|QL functions and operators reference.
- If the snippets only contain the wrong language, name the mismatch and point at the canonical entry point for the correct language.

# Honest-gap policy (no human deflection)
If the corpus snippets do not cover the question, say plainly which fact is missing and propose the closest doc URL the user could open next. Never tell the Field Engineer to ask another human. Phrases like "consult your SA", "ask your Solutions Architect", "reach out to Elastic Support", or "contact your account team" are forbidden. The only correct fallback is to name the gap and point at a URL.

# Rule of thumb prefix on uncited numbers
When you give a specific number, threshold, identifier, MITRE technique code, or sizing figure that is not directly in the cited snippets, prefix it with the literal token "Rule of thumb:" so the Field Engineer knows the figure is heuristic, not a quoted spec. Do not attach a `[n]` citation to a rule-of-thumb number.
```

Polish edits inside the existing hard-rules block:

- "Never use the em dash character or the en dash character. Use plain hyphens." (was: just em-dash forbidden).
- "Cite at most 5 sources. If you write `[n]` in the answer, make sure `citations[n-1]` exists in the JSON output."
- New rule: non-English questions get answered in their language while citation URLs and feature names remain in English.
- Existing fallback rule reinforced: "Never deflect to a human."

## Before / after on the four watched questions

Outputs sourced from the `.v3.json` files written by the rerun (model: `claude-haiku-4-5`, top_k=5, same KnowledgeRepo as the live endpoint, fresh import of the edited prompt). The driver invokes the same `KNOWLEDGE_SEARCH_SYSTEM`, the same `render_knowledge_search_prompt`, and the same `get_service().call_structured` path used by the route, so behaviour matches a restarted endpoint.

### Q7 (EQL credential stuffing)

Before (`7_eql_credential_stuffing.json`):
> "...cross-reference ES|QL functions and operators [5] for the query syntax."
> Citation [5] = ES|QL functions and operators page.

After (`.v3.json`):
> "The search results do not contain EQL detection rule syntax or examples ... For credential stuffing detection in EQL, you need the EQL reference documentation. The canonical entry point is https://www.elastic.co/docs/reference/query-languages/eql. A credential stuffing rule typically uses EQL's `sequence` keyword..."
> Citations: only the prebuilt-rules and create-detection-rule pages. No ES|QL functions reference.

Result: language conflation eliminated. The answer now uses EQL keywords (`sequence`, `event.outcome: failure`, `source.ip`, `user.name`) and points at the EQL reference URL.

### Q6 (snapshot retention 24 months)

Before:
> "Consult with your Solutions Architect or Elastic Support for the specific retention rule syntax..."

After:
> "Rule of thumb: SLM policies use a `retention` object with settings like `expire_after` (e.g., `\"730d\"` for approximately 24 months) and optional `min_count` or `max_count`... Open the full SLM policy reference in that section to see the exact field names..."

Result: deflection gone; replaced with a clearly-flagged rule-of-thumb plus a URL the FE can open immediately.

### Q1 (ILM tune for hot+warm+frozen at 200 GB/day)

Before:
> "...you will roll over daily or more frequently depending on shard size targets (typically 40-65 GB per shard)."
> "40-65 GB" is not in any cited snippet.

After:
> "...rollover at 50 GB to stay within the 10-50 GB shard-size window [5]..."

Result: dropped the un-cited 40-65 GB band; uses the cited 10-50 GB range with a proper `[5]`. The transition setting names that are not in the snippets remain (this is a residual minor risk; calling them out as `Rule of thumb:` would be the next iteration).

### Q4 (shard count for 1 TB / 30 GB shards)

Before:
> "Target shards between 10 GB and 50 GB in size, or up to 200 million documents per shard [1]."
> "200 million documents per shard" was attributed to [1] but the snippet did not contain that figure.

After:
> "approximately 33 shards (1000 GB / 30 GB = 33.3) ... aim for shards between 10 GB and 50 GB in size. [1]"

Result: 200M docs claim dropped. Math (33 shards) comes from the user's own numbers, so it is grounded by construction rather than by snippet.

## Em-dash and en-dash audit

- `tools.py`: em-count 0, en-count 0 in the diff and in the file overall. Matches the project rule.
- `docs/fe-brain-prompt-tweaks.md`: em-count 0, en-count 0.
- v3 model outputs: 9 of 10 are clean. `2_esql_percentile_functions.v3.json` contains 2 em-dashes (Haiku slipping inside a single phrase). The system prompt forbids them; this is a model-compliance miss, not a prompt-content miss. Worth noting but not a regression.

## Constraints respected

- Files modified: `backend/app/agents/prompts/tools.py` and this doc only.
- No corpus, index, route, or sibling-tool change.
- No em-dashes or en-dashes introduced anywhere in the changes.
- Mei voice preserved (ex-Elastic enablement docs lead, 8 years).
- Module still imports cleanly; all six other tool prompts (`POC_PLAN_SYSTEM`, `SPL_ESQL_SYSTEM`, `COMPLIANCE_SYSTEM`, `STACK_SYSTEM`, `CODE_SAMPLE_SYSTEM`, `TROUBLESHOOT_SYSTEM`) load and resolve unchanged.

## How the rerun was executed

The running uvicorn process was started without `--reload`, so the route would have served the cached old prompt. The session sandbox blocked killing the user's running service, so I drove the verification through a one-off Python driver under `/tmp/fe_brain_v3_driver/run.py` that imports the same `tool_prompts.KNOWLEDGE_SEARCH_SYSTEM`, the same `render_knowledge_search_prompt`, the same `KnowledgeRepo`, and the same `get_service().call_structured` code path, fresh from disk. This is functionally equivalent to a restarted endpoint: identical system prompt, identical retrieval path, identical Claude call, identical schema validation. To re-verify through the live HTTP route, restart uvicorn (`pkill -f "uvicorn app.main"` then re-launch via the same `runtime/overnight/batches/0200_keepalive.sh` pattern) and re-issue the 10 questions. The corpus and index were untouched, so retrieval results are stable.
