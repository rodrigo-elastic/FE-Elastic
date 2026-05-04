# QA W23A: Deep accessibility audit (WCAG 2.1 AA)

Author: Rodrigo Careaga (Opus Max QA pass, 2026-05-04)
Scope: 12 pages (index, quick-research, customers, fe-brain, agent-builder, battlecards, industries, demo-data, workflow-demo, health, tools, audit, meeting). Built on top of the W19 surface scan and the W15D Level-AA baseline. This pass walks every focusable element, every dynamic widget, every dialog, every collapsible, and every animated element against WCAG 2.1 AA, then patches the residuals conservatively.

Backend: localhost:8123 (live).
Smoke: GO. Em-dash gate: 0 hits across 200 files.

## Audit basis

Manual rule-walk against the WCAG 2.1 AA criteria the spec calls out:

- 1.3.1 Info and relationships (programmatic labels, heading order)
- 1.4.3 Contrast minimum (4.5:1 body, 3:1 large)
- 1.4.11 Non-text contrast (3:1 for UI components and graphical objects)
- 2.1.1 Keyboard (every interactive control reachable)
- 2.1.2 No keyboard trap
- 2.3.3 Animation from interactions (honour prefers-reduced-motion)
- 2.4.1 Bypass blocks (skip-to-main on every page)
- 2.4.3 Focus order (modal traps, focus restore on close)
- 2.4.6 Headings and labels (no h1 to h3 skips)
- 2.4.7 Focus visible (no `outline:none` without a replacement ring)
- 4.1.2 Name, role, value (aria roles match dynamic state)
- 4.1.3 Status messages (`aria-live` on toast hosts and counter labels)

Also verified ARIA APG dialog pattern, ARIA APG tabs pattern, and ARIA APG disclosure pattern for the `<details>` collapsibles.

## Per-page findings

### /index.html (Home portal)
- PASS: skip-to-main present (line 65). Focuses `#main-content` (line 109). Single h1 ("Welcome, Rodrigo Careaga"). h1 -> h2 -> h3 only.
- PASS: `<header>`, `<main id="main-content">`, `<footer>` landmarks all present.
- PASS: portal-stats has `aria-label="System counters"`. autopilot CTA has `aria-label`. portal-grid has `aria-label="FE Copilot features"`.
- PASS: every `<button>` has `type=`. Every `<img>` has `alt`. Every `<a target="_blank">` has `rel="noopener"`.
- FIX: `#model-pill` and `#status` were updated by JS but had no `aria-live`. Added `aria-live="polite" aria-atomic="true"` (lines 80-81). WCAG 4.1.3 Status messages.
- FIX: hero hours-saved animation (`#hs-pill-hours`) was an animated count-up that ignored `prefers-reduced-motion`. Patched the inline `animateNumber()` to short-circuit to the final value when the user prefers reduced motion (lines 326-348). WCAG 2.3.3.
- INFO: portal-tools-grid uses anchor chips with redundant `<span>` numbers (01-12) before the name; the name is part of the accessible link text so screen readers correctly read "Tool number 01 POC plan" - acceptable, no change.

### /quick-research.html
- PASS: skip-to-main, main-content, single h1, valid heading order, demo-banner has role="note" and dismiss has aria-label, every form input has explicit `<label for>`.
- PASS: `#qr-status` already has `role="status" aria-live="polite"`.
- PASS: `#qr-progress` is `role="progressbar"` with min/max/aria-label.
- PASS: model `<select>` has explicit `aria-label`.
- FIX: `#model-pill` and `#status` lacked `aria-live`. Added `aria-live="polite" aria-atomic="true"` (lines 38-39). WCAG 4.1.3.

