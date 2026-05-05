# QA W26D - Demo Data Freshness Audit

Audit date: 2026-05-05 (today). Auditor: QA agent (Eje D, Overnight Batch 4).

## Scope and method

Walked every demo data surface that carries a timestamp and verified the dates
land in the right window relative to "now":

- Calendar inbox (UI Inbox + smart resolver)
- Synthetic meetings (Past + Upcoming list, Pre-Meeting + Post-Meeting agents)
- Briefs and post-meeting artifacts on disk
- Renewal signals (Renewal Defender, Kibana alerting rule input)
- Demo scenarios (Black Friday, credstuff, GDPR, supply chain, noisy
  microservice, FSI banking fraud, healthcare HIPAA, gov CDM)
- Audit log (read-only check; not modified)

Out of scope (per spec): battlecards, industries, FE Brain corpus, teleprompter,
demo-script.

## Per-source audit

### 1. Calendar inbox - PASS (no fix needed)

File: `backend/app/integrations/google_calendar_mock.py`

Already correct. `_build_events()` is lazy and every event uses
`now + timedelta(hours=N)` for both start and end. Range observed:
`now+2h` to `now+144h`, all inside the next 30 days.

`list_upcoming_events()` filters out anything with `end_dt <= now`, so past
fixtures cannot leak into the inbox.

Stale entries: 0. Fixes applied: 0.

### 2. Synthetic meetings - FIXED

Files:
- `backend/data/synthetic/meetings.json`
- `backend/data/synthetic/calendar.json`
- `backend/data/synthetic/news.json`
- `backend/data/synthetic/tickets.json`

Findings: every entry held an absolute date authored against NOW = 2026-05-02
(see `scripts/generate_synthetic_data.py`). With today at 2026-05-05 the
"upcoming" Northwind meeting dated 2026-05-03 had already drifted into the
past, breaking the Inbox + Pre-Meeting flow.

Fix: `backend/app/repositories/synthetic.py` now treats the on-disk JSON as
authored at `DATA_ANCHOR = 2026-05-02 UTC` and shifts every known time field
(`start_time`, `end_time`, `published_at`, `created_at`) by
`max(0, today - anchor)` at load time. The shift is applied through
`_shift_records()` for `news`, `meetings`, `tickets`, and `calendar`.
`companies` and `transcripts` carry no timestamps and load as-is.

After-shift sample (today 2026-05-05, shift = +3 days):
- Northwind upcoming: 2026-05-06 (tomorrow)
- Mercado Atlas upcoming: 2026-05-07 (T+2)
- Banco Atlantico upcoming: 2026-05-11 (T+6)
- Past meetings span 2026-04-20 to 2026-05-02 (3 to 15 days ago, not clumped)
- News spans 2026-04-11 to 2026-04-30 (5 to 24 days ago)
- Tickets span 2026-04-14 to 2026-05-01 (4 to 21 days ago)

Stale entries before fix: 9 meetings, 9 news, 9 tickets, 3 calendar = 30.
Fixes applied: 1 loader patch (covers all 30 records every day forever).

### 3. Briefs and post-meetings - PASS (no fix needed)

Files:
- `runtime/briefs/atlantico-mtg-001.json` - generated_at 2026-05-04 (1 day old)
- `runtime/briefs/ad-hoc-test-co-20260505-082828.json` - generated_at 2026-05-05
- `runtime/post_meeting/atlantico-mtg-prev-002.json` - generated_at 2026-05-04
- `runtime/post_meeting/transcript-northwind-bank-workflow-demo-20260504-210740.json` - 1 day old

All four are inside the "last 7 days" window. The agents
(`backend/app/agents/pre_meeting.py`, `backend/app/agents/post_meeting.py`)
already stamp `generated_at` with `datetime.now(timezone.utc).isoformat()`,
so future artifacts will always be fresh.

Stale entries: 0. Fixes applied: 0.

### 4. Renewal signals - FIXED

File: `backend/data/seed/renewal_signals.json` (data file, no timestamps in
disk) plus the seeder in `backend/app/repositories/elasticsearch_repo.py`.

Findings: `_seed_renewal_signals_if_empty()` only stamped `@timestamp` once,
on the very first ES seed. After the first run the signals froze in time, so
the "3+ signals in 14 days" Kibana rule eventually stopped firing once the
seed clock drifted past the 14-day window.

Fix: rewrote the helper so every call (gated by a 24-hour idempotency check
on the latest existing `@timestamp`) re-stamps all signals across the last
14 days using a staggered offset table `[1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 13]`
days back. Added a `detected_at` mirror field for downstream UIs that key off
that name. The 24-hour gate prevents thrash when the cron and the FastAPI
boot path both call `ensure_indices()` on the same day.

Stale entries before fix: all 11 signals after first 14 days. Fixes applied:
1 seeder patch (re-stamps every restart, capped to once per 24h).

### 5. Demo scenarios - FIXED (cron coverage)

Files: `backend/app/services/scenarios/*.py`, `runtime/cron/freshness.sh`.

Per-scenario time anchor audit:
- `black_friday.py` - `_now_anchor()` uses `datetime.now(utc)` - PASS
- `credential_stuffing.py` - `datetime.now(utc)` - PASS
- `noisy_microservice.py` - `datetime.now(utc)` - PASS
- `gdpr_audit.py` - `datetime.now(utc)` - PASS
- `supply_chain_attack.py` - `datetime.now(utc)` - PASS
- `fsi_banking_fraud.py` - `datetime.now(utc)` - PASS
- `healthcare_hipaa_audit.py` - `datetime.now(utc)` - PASS
- `government_cdm.py` - `datetime.now(utc)` - PASS

All eight scenarios anchor at wall-clock NOW, so a daily reseed lands every
synthetic event inside the Kibana time picker's "Last 24h" / "Last 7d"
windows.

Cron audit: `runtime/cron/freshness.sh` ran only 5 of the 8 scenarios. The
launchd plist runs every day at 06:00 local but skipped `fsi-banking-fraud`,
`healthcare-hipaa-audit`, and `gov-cdm-compliance`, so those three demo
indices would render blank under the default time picker.

Fix: appended the three missing scenario IDs to the `SCENARIOS` array in
`freshness.sh`. The shell script's failure isolation (`||`/`set -uo pipefail`
without `e`) keeps a single bad scenario from poisoning the rest of the run.

Stale entries before fix: 3 scenarios out of cron coverage. Fixes applied:
1 cron script patch.

### 6. Audit log - PASS (untouched per spec)

File: `runtime/audit.jsonl`. Append-only; not modified. Smoke run confirmed
new `audit.append` events land at the tail when the backend processes a
request.

## Em-dash scan

Ran `grep -nP "\x{2014}|\x{2013}"` against the three patched source files
plus this report. Zero hits.

## Summary

| Source            | Stale found | Fixes |
| ----------------- | ----------- | ----- |
| Calendar inbox    | 0           | 0     |
| Synthetic data    | 30          | 1     |
| Briefs/post-mtg   | 0           | 0     |
| Renewal signals   | 11          | 1     |
| Scenarios + cron  | 3           | 1     |
| Audit log         | n/a         | 0     |
| **Total**         | **44**      | **3** |

Em-dash count: 0. Smoke: GO.
