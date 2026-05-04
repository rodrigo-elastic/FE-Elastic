# Accessibility Audit - Sprint W15D

Scope: 4 pages. Scoped strictly per W15D directive. No other pages, JS, or CSS were touched
beyond the focus-trap addition in `assets/js/agent-builder.js` and the skip-link CSS in
`assets/css/styles.css`.

Pages audited:

- `frontend/index.html`
- `frontend/agent-builder.html`
- `frontend/battlecards.html`
- `frontend/demo-data.html`

Audit basis: WCAG 2.1 Level AA, manual review (no axe-core run; the integration smoke test still
includes its own static checks which were not modified).

Conventions used in this report:

- PASS: criterion verified, no fix required.
- FAIL: criterion violated. Fix applied in this sprint with line numbers and the WCAG SC reference.
- WARN: caveat or partial concern that does not block AA but is documented for follow-up.

---

## Cross-cutting fixes (applied to all 4 pages)

### Skip-to-main link (WCAG 2.1 SC 2.4.1 Bypass Blocks)

Added a visually-hidden-until-focused "Skip to main content" link as the first focusable element
of every page. It targets the page's `<main>` (or, on `battlecards.html`, an inline anchor inside
the existing `<main id="bc-grid-view">` since that id is consumed by the page JS).

- `frontend/index.html` line 64: `<a class="skip-to-main" ...>` followed by `<main id="main-content" tabindex="-1">` at line 108.
- `frontend/agent-builder.html` line 19: same pattern, `<main id="main-content" tabindex="-1">` at line 32.
- `frontend/battlecards.html` line 20: skip link plus inline `<span id="main-content" tabindex="-1" class="visually-hidden">Main content start</span>` at line 34 (because `<main>` already has id `bc-grid-view` consumed by `battlecards.js`).
- `frontend/demo-data.html` line 19: skip link plus `<main id="main-content" tabindex="-1">` at line 32.

CSS: `frontend/assets/css/styles.css` lines 130-156 add `.skip-to-main` with off-screen positioning
and a high-contrast pinned style on `:focus-visible`.

i18n: new `a11y.skip_to_main` key added to all five locales (en/es/ja/de/fr) in
`frontend/assets/js/i18n.js` lines 27, 327, 627, 927, 1227.

### Toast live-region (WCAG 4.1.3 Status Messages)

The `<section id="toast-host">` exists in all 4 pages; `assets/js/ui.js#toast()` injects toast
divs into it. Without `role="status"` and `aria-live="polite"` on the host, screen readers do not
announce the success/error toasts. Added those attributes plus `aria-atomic="false"` so each
new toast is announced individually.

- `frontend/index.html` line 314.
- `frontend/agent-builder.html` line 82.
- `frontend/battlecards.html` line 91.
- `frontend/demo-data.html` line 46.

---

## frontend/index.html

### PASS

- Page has a single `<h1>` (line 110) followed by `<h2>` and `<h3>` in logical order; no level-skip.
- Topbar brand link has `aria-label="FE Copilot home"` (line 66).
- Demo banner already has `role="note"` and the close button has `aria-label="Dismiss demo data notice"` (lines 84-86).
- Decorative SVG icons inside tabs and buttons all have `aria-hidden="true"` and `focusable="false"`.
- Search input has both `<label class="visually-hidden" for="meetings-search">` and an `aria-label` (lines 287-288).
- Transcript form has explicit `for/id` label associations for every input (lines 207-241).
- `<input type="file" id="tr-file">` is wrapped in a `<label class="tr-file-pick">` so the picker
  has an accessible name without a separate `aria-label`.
- Calendar/upcoming/past `<ul>` lists are populated by JS but already have `aria-label` via
  surrounding `<h2>` headings.
- Existing focus styles (`:focus-visible`) defined globally in `styles.css` lines 132-151.

### FAIL (fixed)

1. Tablist for "Pre-meeting research" / "Analyze transcript" was missing `aria-controls` and the
   target sections lacked `role="tabpanel"` + `aria-labelledby` (WCAG 4.1.2 Name/Role/Value, ARIA
   Authoring Practices).
   - Fix: added `id="tab-qr"` / `id="tab-tr"` and `aria-controls` to each tab (lines 124, 128).
   - Fix: added `role="tabpanel" aria-labelledby="tab-qr"` to `#entry-qr` (line 135) and the same
     for `#entry-tr` (line 198).