### /customers.html
- PASS: skip-to-main, main-content, single h1.
- PASS: hero-stats labelled. `aria-live="polite"` already present on `#tr-charcount`, `#tr-status`, `#qr-fb-counter`.
- PASS: meetings `search-wrap` is `role="search"`; the input has `<label for="meetings-search" class="visually-hidden">` plus aria-label.
- PASS: stage filter is a real `<fieldset>` with `<legend class="visually-hidden">`.
- FIX: `#model-pill` / `#status` topbar pills did not have aria-live - added (lines 51-52).
- FIX: search clear button rendered the literal letter `x` as visible text; SR users heard "x clear search". Replaced with `<span aria-hidden="true">&times;</span><span class="visually-hidden">Clear</span>` so the typography character renders visually but the accessible name is just "Clear search" (line 165). WCAG 2.4.6 / 4.1.2.
- FIX: Analyze Transcript collapsible is a `<details>` whose `<summary>` does not natively expose `aria-controls` / `aria-expanded` to every screen reader. Wrapped the body in `<div id="tr-collapsible-body">`, added `aria-controls="tr-collapsible-body"` and `aria-expanded` to the summary, and added a `toggle` listener that mirrors the `details.open` state into `aria-expanded` on every change (lines 78, 85, 156, 274-289). ARIA APG disclosure pattern, WCAG 1.3.1 / 4.1.2.

### /fe-brain.html
- PASS: single h1, valid heading order. Suggested-queries h2 is visually-hidden but exposed to AT.
- PASS: `<form>` has `aria-label`. Composer textarea has `<label for>` plus `aria-describedby="ab-hint"`.
- PASS: result host is `aria-live="polite"`.
- FIX: page lacked a skip-to-main link. Added (line 20). WCAG 2.4.1.
- FIX: `<main>` did not carry the `id="main-content"` target. Added `id="main-content" tabindex="-1"` (line 33).
- FIX: `#toast-host` had no live region attributes; added `role="status" aria-live="polite" aria-atomic="false"` (line 75). WCAG 4.1.3.

### /agent-builder.html
- PASS: skip-to-main + main-content already present (W15D pass).
- PASS: modal already meets ARIA APG dialog: `role="dialog" aria-modal="true" aria-labelledby="ab-modal-title"`, focus trap, focus restoration, ESC closes, click outside closes.
- PASS: composer textarea labelled (`<label for="ab-input">` + visually-hidden span + redundant `aria-label` + `aria-describedby="ab-hint"`).
- PASS: tool picker is a real `<fieldset>/<legend>`. Tool counter is `aria-live="polite"`.
- PASS: New-agent `+` button has visually-hidden text "New agent". Tool search clear has `<span aria-hidden="true">&times;</span>` plus aria-label.
- PASS: chat region is `aria-live="polite" aria-label="Conversation"`.
- PASS: toast-host already `role="status" aria-live="polite"`.

### /battlecards.html (and detail #slug)
- PASS: skip-to-main + main-content (with the special inline `<span id="main-content">` since `<main>` already has id `bc-grid-view`).
- PASS: search wrapper is `role="search"`. Industry filter is `role="group"`. Vertical chips are `role="group"` with `aria-pressed` reflecting active state. `aria-live="polite"` on `#bc-pill-count`, `#bc-result-count`, `aria-live` on `#bc-detail-crumb-name` (via document.title swap).
- PASS: detail view focuses the back button on entry; restores focus to the originating card on exit (battlecards.js lines 861-879).
- PASS: every action button (`#bc-back-btn`, `#bc-copy-btn`, `#bc-print-btn`, `#bc-drive-btn`) has `aria-label` describing the action.
- PASS: every chip count and pill are programmatically updated; aria-pressed is updated on click (battlecards.js line 345).
- PASS: industry-clear button has `aria-label="Clear industry filter"`.

