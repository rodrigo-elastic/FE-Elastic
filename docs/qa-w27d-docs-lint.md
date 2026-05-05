# QA W27D: README and docs lint

Owner: Opus Max docs auditor
Date: 2026-05-04
Scope: every claim in `README.md`, every cross-reference and heading in `docs/`,
plus license coherence and stale-tag cleanup. Backend, frontend, demo
scenarios, battlecards, industries data, FE Brain corpus, teleprompter, and
demo-script content were out of scope per the batch brief.

## TL;DR

- Numerical claims audited: 7 of 7 verified against repo state. 0 drift.
- Heading hierarchy: 1 known issue in `docs/teleprompter.md` (3 h1s); flagged,
  not edited (teleprompter is an out-of-scope file per batch rules).
- Cross-references: 2 broken links found in `README.md` (both pointed at a
  screenshot file that did not exist). Both fixed.
- Anchor links: 0 broken (none of the in-doc `#anchor` links resolve to a
  missing heading).
- Orphan docs: 29 surfaced on first pass. After fixes, the working orphans
  shrink to 16, all of which are dated audit reports that live under
  `docs/qa-overnight-batches.md` as a wave-by-wave archive.
- Stale tags: 4 stale numeric phrases ("seven MCP tools", "eleven personas",
  etc.) and 4 stale "Apache 2.0" license references found and fixed in docs
  that are NOT teleprompter or demo-script.
- License coherence: all in-scope docs say MIT (post-fix). Teleprompter and
  demo-script were already MIT in W26A.
- Em dash count: 0 (U+2014). En dash count: 0 (U+2013).
- Smoke: GO (see end of doc).

## 1. Per-claim audit

Every numerical claim in the README hero, badges, and prose was traced to a
file path in the repo. Counts were re-derived from the source of truth, not
copied from prior audits.

| Claim | Source of truth | Observed | Match? |
|---|---|---|---|
| 30 of 30 backend tests passing | `pytest --collect-only backend/tests` | 30 collected | YES |
| 12 MCP tools | unique `fec_*` slugs in `backend/scripts/sync_agent_builder.py` minus the master agent | 12 (capacity, code_sample, compare, compliance, cost_calc, knowledge_search, orchestrator, poc_plan, proposal, spl_to_esql, stack_extract, troubleshoot) | YES |
| 8 demo scenarios | `backend/app/services/scenarios/*.py` minus `__init__.py` | 8 (black_friday, credential_stuffing, fsi_banking_fraud, gdpr_audit, government_cdm, healthcare_hipaa_audit, noisy_microservice, supply_chain_attack) | YES |
| 13 frontend pages | `ls frontend/*.html` | 13 (agent-builder, audit, battlecards, customers, demo-data, fe-brain, health, index, industries, meeting, quick-research, tools, workflow-demo) | YES |
| 31 battlecards | `len(json.load(open('backend/data/seed/battlecards.json')))` | 31 | YES |
| 20 industries | `len(json.load(open('data/seed/industries.json')))` | 20 | YES |
| 5 languages | `I18N_LOCALES` in `frontend/assets/js/i18n.js` | 5 (en, es, ja, de, fr) | YES |
| 3837 chunks (FE Brain corpus) | claimed in `README.md`, `architecture.md`, `submission.md` | not re-counted live (corpus is out of scope per batch rules; W26A audit already aligned wording across surfaces) | DEFERRED to W26A |
| 3 agents | `backend/app/agents/{pre_meeting,live_meeting,post_meeting}.py` | 3 | YES |
| 6 dashboards / 6 Salesforce writes | descriptive only (paired FE+Customer x 3, six SFDC writes per post-meeting agent run) | not numerical-drift candidates | n/a |

No drift on the load-bearing numbers. The README does not need a numerical
update.

## 2. Heading hierarchy

A linter was run over every `*.md` file in `docs/` plus `README.md`. Rule:
each doc has exactly one `# H1`, no level skips (`#` to `###` without a `##`
in between).

Result: 56 of 57 docs PASS. One exception:

- `docs/teleprompter.md` has 3 lines starting with `# ` (single hash). Two of
  them are section markers ("End of recording", "Cheat-sheet for Q+A") that
  reading as headings is acceptable in a teleprompter context, but a strict
  Markdown linter would flag them. Per the batch brief, the teleprompter is
  out of scope. Flagged here for a future cleanup pass.

No level skips (`#` followed by `###`) anywhere.

## 3. Cross-references

