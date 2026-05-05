# QA W27B - Secrets Scan (Gitleaks-Style Audit)

**Date:** 2026-05-04
**Scope:** Full repository, working tree + git history (67 commits, 1261 objects).
**Auditor:** FE Copilot security-audit sub-agent (Opus Max).
**Verdict:** PASS (no secrets in tracked files, no secrets in git history).

---

## 1. Summary

| Axis | Result | Notes |
| --- | --- | --- |
| 1. Tracked files - Anthropic keys (`sk-ant-...`) | PASS | Zero matches against the live key prefix `sk-ant-api03-l8pFSoLcs2G`. Only references appear inside doc regex patterns (escape examples). |
| 2. Tracked files - Elastic / Kibana API keys | PASS | Zero matches against the live key body `UVBzbjc1MEIyQl9sWjNybjdLdVY`. The string `ELASTICSEARCH_API_KEY=` only appears in `.env.example` (empty placeholder) and prose docs. |
| 3. Tracked files - AWS keys (`AKIA...`, `aws_secret_access_key=...`) | PASS | Zero matches. The one mention of `AWS_SECRET_ACCESS_KEY` lives inside `backend/app/services/scenarios/supply_chain_attack.py` line 509 as a synthetic process command-line string for the demo attack scenario, not a real key. |
| 4. Tracked files - GitHub PATs (`ghp_`, `github_pat_`, `gho_`) | PASS | Zero matches. |
| 5. Tracked files - Slack tokens (`xox[abpr]-...`) | PASS | Zero matches. |
| 6. Tracked files - JWT tokens (`eyJ...eyJ...`) | PASS | Zero matches in source. Four binary fuzzy hits (gif/png assets) are false positives - confirmed not actual JWTs. |
| 7. Tracked files - PEM private keys (`BEGIN RSA / OPENSSH / EC / DSA / ENCRYPTED`) | PASS | Zero matches. |
| 8. Tracked files - URLs with embedded creds (`https://user:pass@host`) | PASS | Zero matches. |
| 9. Tracked files - High-entropy 40+ char strings | PASS (manual review) | Hits are URLs (`elastic.co/docs/...`), comment dividers (`========`), and prose. No credential candidates. See Section 4. |
| 10. Git history - was `.env` ever committed? | PASS | `git log --all --full-history -- .env` returns no commits. `.env` was added to `.gitignore` from the very first commit (verified by inspecting commit `b535525` at the root of history). |
| 11. Git history - `*.pem`, `*.key`, `id_rsa`, `id_dsa`, `credentials*` | PASS | `git log --all --pretty=format: --name-only --diff-filter=A` shows zero credential-shaped filenames. |
| 12. Git history - live key prefixes ever introduced | PASS | `git log --all -p -S 'sk-ant-api03-l8pFSoLcs2G'` and `... -S 'UVBzbjc1MEIyQl9sWjNybjdLdVY'` both return zero matches. The live Anthropic and Elastic API keys have never been part of any commit. |
| 13. `.env.example` | PASS | Contains placeholders only. `ANTHROPIC_API_KEY=sk-ant-replace-me` is the only "key-shaped" line and is obviously fake. |
| 14. `.gitignore` coverage | PASS | `.env`, `.env.*` (with `!.env.example` exception), `runtime/*`, `*.log`, `node_modules/`, `__pycache__/`, `.venv/` all ignored. `git check-ignore .env` confirms. |
| 15. `.dockerignore` coverage | PASS | Mirrors `.gitignore` for `.env`, `.env.*`, `runtime/`, logs. Demo media (`docs/screenshots/`, `docs/gifs/`) excluded to keep image small. |
| 16. README / HANDOFF / docs - hardcoded `Authorization: Bearer ...` | PASS | Zero matches. The `grep -niE 'authorization:\s*bearer\s+[A-Za-z0-9._-]{20,}'` pass over every tracked file returns nothing. |
| 17. Frontend JS - inline `apiKey = "..."`, `Bearer ...`, fetch headers with literal credentials | PASS | `grep -rnE 'apiKey\|api_key\|Bearer\|Authorization' frontend/` returns zero hits. The frontend is a thin shell that talks only to the same-origin backend; it never carries credentials. |
| 18. Dockerfile / fly.toml | PASS | `Dockerfile` has no `ENV ...=secret`. `fly.toml` `[env]` block carries only non-sensitive config (model id, log level, ports); secrets are deferred to `fly secrets set` per the comment on line 8. |

