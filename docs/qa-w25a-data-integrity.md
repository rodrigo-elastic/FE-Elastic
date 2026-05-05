# QA W25A: Data integrity audit, Customers Kanban + records pipeline

Author: Rodrigo Careaga
Date: 2026-05-04

## Scope

The Customers page (`/customers.html`) renders records that flow through
`frontend/assets/js/quick-research-filter.js`. The pipeline:

1. Fetches `/api/v1/calendar/events`, `/api/v1/meetings`, `/api/v1/briefs` in
   parallel via `safeApiGet`.
2. Runs each item through `normalizeCalendar`, `normalizeMeeting`, or
   `normalizeBrief` to produce a unified record shape.
3. Hands the union to `sanitizeRecords`, which drops system / orphan / invalid
   rows and dedupes by id, keeping the most recent timestamp.
4. Renders Kanban (default) or List view via `renderKanban` / `renderGroups`.

This audit verifies the 8 record-level invariants below plus four stress
scenarios.

## Per-axis pass / fail (live backend on localhost:8123)

Run against today's payload (5 calendar events, 10 meetings, 3 briefs).

| # | Axis | Status | Notes |
| - | ---- | ------ | ----- |
| 1 | `customer_name` non-empty, not in {Unresolved, (unknown), n/a, N/A, test, placeholder, unknown} | PASS | `gcal-evt-005` (Unresolved, FE team weekly sync) drops via stage-1 system filter; nothing renders with a tombstone name. |
| 2 | `customer_id` resolves (not "unknown" or "unknown-\*" stem) | PASS after fix | Pre-fix: `gcal-evt-004` leaked with `customer_id: "unknown-freemail"`. Post-fix: dropped via the new `cid.toLowerCase().startsWith("unknown-")` guard. |
| 3 | `timestamp_iso` parseable, not year 1970 / 9999 | PASS | New `hasValidTimestamp` gate rejects unparseable values, year <= 1970, year >= 9999. Live data is all 2025 / 2026. |
| 4 | `stage` in {scheduled, pre, post, transcript, other} | PASS | New `VALID_STAGES` Set check inside `isSystemRecord` rejects anything else. Live data is all valid. |
| 5 | `attendees` is an array; entries are strings or objects with `email` | PASS | New `normalizeAttendees` helper coerces both shapes and drops null / non-string / non-`{email}` entries before they reach the renderer. |
| 6 | `id` unique across the full set | PASS | `sanitizeRecords` dedupes by id; identical ids collapse to the entry with the most recent timestamp. Verified with synthetic duplicates in stress tests. |
| 7 | `title` non-empty | PASS | `isSystemRecord` now rejects records whose title is empty after trim. Normalize\* fall back to a localized "(untitled)" label, so this gate primarily catches malformed payloads. |
| 8 | `href` resolves (no `/api/v1/agents/post-meeting/null`) | PASS | `normalizeMeeting` and `normalizeBrief` now refuse to construct a record at all when the underlying id / `meeting_id` is missing. The Pre / Post agent CTAs build their URL from `record._meeting.id`, which is now guaranteed to exist. |

### Live data dry run (Python parity, identical logic)

```
Pre-sanitize: 15 records  |  Post-sanitize: 13 records
Dropped: 2  Duplicates collapsed: 0

Dropped:
  [sys] cal:gcal-evt-005    "FE team weekly sync"           internal-only
  [sys] cal:gcal-evt-004    "Fjordbank Mexico (Freemail)"   customer_id=unknown-freemail

Kept (13):
  cal:gcal-evt-001  Northwind Pay   scheduled  2026-05-06
  cal:gcal-evt-002  Mercado Atlas   scheduled  2026-05-07
  cal:gcal-evt-003  Banco Atlantico scheduled  2026-05-11
  mtg:atlantico-mtg-prev-002    Banco Atlantico  post  2026-04-17
  mtg:atlantico-mtg-prev-001    Banco Atlantico  pre   2026-04-22
  mtg:mercadoatlas-mtg-prev-001 Mercado Atlas    pre   2026-04-25
  mtg:northwind-mtg-prev-001    Northwind Pay    pre   2026-04-27
  mtg:mercadoatlas-mtg-prev-002 Mercado Atlas    pre   2026-04-28
  mtg:northwind-mtg-prev-002    Northwind Pay    pre   2026-04-29
  mtg:northwind-mtg-001         Northwind Pay    scheduled 2026-05-03
  mtg:mercadoatlas-mtg-001      Mercado Atlas    scheduled 2026-05-04
  mtg:atlantico-mtg-001         Banco Atlantico  scheduled 2026-05-08
  brf:transcript-northwind-bank-workflow-demo-20260504-210740  transcript  2026-05-04
```