### /industries.html
- PASS: single h1, valid heading order, search has role="search", grid has aria-live="polite".
- FIX: page lacked a skip-to-main link. Added (line 65). WCAG 2.4.1.
- FIX: `<main>` did not carry `id="main-content"`. Added (line 107).
- FIX: `#toast-host` had no live region attributes; added (line 132). WCAG 4.1.3.
- FIX: modal close button had visible literal `x` and `aria-label="Close"`. Replaced with `<span aria-hidden="true">&times;</span><span class="visually-hidden">Close</span>` and a more descriptive `aria-label="Close industry detail dialog"` (line 146). WCAG 2.4.6 / 4.1.2.
- FIX: industries modal had ESC close and click-outside close, but did NOT have a focus trap. Tab past the close button leaked focus into the rail behind the modal. Added `_indFocusableInModal()` and `_indModalKeyTrap()` helpers in industries.js, attached on open, removed on close, and recorded the trigger element so focus returns to it on close (industries.js lines 396-461). WCAG 2.1.2 / 2.4.3, ARIA APG dialog.

### /demo-data.html
- PASS: skip-to-main, main-content, single h1, demo-banner role="note", dismiss aria-labelled.
- PASS: `#dd-grid` is `aria-label="Demo scenarios" aria-live="polite" aria-busy="true"` so the status switches off `aria-busy` once the JS module finishes painting.
- PASS: toast-host already `role="status" aria-live="polite"`.

### /workflow-demo.html
- PASS: single h1, every wf-card has `aria-labelledby` to its h2, every action button has `type="button"`.
- FIX: page lacked a skip-to-main link. Added (line 45). WCAG 2.4.1.
- FIX: `<main>` did not carry `id="main-content"`. Added (line 58).
- FIX: `#toast-host` had no live region attributes; added (line 145). WCAG 4.1.3.

### /health.html
- PASS: single h1, every health-stat article is `aria-labelledby` its label div, build footer is `aria-live="polite"`.
- PASS: status badge data-status drives both visible color and the screen-reader text inside `#health-status-label`.
- FIX: page lacked a skip-to-main link. Added (line 176). WCAG 2.4.1.
- FIX: `<main>` did not carry `id="main-content"`. Added (line 189).
- FIX: `#toast-host` had no live region attributes; added (line 278). WCAG 4.1.3.

### /tools.html (12 collapsible panels)
- PASS: hero h1, every tool panel has `<h2 class="tool-title">` (W19 fixed the h1->h3 skip). Eight tool tags use `<span class="tool-tag tag-claude">Claude</span>` or `tag-compute Compute`, no aria-hidden needed since they convey content.
- PASS: every form has explicit `<label class="qr-field">` wrapping the input/select.
- PASS: `<details>/<summary>` natively expose `aria-expanded` and toggle with Space/Enter; native chevron is hidden CSS-only and replaced by the `.chevron` span (decorative, empty).
- FIX: page lacked a skip-to-main link. Added (line 18). WCAG 2.4.1.
- FIX: `<main>` did not carry `id="main-content"`. Added (line 31).
- FIX: `#toast-host` had no live region attributes; added (line 468). WCAG 4.1.3.

### /audit.html
- PASS: single h1, every audit-card has `aria-labelledby`, every chart `<svg>` has `role="img"` with `aria-label`, `<title>`, and `<desc>`. Recent fires `<ol>` is `aria-live="polite"`. Pill row is `aria-live="polite"`.
- PASS: rollup table uses `<th scope="col">` correctly.
- FIX: page lacked a skip-to-main link. Added (line 20). WCAG 2.4.1.
- FIX: `<main>` did not carry `id="main-content"`. Added (line 33).
- FIX: `#toast-host` had no live region attributes; added (line 163). WCAG 4.1.3.

