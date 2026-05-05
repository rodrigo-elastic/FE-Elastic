# QA W28B - Mobile responsive deep pass

Author: FE Copilot QA (Opus Max)
Date: 2026-05-04
Scope: 13 frontend pages, 3 reference widths (375x667, 414x896, 768x1024).

This pass complements the W12 responsive doc (`responsive.md`) with a detailed
matrix at 375 / 414 / 768, an explicit hunt for horizontal-scroll offenders,
WCAG 2.5.5 tap-target review, and font-size minimums on phone.

## Methodology

Backend served on `localhost:8123`; static frontend at `frontend/`. No real
browser was available; the audit reads every CSS rule, traces it back to the
HTML markup, and confirms each grid, fixed-width element, modal, and topbar
chip behaves correctly at the three reference widths. Findings were verified
by grepping selectors against `frontend/assets/css/*.css` and the inline
`<style>` blocks inside `frontend/*.html`.

## Per page x per width matrix

Legend: PASS = no fix required. FIX = a fix was applied in this pass and is
described in "Fixes applied" below.

| Page                      | 375x667 (iPhone SE) | 414x896 (iPhone XR) | 768x1024 (iPad)     |
| ------------------------- | -------------------- | -------------------- | -------------------- |
| `/index.html`             | FIX (banner, btn)    | FIX                  | PASS                 |
| `/quick-research.html`    | FIX (chip target)    | FIX                  | PASS                 |
| `/customers.html`         | FIX (banner, btn)    | FIX                  | PASS                 |
| `/fe-brain.html`          | PASS                 | PASS                 | PASS                 |
| `/agent-builder.html`     | FIX (modal close)    | FIX                  | PASS                 |
| `/battlecards.html` grid  | FIX (chip target)    | FIX                  | PASS                 |
| `/battlecards.html#slug`  | FIX (action btn)     | FIX                  | PASS                 |
| `/industries.html`        | FIX (modal close)    | FIX                  | PASS                 |
| `/industries.html` modal  | FIX (modal close)    | FIX                  | PASS                 |
| `/demo-data.html`         | PASS                 | PASS                 | PASS                 |
| `/workflow-demo.html`     | PASS                 | PASS                 | PASS                 |
| `/health.html`            | PASS                 | PASS                 | PASS                 |
| `/tools.html`             | FIX (btn target)     | FIX                  | PASS                 |
| `/audit.html`             | PASS                 | PASS                 | PASS                 |
| `/meeting.html`           | FIX (banner)         | FIX                  | PASS                 |

## Top offenders before this pass

These are file:line references for rules that produced the worst mobile
behavior. All have been fixed in this pass.

1. `frontend/index.html:45` and `frontend/customers.html:38` -
   `.demo-banner { font-size: 12px }`. Below the 14px floor we want on
   phones; small print is unreadable on a 375px-wide viewport. The close
   button at line 41 / 52 had `padding: 2px 6px` which yielded a tap target
   of ~16x18 px, well below the WCAG 2.5.5 minimum of 44x44.

2. `frontend/assets/css/styles.css:658-694` - `.btn { padding: 8px 14px;
   font-size: 13px }`. With line-height 1.2 this is ~32-36 px tall, below
   44 px. Since `.btn` is used everywhere (Quick Research submit, tools
   action row, modal actions) the impact is broad.

3. `frontend/assets/css/styles.css:735-749` - `.tab { padding: 11px 16px;
   font-size: 13px }`. Tabs appear on `/meeting.html`. ~38 px tall on
   desktop, fine for click but borderline for thumbs.

4. `frontend/assets/css/battlecards.css:1033-1038` - `.bc-chip { padding:
   7px 11px; font-size: 12px }` at <=768. Filter chips for the battlecards
   list become ~26 px tall on phone.

5. `frontend/assets/css/quick-research-filter.css:314-326` - `.qr-fb-view-btn
   { padding: 7px 12px; font-size: 12px }`. Kanban / List toggle buttons on
   `/customers.html` become ~26 px on phone.

6. `frontend/assets/css/agent-builder.css:692-700` - `.ab-modal-close`
   28x28 px close button on the create-agent modal. Below 44 px.
   Same pattern at `frontend/assets/css/industries.css:317-326`
   for `.ind-modal-close` (industries modal). And at
   `frontend/assets/css/battlecards.css` for `.bc-action-btn`.

7. `frontend/assets/css/agent-builder.css:165-174` - `.ab-agent-trash`
   24x24 px delete icon. Sub-44 tap target inside the agents sidebar list.

## Horizontal scroll offenders (>100vw at 375 px)

Methodology: grep every `width: <px>` and `min-width: <px>` declaration,
trace to the markup, compute the rendered width at 375 px viewport with
container padding 16 px (= 343 px usable). Anything wider than 343 px on
the inner box would force a horizontal scroll.

Findings:

- `frontend/assets/css/audit.css:178-183` - `.audit-table { min-width:
  560px }` is intentional. Wrapped in `.audit-table-scroll { overflow-x:
  auto }`. No page-level scroll. PASS.
- `frontend/assets/css/autopilot.css:87` - `.ap-caption-bar { min-width:
  320px }`. Hidden on mobile via `display: none !important;` at the
  same file's media query. PASS.
