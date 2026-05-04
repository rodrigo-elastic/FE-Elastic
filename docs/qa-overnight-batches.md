# Overnight QA batches plan

> Token-efficient way to keep work moving while you sleep. Each batch is 4 parallel Opus Max agents, each ~45 to 60 minutes.

## Status

- Batch 1 (W23 A-D): IN FLIGHT, started this evening. Reports at `docs/qa-w23a-a11y-deep.md`, `docs/qa-w23b-compliance.md`, `docs/qa-w23c-perf.md`, `docs/qa-w23d-e2e-regression.md` when complete.

## Tomorrow morning: tell me "lanza wave 24" and I run this

**Batch 2 (W24 A-D)**: cross-browser + mobile + dark mode + command palette
- W24A: Mobile responsive deep (375x667, 414x896, 768x1024 across all 12 pages, document any horizontal scroll, broken layout, missed breakpoint)
- W24B: Dark mode parity (every component, every page, contrast 4.5:1 in both themes, no hardcoded white/black)
- W24C: Command palette + keyboard shortcuts (Cmd+K opens, type to filter, Enter navigates, Esc closes, every page accessible)
- W24D: Broken link crawler depth-2 (every <a href> from /index.html to depth 2, fail on 4xx/5xx, fail on missing #anchor targets)

## After Batch 2 completes: "lanza wave 25"

**Batch 3 (W25 A-D)**: data integrity + API contracts + error paths + retry
- W25A: Data integrity (every customer rendered in Kanban has valid data; orphan IDs filtered; dedupe verified; no empty cards)
- W25B: API contract test (POST schemas validate, 422 on invalid input, 404 on missing, 200 happy path for every /api/v1/* endpoint)
- W25C: Error path UX (Anthropic credit empty -> graceful fallback; ngrok down -> graceful; ES unreachable -> banner; Kibana 502 -> retry)
- W25D: Retry + timeout policy (every fetch with explicit timeout, exponential backoff for 502/503, no infinite spinners)

## After Batch 3: "lanza wave 26"

**Batch 4 (W26 A-D)**: copy QA + i18n + SEO + social
- W26A: Copy QA EN (no typos, consistent voice, no marketing fluff, every claim verifiable)
- W26B: i18n round-trip (each non-EN locale renders without overflow, no untranslated strings, formal tone)
- W26C: SEO + social meta tags (og:title, og:description, og:image, twitter:card on every page; sitemap.xml; robots.txt)
- W26D: Demo data freshness (timestamps in scenario seeders cover the last 24h relative to NOW, not stuck on old dates)

## After Batch 4: "lanza wave 27"

**Batch 5 (W27 A-D)**: build + supply chain + secrets + docs
- W27A: Dependency audit (pip-audit, npm if any, surface CVEs with fix recommendations)
- W27B: Secrets scan (gitleaks-style: no .env values committed, no API keys hardcoded)
- W27C: Build reproducibility (clean clone -> uvicorn up in <60s, every dependency version pinned)
- W27D: README/docs lint (every claim in README has a file path; every link resolves; every heading hierarchy correct)

## How each batch is structured

For every batch I send 4 prompts in a single message so the agents fan out at the same time. Each agent:
- Has a clear scope (1 axis, 1 deliverable file)
- Files boundary explicit (no two agents touch the same file)
- Restarts the backend if it edits Python
- Runs `integration_smoke.py` at the end and reports verdict
- Em-dash audit on every touched file (must be 0)

## What you can do while you sleep

The agents will run for 45 to 60 min each. Batch 1 finishes around 1h after launch. You can read the 4 batch reports tomorrow and decide what to consolidate.

You do NOT need to babysit. Each agent fixes what it can and reports the rest. Worst case a backend restart fails because of a port collision; the next agent retries.

## When you wake up

Tell me one of:
- "lanza wave 24" -> I read this doc and dispatch the 4 agents from Batch 2.
- "lanza wave 24, salta W24A" -> I dispatch only W24B/C/D.
- "consolida batch 1 y muestrame el resumen" -> I read the 4 W23 reports and surface the regressions found, fixes applied, and remaining gaps.
- "ya basta de QA, lancemos final polish" -> I switch to a different track (README polish, video script v2 dry-run rehearsal hooks, submission packet final pass).

## Known constraints

- Sub-agents are one-shot. I cannot self-cron them. The "fire next batch every hour" needs a human to say "lanza wave N" since I do not have a recurring cron in this session.
- If you set up `at` or `cron` on your laptop yourself, you could dispatch a curl ping to a GitHub Action that triggers a re-clone + agent fan-out. That is a step beyond what is needed for the May 10 deadline; this overnight plan covers what we actually have.

## Cost

Each Opus Max sub-agent run is ~$0.50 to $2 in Anthropic costs depending on file scope. Batch of 4 is ~$2 to $8. Five batches (20 agents) is ~$10 to $40. Worth it for first-place polish.