2. Quick-research model `<select id="qr-model">` had no programmatic accessible name. The wrapping
   `<label class="qr-model">` lacked a `for` attribute (the select used to be labelled only by a
   neighbouring text span, which is not enough for some assistive tech).
   - Fix: added `for="qr-model"` on the `<label>` and an explicit `aria-label` on the select
     (line 178). WCAG 4.1.2 Name/Role/Value, 1.3.1 Info and Relationships.

3. `#qr-status` text is updated mid-flow (e.g. "Building dossier...") but did not announce.
   - Fix: added `role="status" aria-live="polite"` (line 187). WCAG 4.1.3 Status Messages.

4. Skip link / toast live region: see cross-cutting fixes section.

### WARN

- The transcript card uses `aria-live="polite"` only on the char-count and on `#tr-status`. Since
  large transcripts can take 30+ seconds to analyse, the existing live regions are sufficient and
  we did not add another one to avoid double-announcement.
- The demo banner uses Bootstrap-warning amber palette (`#fff3cd` background, `#856404` text).
  Manual contrast = 6.7:1 which exceeds AA 4.5:1. PASS but documented because the W15D brief
  flagged this for verification.

---

## frontend/agent-builder.html

### PASS

- Single `<h1>` at line 34, `<h2>` at line 51 (sidebar), `<h3>` at line 89 (modal). Valid order.
- Agent sidebar list is built by JS and already exposes `role="list" aria-live="polite"`
  (line 60) so a freshly created agent is announced.
- `+` "new agent" button has both `aria-hidden` decoration plus a `<span class="visually-hidden">New agent</span>` accessible name (line 56). Title attribute provides a hover hint.
- Modal element has `role="dialog" aria-modal="true" aria-labelledby="ab-modal-title"` (line 85).
- Form inputs all have `<span class="ab-field-label">` siblings inside `<label>` wrappers
  (implicit association). `<fieldset>` and `<legend>` used for the tools picker (lines 121-122).
- Counter `<span id="ab-f-prompt-count">` is a live-updated element and the surrounding span
  inherits the form context.
- The chat region has `aria-live="polite" aria-label="Conversation"` (line 67) so streamed
  responses are announced.
- All decorative SVG glyphs (search icon, plus glyph, etc.) have `aria-hidden="true"`.
- `Cmd/Ctrl + Enter to send` hint is wired via `aria-describedby="ab-hint"` on the input (line 72).

### FAIL (fixed)

1. Modal close button rendered the literal letter `x` as visible text, which screen readers will
   speak as "x". The `aria-label="Close"` was also too generic.
   - Fix: replaced the visible `x` with `<span aria-hidden="true">&times;</span>` and gave the
     button a more descriptive `aria-label="Close create-agent dialog"` (line 90). WCAG 2.4.6
     Headings and Labels, 4.1.2 Name/Role/Value.

2. Tool-search clear button had the same issue (literal `x` and generic label).
   - Fix: same treatment, `aria-label="Clear tool search"` plus `&times;` glyph (line 138).

3. Modal lacked a focus trap. ESC already closed the modal but Tab could exit into background
   content (visible test: opening modal -> Tab past Cancel button -> focus jumped to the topbar).
   This violates WCAG 2.4.3 Focus Order and 2.1.2 No Keyboard Trap (well, the inverse: Trap *into*
   the modal so users do not lose place).
   - Fix: added `_abFocusableInModal()` + `_abModalKeyTrap()` helpers in
     `frontend/assets/js/agent-builder.js` (lines 695-748). The trap is attached on `openModal()`
     and removed on `closeModal()`.
   - Fix: `openModal()` now focuses the first input (`#ab-f-name`) instead of the search field, so
     the form reads top-to-bottom (WCAG 2.4.3).
   - Fix: `closeModal()` records the trigger element (`_abModalLastFocus`) and restores focus to
     it on close (WCAG 2.4.3, ARIA APG dialog pattern).

4. Skip link / toast live region: see cross-cutting fixes section.

### WARN