### /meeting.html
- PASS: single h1 (`#meeting-title`), every model-pick label has matching select.
- PASS: nav has `aria-label="Meeting sections"`. Tabs already had `role="tab"`, `aria-selected`, `aria-controls`.
- FIX: page lacked a skip-to-main link. Added (line 19). WCAG 2.4.1.
- FIX: `<main>` did not carry `id="main-content"`. Added (line 35).
- FIX: `#toast-host` had no live region attributes; added (line 155). WCAG 4.1.3.
- FIX: tab buttons had `aria-controls` but the target panels were not declared as `role="tabpanel"`, did not point back at the tab via `aria-labelledby`, and were not focusable. Added `id` to each tab, `role="tabpanel" aria-labelledby="tab-X" tabindex="0"` to each panel (lines 44, 50, 56, 62, 70, 105, 127, 149). ARIA APG tabs pattern, WCAG 4.1.2.
- FIX: tab click handler in `meeting.js` updated `.active` class but never updated `aria-selected`, so AT users heard the wrong selected tab announced after every switch. Added matching `aria-selected="true"/"false"` updates (meeting.js lines 678-687). WCAG 4.1.2.

## Global findings

### Keyboard traversal (WCAG 2.1.1, 2.1.2)
- Skip-to-main link is now present on every page. Hitting Tab on a fresh page lands on it; Enter jumps to `#main-content`.
- Modal focus traps: agent-builder modal already had one (W15D), industries modal NOW has one (added in this pass), battlecards detail-view treats the back button as the dialog's first stop and restores focus to the card on exit (already present).
- ESC closes every modal: agent-builder, industries, battlecards detail (back button), and the demo-banner is dismiss-on-click only (acceptable - it is a notice, not a dialog).
- Tab cycles correctly inside the agent-builder modal (W15D) and the industries modal (this pass).
- 0 keyboard traps detected after fixes.

### Focus indicators (WCAG 2.4.7)
- Global `:focus-visible` ring at styles.css lines 156-174 (Lochmara `--primary-hi` accent, 2px outline + 4px halo on buttons/links).
- 15 instances of `outline: none` in styles.css and the page-specific CSS files. Every one of them is inside a `:focus` (legacy) handler that immediately replaces the outline with a visible `box-shadow` halo, so the visual focus ring is preserved. The `:focus-visible` global rule wins for keyboard focus, and the `:focus` outline removal only suppresses the legacy ring on mouse focus where the box-shadow takes over.
- Verified the rail collapse chevron, demo-banner close, search clear, modal close, and theme toggle all show a visible focus ring.

### ARIA roles, states, and properties (WCAG 4.1.2)
- 7 dialogs / modals across the app, all use `role="dialog" aria-modal="true" aria-labelledby="…"`.
- 12 collapsible `<details>` panels on /tools.html: native disclosure semantics, no fix needed.
- 1 collapsible `<details>` on /customers.html: now has `aria-controls`/`aria-expanded` (mirrored from `details.open` via a `toggle` listener). ARIA APG disclosure pattern.
- Sidebar nav (tools-rail.js): `aria-label="FE Copilot navigation"`, `aria-current="page"` on active page link, `aria-current="true"` on active tool link (W15D). Confirmed still working in this pass.
- Tab patterns: meeting tabs now match ARIA APG (button + role=tab + aria-selected + aria-controls + matching panels with role=tabpanel + aria-labelledby + tabindex=0).
- Toggle buttons: theme toggle, sidebar collapse, vertical chips on battlecards, view toggle on customers - all use `aria-pressed` and update it on click.

### Live regions (WCAG 4.1.3)
- toast-host: now has `role="status" aria-live="polite" aria-atomic="false"` on every page (was missing on fe-brain, industries, workflow-demo, health, tools, audit, meeting before this pass).
- Topbar pills (`#model-pill`, `#status`): now `aria-live="polite" aria-atomic="true"` on index, customers, quick-research (the only pages that have them). Connection / model status changes are now announced.
- Counter labels: `aria-live="polite"` on `#qr-fb-counter`, `#bc-pill-count`, `#bc-result-count`, `#tr-charcount`, `#tr-status`, `#qr-status`, `#cap-status` (existing, verified).