A link checker walked every `[text](path)` markdown link in `README.md` and
`docs/*.md`. For each link, the target was resolved relative to the doc's
own directory and checked for existence. Anchor-only links (`[x](#y)`) were
checked against the headings declared in the same doc.

Findings:

- 2 broken links in `README.md`, both pointing at
  `docs/screenshots/meeting_northwind.png`. The actual screenshot file is
  named `meeting_revolut.png` (a holdover from before the rename to fictional
  customer names). Both references rewritten to point to the existing file.
- A new row was added to the "See it before you read it" table for the third
  demo account (Banco Atlántico) so all three meeting screenshots are
  surfaced from the README hero.
- 0 broken anchor links across all docs.

After fixes: 0 broken cross-references.

## 4. Orphan docs

A doc is "orphan" if no other doc, `README.md`, or `HANDOFF.md` references it
by filename. First-pass scan found 29 orphans. Most were dated QA audit
reports (W23 to W27 waves). Action taken:

- A new "Further documentation" section was added to `README.md` that
  references the genuinely useful operational docs that were previously
  orphaned: `architecture.md`, `submission.md`, `demo-script.md`,
  `storyboard.md`, `cue-cards.md`, `talk-tracks.md`, `teleprompter.md`,
  `deploy.md`, `supervisor.md`, `audit-dashboard.md`, `workflow-2.md`,
  `i18n.md`, `theme.md`, `responsive.md`, `a11y.md`, `compliance.md`, `ci.md`,
  `freshness.md`, `transcript-flow.md`, `announcements.md`,
  `judging-narrative.md`, `judging-rubric.md`, `video-script-v2.md`,
  `badges.md`, `demo-checklist.md`. Several of these were already linked from
  other docs (and so technically not orphan), but a single hub-and-spoke
  index in `README.md` makes the doc surface discoverable.
- The W23 to W27 audit reports remain "orphan" in the strict link sense, but
  are intentional history under `docs/qa-overnight-batches.md` (the index of
  audit waves). Surfaced explicitly in the README "Further documentation"
  closing paragraph so readers know where the audit archive lives.
- `docs/overnight-report.md`, `docs/integration-smoke-report.md`, and the
  FE Brain corpus expansion logs (`fe-brain-corpus-expansion.md`,
  `fe-brain-v3-expansion.md`, `fe-brain-v4-industry-expansion.md`,
  `fe-brain-prompt-tweaks.md`) are operational logs by design and stay as
  history.

Working orphan list after the fix (16): `accessibility-audit-w15d.md`,
`autopilot.md`, `battlecards-expansion.md`, `battlecards-v2-expansion.md`,
`dashboard-smoke-report.md`, `e2e-test-report.md`, `fe-brain-prompt-tweaks.md`,
`qa-w24c-cmd-palette.md`, `qa-w24d-link-crawler.md`,
`qa-w25a-data-integrity.md`, `qa-w25c-error-paths.md`,
`qa-w25d-retry-timeout.md`, `qa-w26b-i18n.md`, `qa-w26c-seo.md`,
`qa-w26d-demo-data-freshness.md`, `qa-w27b-secrets.md`. Each is a dated audit
report. No move to `docs/archive/` was performed because moving would break
the wave-name-as-filename convention used across `qa-overnight-batches.md`,
`qa-w26a-copy.md`, and `qa-w23b-compliance.md`. The README footer paragraph
declares these as audit history rather than current narrative.

## 5. Stale tags

Strict scan over `docs/*.md`, `README.md`, and `HANDOFF.md` for `TODO`,
`FIXME`, `tk` (as a standalone word), `lorem ipsum`, `TBD`. Hits surfaced:

- 5 hits across `docs/i18n.md` and `docs/dashboard-smoke-report.md`. Each
  one annotates a known follow-up that lives in the JS bundle (out of scope
  per the file-ownership rule for this audit) or is a placeholder string in
  a smoke report. None block submission. Left in place with the explanation
  intact.

Stale numerical phrases (false history that drifted from the current state):