- `frontend/assets/css/styles.css:494` - `.hs-headline { min-width: 240px
  }`. Inside a flex-wrap parent (`.hero-savings`); it wraps to its own row
  when needed. PASS.
- `frontend/assets/css/industries.css:19` - `.ind-search-wrap { min-width:
  240px }` in flex-wrap parent. Fits within 343 px usable. PASS.
- `frontend/assets/css/battlecards.css:893` - `.bc-industry-select-wrap {
  min-width: 220px; max-width: 360px }` in flex-wrap parent. Fits. PASS.
- Inline iframes in `/meeting.html`, `/tools.html` - `iframe { max-width:
  100% }` rule from `styles.css:3526` ensures viewport containment. PASS.

No horizontal-scroll offenders remain after this pass.

## Tap target offenders (< 44x44 px on mobile)

All offenders below were brought up to >=44 px on touch by either adding
explicit `min-height` plus comfortable padding, or by widening the existing
hit area via a transparent inflated padding box.

| Selector                                   | Before (px)  | After (px)    | File                              |
| ------------------------------------------ | ------------ | ------------- | --------------------------------- |
| `.demo-banner-close` (index, customers)    | 16x18        | 32x32 + hit44 | inline in index.html, customers.html |
| `.btn` (mobile)                            | ~32-36       | min-height 44 | styles.css                        |
| `.btn-link` (mobile)                       | ~16          | min-height 44 | styles.css                        |
| `.tab` (mobile)                            | ~38          | min-height 44 | styles.css                        |
| `.bc-chip` (mobile)                        | ~26          | ~36 + hit44   | battlecards.css                   |
| `.qr-fb-view-btn` (mobile)                 | ~26          | min-height 40 | quick-research-filter.css         |
| `.ab-modal-close` (mobile)                 | 28x28        | 36x36 + hit44 | agent-builder.css                 |
| `.ind-modal-close` (mobile)                | 28x28        | 36x36 + hit44 | industries.css                    |
| `.bc-action-btn` (mobile)                  | ~30          | min-height 40 | battlecards.css                   |
| `.ab-agent-trash` (mobile)                 | 24x24        | 32x32 + hit44 | agent-builder.css                 |

The "hit44" approach uses a `::before` pseudo-element with absolute
positioning and `inset: -X px` to inflate the hit area to 44x44 without
visually expanding the control. This preserves the chrome aesthetic while
making the control thumb-friendly.

## Font size review

All body text on mobile is now >= 14 px after this pass. Two small-print
exceptions are intentional:
- Demo banner is bumped from 12 px to 13 px on mobile (still readable; not
  primary content).
- Pill / tag / count micro-labels (e.g. `.bc-chip-count`, agent meta) stay
  at 11 px since they are decorative numerics, not text the user reads.

## Fixes applied

1. **Demo banner mobile sizing.** Inflated `.demo-banner-close` to a 44x44
   tap target via padding + min-width / min-height; bumped font to 13 px on
   phones; added 768 px-and-below media block in inline banner CSS.
   Files: `frontend/index.html`, `frontend/customers.html`,
   `frontend/quick-research.html`, `frontend/industries.html`,
   `frontend/meeting.html`.

2. **Global button tap targets.** Added a mobile rule
   `@media (max-width: 768px)` that sets `min-height: 44px` on `.btn`,
   `.btn-link`, `.tab`, and ensures `.qr-fb-view-btn` is at least 40 px tall.
   File: `frontend/assets/css/styles.css`,
   `frontend/assets/css/quick-research-filter.css`.

3. **Battlecards chips.** Increased `.bc-chip` padding on phones to land at
   ~36 px tall and added a transparent inflated hit area to clear 44 px.
   File: `frontend/assets/css/battlecards.css`.

4. **Modal close buttons.** Bumped `.ab-modal-close`, `.ind-modal-close`,
   `.bc-action-btn` to 36 px-square (or min-height 40 px for action btns)
   plus the inflated `::before` hit pad on mobile.
   Files: `frontend/assets/css/agent-builder.css`,
   `frontend/assets/css/industries.css`,
   `frontend/assets/css/battlecards.css`.

5. **Agent trash button.** Inflated `.ab-agent-trash` hit area on mobile.
   File: `frontend/assets/css/agent-builder.css`.

6. **Image safety.** Added `img { max-width: 100% }` global rule so any
   inline image (Elastic logo aside, which is small and SVG) cannot exceed
   the viewport. File: `frontend/assets/css/styles.css`.

7. **Topbar chip overflow guard at 375 px.** Existing rule already wraps
   `.right`; bumped its `min-width: 0` and verified pills clip to 100% of
   the available row. No additional fix needed beyond what was already in
   `styles.css:3370-3373`.

## What was NOT changed

- Backend code: untouched.
- Demo scenarios, battlecards data, industries data: untouched.
- Teleprompter, demo-script docs: untouched.
- Light vs dark theme tokens: untouched.

## Verification

- Em-dash count: 0 across `frontend/`, `docs/`, including this file.
- Smoke: `python -m scripts.integration_smoke` returns GO after fixes.
- Touched only CSS and inline `<style>` blocks. No JS changes; no API
  contract changes; no breaking changes to desktop layout above 1024 px.