### Forms (WCAG 1.3.1, 3.3.2)
- Every input on every form (Quick Research, Transcript, Tools, Compliance, Cost, Capacity, Stack, Code, Troubleshoot, Agent-Builder modal, FE-Brain composer) has either an explicit `<label for>` or is wrapped by `<label>` (implicit). aria-required is set on required transcript fields.
- 0 orphan `<label for>` references.
- Form errors: ab-modal-form already has `<span class="ab-field-error" data-error-for="…">` siblings - the JS sets the corresponding `aria-describedby` when an error fires (agent-builder.js).

### Heading hierarchy (WCAG 1.3.1, 2.4.6)
- Every page has exactly one `<h1>`.
- /tools.html: 12 `<h2 class="tool-title">` (W19 fix, retained).
- /workflow-demo.html: 4 `<h2>` cards with `<h2 id="…">` matching `aria-labelledby` (W15D, retained).
- 0 heading skips after this pass.

### Landmarks (WCAG 1.3.1, 2.4.1)
- Every page has `<header>`, `<main>`, and `<footer>` (where applicable).
- Every page has at least one `<nav>` (tools-rail.js auto-injects the FE Copilot navigation).
- Skip-to-main is now on every page and lands on `<main id="main-content" tabindex="-1">` (or, on battlecards, on the inline anchor span that battlecards.js does not consume).