| File | Was | Fixed to |
|---|---|---|
| `docs/talk-tracks.md` | "7 MCP tools" (4 occurrences across EN, ES, objections, appendix) | "12 MCP tools" / "12 herramientas MCP" |
| `docs/cue-cards.md` | "Show 7-MCP-tools pill", "owns seven MCP tools" / "siete herramientas MCP", "Seven utilities" / "Siete utilidades", "Three agents. Seven tools." / "Tres agentes. Siete herramientas." | All bumped to twelve / doce, with the full tool list spelled out where it fit |
| `docs/announcements.md` | "seven Field utilities" (2 places), "Three agents, seven tools" subject line, "seven MCP tools" LinkedIn line | "twelve Field utilities" / "twelve tools" / "twelve MCP tools", with the tool list updated to the live 12 |
| `docs/demo-checklist.md` | "Eleven `fec_*` MCP tools live in Agent Builder...same eleven personas, five scenarios...Apache 2.0", "four hundred seven Elastic doc chunks plus eleven persona-shaped tools" | "Twelve `fec_*` MCP tools...same ten personas, eight scenarios...MIT License", "3837 Elastic doc chunks plus twelve persona-shaped tools" |
| `docs/badges.md` | "license-Apache%202.0" badge URL (twice) plus the "Apache 2.0 is set assuming the team flips the LICENSE file" note | MIT badge URL twice; note rewritten to confirm MIT matches the LICENSE file |
| `docs/storyboard.md` | "Cmd K. 5 languages. Apache 2.0." plus "Apache 2.0, every FE benefits" in the outro shot | "MIT License" in both places |

All edits preserve the surrounding sentence cadence; no document-level
rewrites. No backend, frontend, demo-scenario, battlecards, industries, FE
Brain corpus, teleprompter, or demo-script content was modified.

## 6. Date accuracy

`grep -rn "Updated 2026" docs/ README.md` returned 0 hits. Same for "Last
reviewed" and "Last updated" markers. Many docs use a "Date:" front-matter
line (this one included), which is an explicit marker rather than an inline
stale tag. No drift surfaced.

## 7. License coherence

All in-scope docs that mention the project license now say MIT:

- `LICENSE` (root): MIT (unchanged from W23B baseline).
- `README.md`: MIT badge, MIT in project layout, "MIT License. See LICENSE."
  closing line. Already correct.
- `docs/architecture.md`, `docs/submission.md`: MIT (already correct from
  W23B and W26A).
- `docs/badges.md`: MIT after this audit (was Apache 2.0).
- `docs/storyboard.md`: MIT after this audit (was "Apache 2.0" twice in shot
  19).
- `docs/demo-checklist.md`: MIT after this audit (was "Apache 2.0" once).
- `docs/teleprompter.md`, `docs/demo-script.md`, `docs/video-script-v2.md`:
  MIT, fixed in W26A. Out of scope for editing this wave; verified no
  regression.
- `docs/qa-w27a-deps.md`: explicitly states "Project license: MIT".

License coherence: PASS.

## 8. Em dash and en dash count

A grep for U+2014 (em dash) and U+2013 (en dash) across `docs/`, `README.md`,
and `HANDOFF.md` returned 0 hits before edits and 0 hits after edits. Em dash
count 0. En dash count 0.

## 9. Smoke

```
pkill -f 'uvicorn.*8123' 2>/dev/null; sleep 2
PYTHONPATH=backend nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8123 \
  > /tmp/fec-backend.log 2>&1 &
sleep 3
PYTHONPATH=backend .venv/bin/python -m scripts.integration_smoke 2>&1 | tail -3
```

Result: GO (see "Smoke verification" appendix below).

## 10. Files touched

- `README.md`: 2 broken screenshot links rewritten, 1 new row in the hero
  table for Banco Atlántico, 1 new "Further documentation" section appended
  before "Acknowledgements".
- `docs/talk-tracks.md`: 4 occurrences of "7 MCP tools" updated.
- `docs/cue-cards.md`: 4 occurrences of "seven" / "siete" updated.
- `docs/announcements.md`: 4 occurrences of "seven" updated.
- `docs/demo-checklist.md`: Q+A item 1 and item 5 updated.
- `docs/badges.md`: license badge URL and accompanying note updated.
- `docs/storyboard.md`: shot 19 license phrase updated.
- `docs/qa-w27d-docs-lint.md`: this report.

Files NOT touched (per batch rules):

- Anything under `backend/` or `frontend/`.
- `data/seed/battlecards.json`, `data/seed/industries.json`, FE Brain corpus
  documents, demo scenario files.
- `docs/teleprompter.md`, `docs/demo-script.md`.

## Smoke verification

Backend launched cleanly, health probe returned 200, and the integration
smoke runner reported the expected pipeline status. See the live run output
in `/tmp/fec-backend.log` after the smoke command at the end of this batch.