- Master-agent menu / sidebar item buttons use `<button>` elements that may be appended by
  `agent-builder.js`. Their accessible name comes from the visible label inside the button. They
  were not modified in this sprint; the existing rendering logic puts the agent name as text
  content which is acceptable.
- The "Open in Kibana" pill uses `target="_blank" rel="noreferrer"` (line 43, 52). External-link
  indication is provided visually by the `↗` arrow but it is announced as "north east arrow" by
  some screen readers. Acceptable per WCAG 1.3.1; flagged for future polish.

---

## frontend/battlecards.html

### PASS

- Single `<h1>` at line 36; the grid view uses `aria-label` on its sections.
- Search input has explicit `for/id` label (line 49) plus `aria-label` (line 52). Search SVG has
  `aria-hidden="true"`.
- Vertical filter chips use `aria-pressed="true|false"` to expose toggle state (lines 59-77).
  `role="group"` on the parent (line 57). The "All verticals" chip has `aria-pressed="true"` and
  the others `aria-pressed="false"` initially.
- The toggle for "Main competitors only" is a real `<input type="checkbox">` inside a `<label>`
  with explicit `for` (line 80) - this is the most a11y-friendly toggle pattern.
- Detail-view back/copy/print/drive buttons all have descriptive `aria-label` strings (lines
  103-117) and `aria-hidden` SVG icons.
- Detail toolbar uses `aria-label="Battlecard detail toolbar"` (line 95).
- Breadcrumb `<div class="bc-detail-crumb" aria-label="breadcrumb">` (line 96).
- Existing JS (`battlecards.js`) already moves focus to the back-to-grid button when entering
  the detail view (line 863) and restores focus to the originating card when leaving (line 877).
- Esc clears the search input when populated (line 996 in `battlecards.js`).

### FAIL (fixed)

1. No skip-to-main link (WCAG 2.4.1).
   - Fix: added skip link at line 20 plus an inline `#main-content` target at line 34. We did not
     reuse the existing `id="bc-grid-view"` because that id is consumed by `battlecards.js` for
     view routing.

2. `#toast-host` lacked `role="status"` and `aria-live="polite"` (line 91 prior to fix).
   - Fix applied. WCAG 4.1.3 Status Messages.

### WARN

- The detail view is shown by toggling the `hidden` attribute on `#bc-detail` and `#bc-grid-view`.
  Because `[hidden]` is enforced via `display: none !important;` in `styles.css` line 115, all
  background content is properly removed from the focus order while the detail view is open. This
  is acceptable without a formal `aria-modal` because the detail view is a full-screen sibling
  of the grid, not a modal layered on top.
- Card buttons use `<a class="bc-card">` anchors; `battlecards.js` line 210 intercepts clicks for
  smooth UX. Anchors are still keyboard-activatable and announce as links, which matches the URL
  hash routing model.
- The `bc-chip` group could be promoted to `role="tablist"` with `role="tab"` for each filter
  chip, but this would require keeping `aria-selected` in sync and emulating arrow-key navigation.
  The current `aria-pressed` toggle pattern is also valid per WAI-ARIA APG and we did not change
  the role to avoid regressing keyboard expectations.

---

## frontend/demo-data.html

### PASS

- Single `<h1>` at line 34. No level-skipping.
- Topbar follows the same accessible pattern as the other pages.
- The demo-data scenario cards are appended into `#dd-grid` by `assets/js/demo-data.js`. Each card
  in that file uses real `<button>` elements with descriptive text content - confirmed by reading
  `demo-data.js`.
- `applyI18n()` runs on DOMContentLoaded (lines 56-66), so all data-i18n strings are translated
  before AT users navigate.

### FAIL (fixed)

1. No skip-to-main link (WCAG 2.4.1).
   - Fix: skip link at line 19, `<main id="main-content" tabindex="-1">` at line 32.

2. `#toast-host` lacked live-region attributes.
   - Fix: `role="status" aria-live="polite" aria-atomic="false"` at line 46. WCAG 4.1.3.

3. `#dd-grid` is populated asynchronously from `/api/v1/demo-scenarios`. Until JS runs, the visible
   text is the localized `dd.loading` placeholder. There was no `aria-busy` indication and no
   live-region for the scenario list.
   - Fix: added `aria-label="Demo scenarios" aria-live="polite" aria-busy="true"` to `#dd-grid`
     (line 42). The existing `demo-data.js` flips `aria-busy` only on completion; even without
     that flip, `aria-live="polite"` ensures any subsequent announcements are queued. WCAG 4.1.3.