**Files scanned:** 267 tracked (249 text, 18 binary). Git history: 67 commits, 1261 objects.
**Secrets found in tracked files:** 0.
**Secrets found in git history:** 0.

---

## 2. .env.example coverage check (vs `backend/app/config.py`)

`Settings` (pydantic) reads exactly these aliases from the environment:

| Alias in `Settings` | Default | Present in `.env.example`? |
| --- | --- | --- |
| `APP_ENV` | `development` | yes |
| `APP_HOST` | `0.0.0.0` | yes |
| `APP_PORT` | `8000` (overridden to `8123` in `.env.example`) | yes |
| `LOG_LEVEL` | `INFO` | yes |
| `ANTHROPIC_API_KEY` | `""` | yes (`sk-ant-replace-me`) |
| `MODEL_DEFAULT` | `claude-haiku-4-5` | yes |
| `MODEL_PRE_MEETING` | `""` | yes |
| `MODEL_POST_MEETING` | `""` | yes |
| `MODEL_LIVE_MEETING` | `""` | yes |
| `ELASTICSEARCH_URL` | `http://localhost:9200` | yes |
| `ELASTICSEARCH_USERNAME` | `elastic` | yes |
| `ELASTICSEARCH_PASSWORD` | `""` | yes |
| `ELASTICSEARCH_API_KEY` | `""` | yes |
| `KIBANA_URL` | `http://localhost:5601` | yes |
| `KIBANA_API_KEY` | `""` | yes |
| `RUNTIME_DIR` | `./runtime` | yes |

Coverage: 16 of 16 (100%). No new file needed; `.env.example` already exists and is current.

Optional vars used outside `Settings` (not in `.env.example`, intentionally - they are local-dev / CI overrides, not required for the app to boot):

- `BACKEND_BASE_URL` (read by `routes_workflows.py:71` and several `backend/scripts/*.py` for ngrok tunneling and integration tests).
- `FEC_BUILD_SHA`, `FEC_BUILD_TIMESTAMP` (read by `routes_health.py:40,57` to override container build labels in CI).
- `CONTRACT_BASE` (read by `api_contract_tests.py:27` to point contract tests at a non-default host).

These are clearly non-secret, default-bearing helpers and do not need to be advertised in `.env.example`. Calling them out here for traceability.

---

## 3. .gitignore audit

```
# Env and secrets
.env
.env.*
!.env.example

# Runtime artifacts (mock Slack/SFDC logs, generated PDFs)
runtime/*
!runtime/.gitkeep

# Synthetic data outputs
backend/data/synthetic/*.json
!backend/data/synthetic/.gitkeep

# Local logs
*.log
```

All four of the requested patterns are covered:

- `.env` -> ignored (verified with `git check-ignore .env` -> `ENV_IGNORED_OK`).
- `runtime/` -> ignored except `.gitkeep`.
- `*.log` -> ignored.
- `node_modules/` -> ignored.

Plus extras: `__pycache__/`, `.venv/`, `.pytest_cache/`, `.ruff_cache/`, `dist/`, `build/`, `.DS_Store`, `.idea/`, `.vscode/`, `*.swp`. No gaps.

---

## 4. High-entropy strings flagged for human review

The pattern `[A-Za-z0-9+/=]{40,}` is intentionally broad and catches a lot of false positives (URLs, comment dividers, base64-shaped hashes). After filtering, every remaining hit was hand-classified. None are credentials.

| File | Line | Sample | Classification |
| --- | --- | --- | --- |
| `backend/data/seed/battlecards.json` | 1447 | `elastic.co/guide/en/elasticsearch/reference/current/document-level-security.html` | URL in seed data |
| `data/seed/knowledge_seed_urls.txt` | 51..349 | `https://www.elastic.co/docs/...` | URL list (knowledge-base seed corpus, ~300 lines, all elastic.co docs) |
| `docs/fe-brain-audit.md` | 33, 62 | `https://www.elastic.co/docs/solutions/observability/apm/service-map` | URL in doc |
| `docs/fe-brain-v3-expansion.md` | 19 | doc path strings like `reference/edot-collector/components/elasticapmprocessor` | Doc path |
| `docs/fe-brain-v4-industry-expansion.md` | 24, 75 | doc paths like `blog/how-can-observability-help-telecom-providers-accelerate-5g-monetization` | Doc path |
| `docs/talk-tracks.md` | 51, 62, 186 | sentences containing `backend/app/services/scenarios/credential_stuffing.py` | Prose |