## Stress tests

Backend has no public write endpoint for calendar events / meetings (writes are
agent-driven), so curl-based POST stress tests are not possible. Instead, the
sanitizer was driven directly with a synthetic batch of 54 records (35 valid +
17 invalid + 2 duplicates) under a Python parity harness with byte-identical
logic to the JS sanitizer.

| Stress | Status | Notes |
| ------ | ------ | ----- |
| 50 fake records, sanitizer drops invalid | PASS | 35 valid kept, 17 invalid dropped, 2 duplicates collapsed. |
| `customer_name: ""` does NOT render | PASS | Dropped under `[sys]` reason (empty cust check). |
| Duplicate id rendered once | PASS | Two entries with id `cal:fake-good-000` collapse into the newer (2026-05-05) entry; older 2025-01-01 discarded. |
| Malformed timestamp dropped, not crashed | PASS | `"NOTADATE"`, `"1969-12-31..."`, `"9999-12-31..."` all rejected by `hasValidTimestamp`. |
| Invalid stage dropped | PASS | `stage: "meeting"` rejected by the `VALID_STAGES` guard. |
| Title="" dropped | PASS | New trim-non-empty title gate. |
| `null` and non-object records dropped | PASS | First-line `if (!record \|\| typeof record !== "object")` guard in `isSystemRecord` plus `if (!hasValidId)` in `sanitizeRecords`. |
| `customer_id: "unknown-*"` synthetic stem dropped | PASS | New `cid.toLowerCase().startsWith("unknown-")` guard. |
| Records with missing id dropped (no random fallback) | PASS | `normalizeCalendar` / `normalizeMeeting` / `normalizeBrief` now return `null` when the underlying id is missing, rather than synthesizing `Math.random()` ids that defeat dedup. |
| Records with system prefixes dropped | PASS | `orphan-demo-`, `synthetic-`, `_internal-`, `demo-data-` on either id or customer_id continue to drop. |

## Audit of `isSystemRecord` and `sanitizeRecords`

### Pre-fix coverage (lines 159 to 219 in the prior version)

`isSystemRecord` covered:

- system prefixes (`orphan-demo-`, `synthetic-`, `_internal-`, `demo-data-`) on
  either `id` (after stripping the `cal:` / `mtg:` / `brf:` prefix) or
  `customer_id`;
- the literal title regex `FE team weekly sync`;
- `customer_id === "unknown"` (exact match);
- empty `customer_name`;
- placeholder names: `unresolved`, `n/a`, `(unknown)`;
- prefix regex `^(unknown|placeholder|test)\b`.

`sanitizeRecords` deduped by id and kept the most recent timestamp.

### Edge cases missed (now fixed)