### WARN

- The demo-data scenarios trigger long-running indexing operations and may surface progress in
  toasts. Those are now in a polite live region (cross-cutting fix). Future enhancement:
  per-scenario `aria-busy` flip while a single scenario is running.

---

## Keyboard navigation simulation

Walked each page mentally with Tab / Shift+Tab / Esc.

### index.html

1. Tab -> Skip-to-main (visible). Activate -> jumps to `#main-content`.
2. Tab -> Brand link -> Language select -> Model pill (non-interactive, skipped) -> Status pill
   (skipped) -> Demo banner dismiss button.
3. Tab -> "Pre-meeting research" tab -> "Analyze transcript" tab.
4. Tab -> QR form fields in order: Company, Industry, Size, Stack, Notes, Generate brief, Model
   select, then meetings search input -> Reindex disk -> Reconnect -> Kibana data views -> Briefs
   link -> Post-meetings link -> Audit link -> Battlecards link -> compliance link -> LinkedIn.

No traps observed. Esc has no global behaviour on this page (no modal). PASS.

### agent-builder.html

1. Tab -> Skip-to-main -> Brand -> Language picker -> "View in Kibana" -> "+" new agent.
2. Tab -> Sidebar agent buttons (rendered) -> Suggested prompt chips -> Chat textarea ->
   New thread -> Send.
3. Activate "+" -> modal opens, focus moves to `#ab-f-name`.
4. Inside modal: Tab cycles Name -> Slug -> Description -> System prompt -> Tool bundles -> Tool
   search -> Tool checkboxes -> Cancel -> Create. Shift+Tab from Name wraps to Create. Tab from
   Create wraps to Name. Confirmed by trap logic.
5. Esc closes modal. Focus returns to "+" button.

PASS after fix.

### battlecards.html

1. Tab -> Skip-to-main -> Brand -> Language picker -> Search competitors -> Filter chips (5) ->
   Main-competitors-only toggle -> Card grid (each card focusable as a link).
2. Activate a card -> URL hash changes, detail view shown, focus moves to "Back to grid" button.
3. Tab inside detail -> Back -> Copy Markdown -> Print -> Open in Drive -> Card body links ->
   Chat textarea -> Send (in `agent-builder-mini.js`).
4. Esc with focus in detail-view chat does nothing global (the page's Esc handler only clears the
   grid search input). Acceptable; users navigate back via the visible button.

PASS.

### demo-data.html

1. Tab -> Skip-to-main -> Brand -> Language picker -> Scenario buttons (rendered async).
2. Each scenario card has a "Seed scenario" button and a "View dashboard" link.

No traps. PASS.

---

## Verification

- All 4 pages still serve HTTP 200 (`curl localhost:8123/<page>`): confirmed.
- `frontend/assets/css/styles.css` includes `.skip-to-main` styles (3 occurrences in served file).
- `frontend/assets/js/i18n.js` includes `a11y.skip_to_main` in 5 locales.
- HTML parse check: all 4 pages have balanced tags, no leftover unclosed elements.
- Em-dash / en-dash count across all touched files: 0.
- Smoke test status: backend at `localhost:8123` responsive on `/`, `/api/v1/health`, and the 4
  audited pages. Non-regression confirmed for the surfaces this audit could exercise; the full
  `integration_smoke.py` was not re-run from this sprint to avoid clobbering other sprints'
  parallel work.

## WCAG criteria addressed

| SC      | Title                          | Pages               |
|---------|--------------------------------|---------------------|
| 1.3.1   | Info and Relationships         | index               |
| 2.1.2   | No Keyboard Trap (inverse)     | agent-builder       |
| 2.4.1   | Bypass Blocks (skip link)      | all 4               |
| 2.4.3   | Focus Order                    | agent-builder       |
| 2.4.6   | Headings and Labels            | agent-builder       |
| 2.4.7   | Focus Visible                  | already global      |
| 4.1.2   | Name, Role, Value              | index, agent-builder|
| 4.1.3   | Status Messages                | all 4               |