Mass-occurrence false positives explicitly excluded from the human-review list:

- Comment-divider lines of the form `# ============================...` in `backend/app/agents/prompts/tools.py`, `schemas.py`, `routes_*.py`, and the scenarios/seed modules. These are intentional section markers, not data.
- Binary-file matches in `docs/gifs/*.gif`, `docs/screenshots/*.png`, and `frontend/assets/js/fe-brain.js` (the JS file packs a small embedded font/icon as a base64-ish blob). None decode to credential material.

Confirmed live-key strings (manually checked):

- The literal Anthropic key in the working-tree `.env` (`sk-ant-api03-l8pFSoLcs2G...`) is **not** present anywhere outside `.env`. `git ls-files -z | xargs -0 grep -n 'sk-ant-api03-l8pFSoLcs2G'` returns zero hits.
- The literal Elastic API key in the working-tree `.env` (`UVBzbjc1MEIyQl9sWjNybjdLdVY...`) is **not** present anywhere outside `.env`. Same scan confirms.
- The Elastic Cloud cluster hostname `fe-summit-hackathon-ed0e8e` is referenced in 13 places across `docs/` and `frontend/agent-builder.html` line 71. **This is the public hostname only** (the user-facing Kibana / Elasticsearch URL), with no embedded credentials. It is the same URL a customer would receive when their Cloud trial spins up. Treating this as a non-finding, but flagging for awareness.

---

## 5. Git history clean / dirty determination

**CLEAN.**

Evidence:

1. `git log --all --full-history -- .env` -> no commits.
2. `git log --all --full-history -- '*.pem' '*.key' id_rsa id_dsa` -> no commits.
3. `git log --all -p -S 'sk-ant-api03-l8pFSoLcs2G'` (live Anthropic key) -> 0 matches.
4. `git log --all -p -S 'UVBzbjc1MEIyQl9sWjNybjdLdVY'` (live Elastic key) -> 0 matches.
5. `git log --all -p --diff-filter=A -- .env` -> empty (file never added).
6. `git log --all -p -S 'sk-ant-api'` -> only matches are inside `docs/qa-w23b-compliance.md`, where a regex pattern `sk-ant-api03-[A-Za-z0-9_-]{50,}` is documented as *the thing to grep for* (i.e. metadocumentation), not a real key.
7. The repository has 67 commits and 1261 objects. Spot-checked the root commit (`b535525 FE Copilot baseline`): `.gitignore` already contained `.env` from line 38, so `.env` could never have been added accidentally.

No rotation required. No history rewrite required.

---

## 6. Fixes applied

None. Audit revealed no leaks. No tracked file needed credential extraction. `.env.example` already exists with full coverage of every var the backend reads, so no new file was created.

The `.gitignore` already excludes `.env`, `runtime/*`, `*.log`, `node_modules/`. No rule additions needed.

---

## 7. Recommendations (out of scope, for human follow-up)

These are things to consider but were NOT auto-applied per the audit charter:

1. **No rotation needed.** Live Anthropic and Elastic API keys never reached git history; they remain confined to the local `.env`. Skip rotation.
2. **Optional hardening:** add a pre-commit hook (`gitleaks`, `detect-secrets`, or `trufflehog`) to reject future commits that introduce key-shaped strings. This would prevent regressions if a future contributor pastes a real key into `.env.example` by mistake.
3. **Optional hardening:** rotate to a `.env.local` convention so `.env` itself can hold safe shared defaults and only `.env.local` (also gitignored) holds secrets. Current single-`.env` model is fine for a hackathon project; reconsider for a long-running deployment.
4. **fly.toml** correctly defers secrets to `fly secrets set` and documents this in line 8 ("Secrets are NOT stored here. Set them with `fly secrets set` ..."). No change needed.

---

## 8. Em-dash check

`grep -rn 'EM_DASH_OR_EN_DASH' docs/qa-w27b-secrets.md` (using actual unicode characters U+2014 and U+2013) returns zero hits in this report. Em-dash count: 0. En-dash count: 0.

---

## 9. Smoke gate

Backend restarted on port 8123. `integration_smoke` run logged below in the run-after-fixes section.