| Gap | Symptom | Fix |
| --- | ------- | --- |
| `customer_id` synthetic stems like `"unknown-freemail"` | `gcal-evt-004` leaked into the Kanban with name "Freemail" | Added `cid.toLowerCase().startsWith("unknown-")` reject. |
| Empty `customer_id` | Edge: `customer_id` set to empty string would slip the `=== "unknown"` check | Added `!cid` reject. |
| Records with `null` / non-object payloads | Would crash `normalizeCalendar` (`ev.resolution` on null) | Added `if (!ev \|\| typeof ev !== "object") return null` in all three normalize\* + matching guard at the top of `isSystemRecord`. |
| Non-string `id` | A numeric or null id slipped through dedupe (`id` falsy made it "drop silently from dedupe map" but the record stayed `kept`) | Added `hasValidId` first-gate in `sanitizeRecords`. |
| `Math.random()` id fallback in normalize\* | Defeated the dedup contract (different runs got different ids) | Removed all three random fallbacks; if the underlying id is missing, the normalize function returns `null`. |
| Bad timestamps (NaN / 1970 / 9999) | Would render as "Jan 1, 1970" or "Dec 31, 9999" cards | Added `hasValidTimestamp` gate. |
| Invalid stage | Would render as the "Other" column silently | Added `VALID_STAGES` reject inside `isSystemRecord` so it lands in the dropped log instead. |
| Empty title (post-trim) | Card with a blank top line | Added trim-non-empty title reject. |
| Attendees with non-string / non-`{email}` entries | `String(a)` later in the renderer could log "[object Object]" | Added `normalizeAttendees` helper to coerce + drop. |
| `briefMap.has` / `postMap.has` on a non-Map | TypeError if upstream feeder ever returns plain objects | Added `typeof briefMap.has === "function"` guard in `normalizeMeeting`. |

### Edge cases still consciously not enforced (out of scope)

- A record with a duplicate id but a different `customer_id` is silently
  collapsed onto the newer entry. This is the intended behaviour: ids are the
  contract; if a bug upstream ever ships duplicate ids with mismatched
  customers, dedupe will mask it. Acceptable risk for the demo surface.
- We do NOT cross-validate that `customer_id` from the calendar matches the
  `company_id` from a meeting with the same id stem. That belongs to a backend
  consistency check.

## Sample API responses (live, today)

Captured from `curl http://localhost:8123/api/v1/...` at 2026-05-04. Trimmed.

```json
// /calendar/events  -> 5 items
{ "items": [
  { "id": "gcal-evt-005", "summary": "FE team weekly sync",
    "resolution": { "company": null, "confidence": "internal" } },                  // dropped (sys)
  { "id": "gcal-evt-001", "summary": "Northwind Pay x Elastic, observability...",
    "resolution": { "company": { "id": "northwind", "name": "Northwind Pay" } } },  // kept
  { "id": "gcal-evt-002", "summary": "Mercado Atlas search relevance...",
    "resolution": { "company": { "id": "mercado-atlas", "name": "Mercado Atlas" } } }, // kept
  { "id": "gcal-evt-004", "summary": "Fjordbank Mexico, intro call (via Vega...)",
    "resolution": { "company": { "id": "unknown-freemail", "name": "Freemail" } } },// dropped (sys, post-fix)
  { "id": "gcal-evt-003", "summary": "Banco Atlantico Splunk renewal review",
    "resolution": { "company": { "id": "atlantico", "name": "Banco Atlantico" } } } // kept
]}
```

```json
// /meetings  -> 10 items
[
  { "id": "atlantico-mtg-prev-002", "company_id": "atlantico", "title": "...regulatory mapping...",
    "start_time": "2026-04-17T09:00:00+00:00", "is_upcoming": false },
  { "id": "atlantico-mtg-prev-001", "company_id": "atlantico", "title": "...exec discovery",
    "start_time": "2026-04-22T09:00:00+00:00", "is_upcoming": false },
  // ...
  { "id": "atlantico-mtg-001", "company_id": "atlantico", "title": "...Splunk renewal alternative review",
    "start_time": "2026-05-08T09:00:00+00:00", "is_upcoming": true }
]
```

```json
// /briefs  -> 3 items
{ "items": [
  { "type": "post_meeting", "meeting_id": "transcript-northwind-bank-workflow-demo-20260504-210740",
    "company_id": "transcript-northwind-bank-workflow-demo", "summary": "...",
    "generated_at": "2026-05-04T21:07:41+00:00" },
  { "type": "pre_meeting", "meeting_id": "atlantico-mtg-001", "company_name": "Banco Atlantico",
    "headline": "Banco Atlantico's Splunk renewal + 'Atlas Multi-Cloud' platform...",
    "generated_at": "2026-05-04T17:10:50+00:00" },
  { "type": "post_meeting", "meeting_id": "atlantico-mtg-prev-002", "company_id": "atlantico",
    "summary": "Banco Atlantico is running a three-way bake-off...",
    "generated_at": "2026-05-04T17:07:45+00:00" }
]}
```

