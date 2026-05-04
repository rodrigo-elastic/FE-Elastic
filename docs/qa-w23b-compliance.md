# QA W23-B Compliance + Privacy Audit Report

> **Audit window**: 2026-05-04 overnight batch (Eje B).
> **Auditor**: Opus Max-effort sub-agent under hackathon governance.
> **Scope**: backend/, frontend/, data/, docs/, runtime/, README, HANDOFF, LICENSE.
> **Goal**: verify the "synthetic only" claim, audit for leaks, and ensure public-facing copy is accurate.

The audit is reproducible. Every grep used to gather evidence is listed at the bottom of this report.

## TL;DR

- Customer-name compliance: PASS after fixes. 13 hits remediated; 17 remaining hits are either exempt (legacy fixture mocks tagged "for backwards compatibility") or historical self-reference inside a prior audit report.
- PII: PASS after one fix. 1 real-looking gmail address in a mock fixture rewritten to a `.example` domain.
- Synthetic data attestation: PASS. All emails use `.example` (RFC 2606 reserved). The user's own `@elastic.co` address is the only non-reserved domain present and is acceptable scope.
- Audit log content: PASS. `runtime/audit.jsonl` carries timestamp, model, mode, token counts, and structured `audit_meta` keys only. No raw prompt text, no transcript text, no user input is logged.
- License accuracy: PASS after fix. `LICENSE` is MIT. README badge and project-layout block were claiming "Apache 2.0" in two places; both reset to MIT to match the file.
- Compliance.md: PASS. Every claim in `docs/compliance.md` is verifiable in code. PII redaction is correctly framed as "Not implemented; documented for the next phase" rather than overclaimed.
- Hardcoded keys: PASS. No `sk-ant-...`, no `ELASTICSEARCH_API_KEY=...` literal, no `KIBANA_API_KEY=...` literal in any tracked file. `.env` is gitignored and never appeared in git history.
- Klue / Salesforce / Highspot framing: PASS. Every mention uses forward-looking language ("planned MCP tool", "1-day swap when greenlit", "demo-grade integration").
- Submission packet (docs/submission.md): PASS. Tone is "hackathon submission, demo-grade integration", not "production hardened" or "in customer hands". Honest scope table is intact.
- Em-dash audit: 0 hits across user-shipped surface. The remaining mentions are inside the em-dash detector itself (`.github/workflows/ci.yml`, `.github/workflows/deploy.yml`, `runtime/overnight/batches/0100_audit.sh`) where the character is a regex literal.

Smoke status: re-run after edits per the playbook in this doc.

## Scope and method

The audit walked five concerns:

1. Customer-name compliance against the FORBIDDEN list: Revolut, Santander, Mercadolibre, KPMG, Accenture, Deloitte, Capgemini, Zara, Ray-Ban, Globex, Acme. Acceptable contexts per the W23-B charter: legacy fixture comments tagged "for backwards compatibility" and screenshot files under `docs/screenshots/` (filename mention only).
2. PII: real-looking emails (`@gmail.com`, `@outlook.com`, etc.), phone numbers, and LinkedIn / Twitter handles other than the user's own (`rodrigocareaga` / `rodrigo-elastic`).
3. Synthetic-data attestation: every fixture under `backend/data/synthetic/*.json`, plus the demo banner copy on `frontend/index.html`.
4. Audit log content: verify `runtime/audit.jsonl` never logs raw user input.
5. Hardcoded credentials: scan tracked files for Anthropic API keys, Elasticsearch keys, Kibana keys.

Every step writes a fix or a Pass entry into the lists below.

---

## Pass list

### Customer-name compliance (post-fix)

- `backend/data/synthetic/companies.json`, `meetings.json`, `transcripts.json`, `tickets.json`, `news.json`, `calendar.json`: 0 forbidden hits. All tenants are Northwind Pay, Mercado Atlas, Banco Atlántico.
- `frontend/index.html` line 86 (demo banner): "Demo data only. All companies, employees, and financials shown are fictional. Public list pricing for Splunk and Datadog is real." Banner copy is accurate.
- `frontend/index.html` line 275 (footer): "Synthetic data, Append-only audit, Per-agent model override, See compliance.md." Verbatim short-form of the four pillars; each one is verifiable.
- `frontend/agent-builder.html`, `frontend/customers.html`, `frontend/meeting.html`, `frontend/tools.html`, etc.: 0 forbidden hits.
- `backend/app/agents/prompts/pre_meeting.py` line 338 and `backend/app/agents/prompts/post_meeting.py` line 592: explicit "for backwards compatibility with older fixtures" docstring. Acme/Globex/Initech mock blocks are exempted under that comment per the W23-B charter and never surface to demos (the Quick Research and meeting flows route to Northwind Pay, Mercado Atlas, Banco Atlántico keys).
- `backend/app/agents/prompts/tools.py`: 0 forbidden hits.
- `docs/compliance.md`, `docs/architecture.md`, `docs/demo-script.md`, `docs/storyboard.md`: 0 forbidden hits.
- `docs/qa-audit-w19.md` line 93: contains the FORBIDDEN list verbatim because it is a prior audit report claiming "0 hits". Self-reference, not a customer claim, exempted.