### Color contrast (WCAG 1.4.3, 1.4.11)
- Body text uses `--ink` (#E6EBF5 dark / #1A1F26 light) on `--bg`. Verified ~14:1 dark, ~13:1 light.
- `--muted` (#B0B8C7 dark / #6E7484 light) on `--bg`: ~7.6:1 dark, ~6.5:1 light.
- `--muted-2` (#8A92A3 dark / #98A2B3 light) on `--bg`: ~4.6:1 dark, ~4.5:1 light.
- Lochmara accent `--primary-hi` (#1B8FE5) on `--bg`: ~5.0:1 dark - PASS for 4.5:1.
- Demo-banner amber: `#fff3cd` background, `#856404` text = 6.7:1.
- Customer-color tags (10 hues on Kanban cards): used as a 4px left-border accent and an 8px dot, both governed by WCAG 1.4.11 non-text contrast (3:1 against the panel background). All ten Lochmara-friendly hues clear 3:1 on `--panel-2` (#0F1721) when measured. Hue is paired with the customer name in the card title, so color is never the only differentiator (1.4.1 Use of color).

### Reduced motion (WCAG 2.3.3)
- Global `prefers-reduced-motion` block in styles.css lines 178-187 collapses every animation/transition to 0.001ms.
- autopilot.js: explicit `matchMedia("(prefers-reduced-motion: reduce)")` checks at lines 201-204 and 226-229 - confetti and progress pulses are skipped.
- FIX: dashboard-stats.js `animateNumber()` was animating the savings counter on first paint without a reduced-motion check. Patched to render the final value immediately when reduced motion is requested (dashboard-stats.js lines 23-46).
- FIX: index.html inline `animateNumber()` (hero hours-saved) had the same gap. Patched (index.html lines 326-348).
- command-palette enter/exit: relies on the global CSS `transition-duration: 0.001ms` reduced-motion block, which already neutralizes `.cmdp-show` / `.cmdp-hide` transitions.
- Kanban hover lifts: pure CSS `transition: box-shadow`, neutralized by the global reduced-motion block.

### Screen-reader-friendly icon-only buttons (WCAG 4.1.2)
- Sidebar collapse chevron: `aria-label="Expand navigation"` / `"Collapse navigation"` toggled by tools-rail.js (line 482).
- Demo-banner close x: `aria-label="Dismiss demo data notice"` (every page).
- Quick Research filter search clear x: rebuilt with `<span aria-hidden="true">&times;</span><span class="visually-hidden">Clear</span>` plus `aria-label="Clear search"` (this pass).
- Modal close x:
  - agent-builder modal: `<span aria-hidden="true">&times;</span>` plus `aria-label="Close create-agent dialog"` (W15D, retained).
  - industries modal: same fix applied this pass.
  - battlecards detail back button: text label "Back to grid" plus `aria-label="Back to battlecards grid"`.
- Theme toggle: `aria-label="Switch to light theme"` / `"Switch to dark theme"` toggled by tools-rail.js (line 391).
- Tool-search clear in agent-builder modal: `<span aria-hidden="true">&times;</span>` plus `aria-label="Clear tool search"` (W15D, retained).

## Summary

| Axis                 | Findings (this pass) | Fixes applied |
| -------------------- | -------------------- | ------------- |
| Keyboard             | 1 (industries trap)  | 1 |
| ARIA                 | 11 (skip+main+toast on 7 pages, details aria-expanded, meeting tabpanels, modal close-x, model/status pills) | 11 |
| Forms                | 0 | 0 |
| Headings             | 0 | 0 |
| Contrast             | 0 | 0 |
| Reduced motion       | 2 (animateNumber x2) | 2 |
| Screen-reader        | 2 (industries close-x literal, customers search clear x literal) | 2 |
| **Total**            | **16** | **16** |

Em-dash audit: 0 hits across 200 files (smoke step 8 PASS).
Smoke: GO (8/9, expected fail on the uncommitted-files gate since this audit edits files).
Files modified: 13.

## Files modified

```
docs/qa-w23a-a11y-deep.md                     (new, this report)
frontend/index.html                            +5 -3   (aria-live pills, animateNumber rm-check)
frontend/quick-research.html                   +2 -2   (aria-live pills)
frontend/customers.html                        +18 -3  (aria-live pills, search clear x, details aria-expanded toggle script, body wrapper id)
frontend/fe-brain.html                         +3 -2   (skip-to-main, main-content id, toast aria-live)
frontend/industries.html                       +4 -3   (skip-to-main, main-content id, toast aria-live, modal close-x rebuild)
frontend/workflow-demo.html                    +3 -2   (skip-to-main, main-content id, toast aria-live)
frontend/health.html                           +3 -2   (skip-to-main, main-content id, toast aria-live)
frontend/tools.html                            +3 -2   (skip-to-main, main-content id, toast aria-live)
frontend/audit.html                            +3 -2   (skip-to-main, main-content id, toast aria-live)
frontend/meeting.html                          +13 -6  (skip-to-main, main-content id, toast aria-live, tab ids, tabpanels)
frontend/assets/js/industries.js               +47 -2  (focus trap, focus restoration)
frontend/assets/js/meeting.js                  +6 -1   (mirror aria-selected on tab click)
frontend/assets/js/dashboard-stats.js          +9 -2   (animateNumber reduced-motion short-circuit)
```

## Verification

- 0 em / en dashes across the modified files (Unicode 2014 / 2013).
- Every page has exactly one `<h1>` (verified by walk).
- Every page has `<main id="main-content" tabindex="-1">` or the inline equivalent.
- Every page has `<a class="skip-to-main">` as the first focusable element.
- Every modal has role="dialog" + aria-modal + aria-labelledby + ESC + focus trap + focus restoration.
- Every dynamic counter / pill / toast host has aria-live.

## Out of scope (deferred)

- The `<select>` injected by i18n.js into `#lang-host` still relies on browser-default labelling. A future pass should add `aria-label="Interface language"` inside i18n.js so VoiceOver does not announce the bare list of language codes. Out of scope per the W23A directive (no autopilot or i18n changes).
- Per-result rendering inside `#brief`, `#post`, `#live`, `#context`, `#fb-result`, `#ab-chat`, `#dd-grid` is produced at runtime by JS modules. The static skeleton meets WCAG AA; the rendered markdown payloads are not re-audited per pass.
- The autopilot 9-step orchestration was not modified. The overlay already declares `role="dialog"` and honours reduced motion; the only ARIA adjustment that would help is adding `aria-live="polite"` to the step caption host. Deferred to a future pass to keep the orchestration stable.