## Fixes applied

All edits in `frontend/assets/js/quick-research-filter.js`:

1. **`isSystemRecord` tightening** (now lines ~221-262):
   - Added top guard for `null` / non-object records.
   - Added `!cid` reject (empty customer_id).
   - Added `cid.toLowerCase().startsWith("unknown-")` reject.
   - Promoted the placeholder name list into a frozen Set
     `PLACEHOLDER_NAMES = {"unresolved","n/a","(unknown)","unknown","placeholder","test"}`
     so an exact-match check runs in addition to the prefix regex.
   - Added `VALID_STAGES.has(record.stage)` reject.
   - Added trim-non-empty title reject.
2. **`sanitizeRecords` hardening** (now lines ~264-310):
   - Added `Array.isArray` guard (returns `[]` if records is not a list).
   - Added `hasValidId` first-gate (drops records whose id is missing or
     non-string).
   - Added `hasValidTimestamp` second-gate (drops NaN / year <= 1970 / year >= 9999).
3. **`normalizeAttendees` helper** (new, ~line 314):
   - Coerces strings or `{email: string}` objects into an email-string array.
   - Drops `null`, numbers, arrays, and other junk silently.
4. **`normalizeCalendar`** (now ~330-360):
   - Returns `null` if `ev` is not an object.
   - Returns `null` if `ev.id` is missing or non-string (no more `Math.random()` fallback).
   - Type-checks `summary`, `company.name`, `company.id`, `company.industry`.
   - Uses `normalizeAttendees` for the attendees list.
5. **`normalizeMeeting`** (now ~362-405):
   - Returns `null` if `m` is not an object or `m.id` is missing.
   - Type-checks `title`, `company_name`, `company_id`, `company_industry`.
   - Defensive `briefMap` / `postMap` shape check.
   - Uses `normalizeAttendees`.
6. **`normalizeBrief`** (now ~407-443):
   - Returns `null` if `b` is not an object, or both `meeting_id` and `id` are
     missing or non-string (so the resulting `href` can never be
     `/meeting.html?id=null`).
   - Type-checks `headline`, `summary`, `company_name`, `company_id`,
     `industry`.
7. **`fetchAll`** (now ~125-175):
   - Filters `null` returns from each normalize\* before appending.
   - `meetingIds` Set built only from string ids.
   - Skips `null` / non-object brief items defensively.

Total fixes: 7 functions / blocks tightened. Files modified: 1.

## Em-dash audit

```
$ grep -cnP "[\x{2014}\x{2013}]" frontend/assets/js/quick-research-filter.js
frontend/assets/js/quick-research-filter.js:0
$ grep -cnP "[\x{2014}\x{2013}]" docs/qa-w25a-data-integrity.md
docs/qa-w25a-data-integrity.md:0
```

Pass.

## Smoke

Re-ran after the fix:

```
PYTHONPATH=backend .venv/bin/python -m scripts.integration_smoke
```

Result captured in the run log: GO. Backend still serves /calendar/events,
/meetings, /briefs with the unchanged contract; only the FE sanitizer is
stricter.

## What is NOT touched

- Backend code (no new endpoints; no schema changes).
- Battlecards, industries, FE Brain corpus, demo scenarios, customers data.
- Teleprompter, demo-script.
- Other JS modules; only `quick-research-filter.js` was edited.

## Per-axis summary

| Axis | Status |
| ---- | ------ |
| 1 customer_name | PASS |
| 2 customer_id | PASS (after fix; pre-fix would FAIL on gcal-evt-004) |
| 3 timestamp_iso | PASS |
| 4 stage | PASS |
| 5 attendees | PASS |
| 6 id unique | PASS |
| 7 title | PASS |
| 8 href | PASS |
| Stress: 50 fake records | PASS |
| Stress: empty customer_name | PASS |
| Stress: duplicate id | PASS |
| Stress: malformed timestamp | PASS |
| Em-dash count | 0 |
| Smoke | GO |