### PII (post-fix)

- Email-domain audit returns only `@elastic.co` (the user's own work email) and `@example` / `@bigcorp.com` (RFC 2606 reserved or fictional). 1 real-looking gmail (`j.gomez99@gmail.com`) was replaced with `j.gomez99@freemail.example`.
- Phone-number-shaped strings: 0 hits (only date strings of the form `20260503-1812`).
- LinkedIn / Twitter handles: only `https://www.linkedin.com/in/rodrigocareaga/` (the user's own, in `frontend/index.html` line 282). No other social profile.

### Synthetic-data attestation

- `backend/data/synthetic/companies.json`: 3 fictional companies (Northwind Pay, Mercado Atlas, Banco Atlántico).
- `backend/data/synthetic/calendar.json`, `meetings.json`, `tickets.json`, `transcripts.json`: all reference the three fictional companies and the user's own email.
- `frontend/index.html` line 86 banner copy is accurate.

### Audit log

- `backend/app/integrations/claude_client.py` `_audit()` writes only `ts`, `model`, `mode`, `input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, plus caller-supplied `audit_meta` (agent name, meeting_id, company_id, ad-hoc flag).
- The function never receives the `system` or `user` strings as arguments. Verified by reading lines 23 to 45, 95 to 113, 170 to 201.
- `runtime/audit.jsonl` does not contain any `prompt`, `user_input`, `transcript_text`, or `message` fields.

### License

- `LICENSE` lines 1 to 22: MIT License, Copyright 2026 Rodrigo Careaga.
- `README.md` line 10: badge corrected to MIT.
- `README.md` line 207: project-layout block corrected to "MIT".
- `README.md` line 281: `MIT License. See LICENSE.` was already correct.

### Compliance.md accuracy

- "Synthetic data only" - verified above.
- "Append-only audit log" - verified by reading `_audit` (open mode `"a"`).
- "Per-agent model override" - verified by reading `backend/app/config.py` `model_for()` and the three env vars (`MODEL_PRE_MEETING`, `MODEL_POST_MEETING`, `MODEL_LIVE_MEETING`).
- "No customer data leaves the boundary unless explicitly pasted" - matches the data-flow diagram. Quick Research only sends user-typed fields; Pre and Post agents only send the synthetic dossier or the pasted transcript.
- DORA / GDPR / HIPAA / PCI DSS framing - the file does NOT claim DORA compliance. It documents the mapping surface (compliance mapping tool) and labels the PII story as "Not implemented. Synthetic data only today; clear hook documented for the next phase." Wording is precise.

### Anthropic + Elasticsearch keys

- `git ls-files` confirms `.env` is not tracked. `git log --all --full-history -- .env` returns empty: never committed.
- `grep -rIn -E "sk-ant-api03-[A-Za-z0-9_-]{50,}"` returns 0 hits.
- The placeholder in `.env.example` is `sk-ant-replace-me`, which is recognized by `claude_client.PLACEHOLDER_KEYS` and triggers mock mode.

### Klue / Salesforce / Highspot framing

- `README.md` line 255: "Klue: the source of truth for competitor positioning ..." (forward-looking).
- `README.md` line 262: "would get a `klue_battlecard_lookup` MCP tool" (forward-looking).
- `docs/architecture.md` line 137 to 139: "the master agent calls `klue_battlecard_lookup`" framed as the production pattern; the demo uses `data/seed/battlecards.json`.
- `docs/submission.md` line 65: "complementary, not duplicate. ... read from the source-of-truth systems Elastic FEs already trust, rather than re-author that research here."
- Salesforce is explicitly tagged "Demo-grade integration" in the honest-scope table at `docs/submission.md` line 182.

### Submission packet

- `docs/submission.md` does not use the phrases "production hardened", "deployed at scale", or "in customer hands". It frames the project as a hackathon submission with deterministic mock fallbacks.
- The honest-scope table at line 173 to 184 calls out which integrations are real and which are demo-grade.

---

## Fail list (resolved by this audit)

### Customer-name compliance (13 fixes)

| File | Line | Before | After |
|---|---|---|---|
| `README.md` | 10 | `License: Apache 2.0` badge | `License: MIT` badge |
| `README.md` | 53 | `meeting_revolut.png` link | `meeting_northwind.png` link |
| `README.md` | 158 | `Screenshot: meeting_revolut.png (the "revolut" filename is a legacy asset; ...)` | `Screenshot: meeting_northwind.png` |
| `README.md` | 207 | `LICENSE                 Apache 2.0` | `LICENSE                 MIT` |
| `frontend/assets/js/onboarding.js` | 100 | `Ray-Ban-style demos in 15 seconds` | `Atlas Eyewear-style demos in 15 seconds` |
| `frontend/assets/js/i18n.js` | 81 (EN) | `e.g. Globex, Mercado Atlas, Banco Atlántico` | `e.g. Northwind Pay, Mercado Atlas, Banco Atlántico` |
| `frontend/assets/js/i18n.js` | 494 (ES) | `Ej. Globex, ...` | `Ej. Northwind Pay, ...` |
| `frontend/assets/js/i18n.js` | 907 (JA) | `例: Globex...` | `例: Northwind Pay...` |
| `frontend/assets/js/i18n.js` | 1320 (DE) | `z. B. Globex, ...` | `z. B. Northwind Pay, ...` |
| `frontend/assets/js/i18n.js` | 1733 (FR) | `p. ex. Globex, ...` | `p. ex. Northwind Pay, ...` |
| `tests/e2e/tests/meeting_revolut.spec.ts` | (whole file, renamed) | `revolut-mtg-prev-001`, "Revolut" | renamed to `meeting_northwind.spec.ts`, asserts `northwind-mtg-prev-001` and "Northwind" |
| `docs/e2e.md` | 14 | `meeting_revolut.spec.ts` (suite layout) | `meeting_northwind.spec.ts` |
| `backend/scripts/run_pipeline.py` | 3 | `the upcoming Acme meeting, ... a past Acme meeting` | `the upcoming Northwind Pay meeting, ... a past Northwind Pay meeting` |
| `backend/tests/test_services/test_pdf_builder.py` | 24 | `"title": "Acme x Elastic discovery"` | `"title": "Northwind Pay x Elastic discovery"` |
| `docs/judging-narrative.md` | 42 | `Acme: consolidation; Globex: regulated finance; Initech: cross-sell` | `Northwind Pay: consolidation; Banco Atlántico: regulated finance; Mercado Atlas: cross-sell` |
| `docs/transcript-flow.md` | 47 | `"company_name": "Globex"` | `"company_name": "Northwind Pay"` |
| `docs/transcript-flow.md` | 68, 69 | `transcript-globex-...`, `"company_name": "Globex"` | `transcript-northwind-...`, `"company_name": "Northwind Pay"` |
| `docs/overnight-report.md` | 167 | sample audit line `"company_name": "Ray-Ban"` | `"company_name": "Atlas Eyewear"` |
| `runtime/overnight/batches/0300_screenshots.sh` | 42 to 44 | `meeting_revolut`, `meeting_meli`, `meeting_santander` shoot calls | `meeting_northwind`, `meeting_mercado`, `meeting_atlantico` |

### PII (1 fix)

| File | Line | Before | After |
|---|---|---|---|
| `backend/app/integrations/google_calendar_mock.py` | 93 | `j.gomez99@gmail.com` | `j.gomez99@freemail.example` (RFC 2606 reserved domain noted in comment) |

---

## Documented exemptions

- `backend/app/agents/prompts/pre_meeting.py` `_MOCKS["acme-001"]`, `_MOCKS["globex-002"]`, `_MOCKS["initech-003"]`: the docstring at line 333 to 339 of the same file explicitly says "Acme/Globex/Initech keys remain for backwards compatibility with older fixtures." Per the W23-B charter, fixtures tagged "backwards compatibility" are acceptable. These keys are NOT routed to in any current demo flow; the fictional Northwind / Mercado Atlas / Banco Atlántico keys are the active demo set.
- `backend/app/agents/prompts/post_meeting.py` `_ACME_MOCK`, `_GLOBEX_MOCK`, `_INITECH_MOCK`: same pattern. Docstring at line 588 to 594 carries the same exemption.
- `docs/qa-audit-w19.md` line 93: contains the FORBIDDEN list verbatim because it is a self-referencing audit report ("0 hits in active runtime files for Revolut / Santander / Mercadolibre ..."). It is reporting on the names, not claiming any of them as customers.
- `runtime/knowledge/*.jsonl`: third-party Elastic.co blog corpus. Files like `customers-bbva.jsonl`, `blog-elastic-ai-fraud-detection-financial-services.jsonl` are real public Elastic-published content. They legitimately mention BBVA, Deloitte, Accenture, etc. as Elastic-published customer cases. This is a knowledge corpus, not "FE Copilot customer claims". `runtime/` is gitignored and does not ship publicly.
- `runtime/audit.jsonl`: append-only by design. Historical entries from before the customer-name remap (early May 2026) reference legacy IDs like `revolut-mtg-prev-001` and `mercado-libre`. Per the "append-only audit log" claim in `docs/compliance.md`, these entries must not be retroactively rewritten. They contain no PII; only structured fields (token counts, model, mode, agent name, meeting_id). `runtime/` is gitignored and does not ship publicly.
- `runtime/scratch/*`, `runtime/qa/dashboard_smoke/*`, `runtime/qa/carmen_routing_*.json`: dev scratch and QA artifacts under gitignored `runtime/`.
- `frontend/agent-builder.html` line 53: hardcoded URL `https://fe-summit-hackathon-ed0e8e.kb.us-west-1.aws.found.io`. URL only, not a credential. The actual API key lives in `.env` (gitignored).

---

## Reproducibility (commands)

```bash
# Customer-name scan (active dirs only).
grep -rIn -E "Revolut|Santander|Mercadolibre|KPMG|Accenture|Deloitte|Capgemini|\bZara\b|Ray-?Ban|Globex|\bAcme\b|Initech" \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache \
  /path/to/FE-Elastic/frontend /path/to/FE-Elastic/backend \
  /path/to/FE-Elastic/docs /path/to/FE-Elastic/data \
  /path/to/FE-Elastic/README.md /path/to/FE-Elastic/HANDOFF.md \
  | grep -v "docs/screenshots/" | grep -v "docs/gifs/"

# PII scan (emails).
grep -rhoE '[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]+' \
  --include="*.py" --include="*.json" --include="*.html" --include="*.js" \
  --include="*.ts" --include="*.md" \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache \
  /path/to/FE-Elastic | sort -u | grep -vE "\.example$|@example\.|@elastic\.co$|@127\.0\.0\.1|@localhost|\.test$"

# PII scan (phone numbers).
grep -rIohE '\+?[0-9]{1,3}[-. ]?\(?[0-9]{3}\)?[-. ]?[0-9]{3}[-. ]?[0-9]{4}' \
  --include="*.py" --include="*.json" --include="*.html" --include="*.js" \
  --include="*.ts" --include="*.md" \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  /path/to/FE-Elastic | sort -u

# Anthropic key scan.
grep -rIn -E "sk-ant-api03-[A-Za-z0-9_-]{50,}|sk-ant-api[0-9]{2}-" \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  /path/to/FE-Elastic

# .env tracked-by-git check.
git ls-files | grep -E "^\.env$|^\.env\.example$"
git log --all --full-history -- .env

# Em-dash scan (the two literal characters appear in this comment block as
# code-fenced text only; the actual scan reads the same regex from the CI files
# under .github/workflows/).
grep -rn -P '[\x{2014}\x{2013}]' \
  --include="*.py" --include="*.md" --include="*.html" --include="*.js" \
  --include="*.ts" --include="*.css" \
  --exclude-dir=.git --exclude-dir=.venv --exclude-dir=node_modules \
  --exclude-dir=.pytest_cache --exclude-dir=.ruff_cache \
  /path/to/FE-Elastic
```

---

## Counts (final)

- Forbidden-name fixes applied: 19 line-level edits across 11 files (one of them the e2e spec, which was renamed end-to-end).
- PII fixes applied: 1 (gmail to .example).
- Em-dash count in user-shipped surface: 0.
- Hardcoded credentials in tracked files: 0.
- README license claims aligned with `LICENSE`: 2 line-level edits.
- Compliance.md claims independently verified: 5 of 5.
- Submission packet overstatements: 0.

## Smoke status

Re-run after fixes per the W23-B playbook. See the smoke command in the next section.

```
pkill -f 'uvicorn.*8123' 2>/dev/null; sleep 2
cd /Users/rodrigocareaga/Downloads/FE-Elastic && PYTHONPATH=backend nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8123 > /tmp/fec-backend.log 2>&1 &
sleep 3
PYTHONPATH=backend .venv/bin/python -m scripts.integration_smoke 2>&1 | tail -3
```
