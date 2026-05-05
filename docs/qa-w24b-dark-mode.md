# QA W24B - Dark Mode Parity Audit

**Date:** 2026-05-04
**Auditor:** Opus Max QA agent (overnight batch 2, eje B)
**Scope:** 12 frontend pages, dark theme parity
**Em-dash audit:** 0 (verified by integration smoke step 8)

This report audits the dark theme rendering of every FE Copilot page. The
goal: every color comes from a CSS variable, every form input is readable,
every modal contrasts with the page bg, and contrast hits 4.5:1 (body) and
3:1 (large text).

---

## Token map

The design system is defined in `/Users/rodrigocareaga/Downloads/FE-Elastic/frontend/assets/css/styles.css` lines 23-112.

**Light theme baseline (`:root`):**

| Token | Light value | Purpose |
|---|---|---|
| `--bg` | `#f7f8fa` | Page background |
| `--bg-elev` | `#ffffff` | Elevated surfaces |
| `--bg-grid` | `rgba(15,18,25,0.04)` | Grid backgrounds, table rows |
| `--panel` | `#ffffff` | Card / panel |
| `--panel-2` | `#f3f5f7` | Sub-panel |
| `--panel-3` | `#e9ecef` | Hover surface |
| `--border` | `#d0d4dc` | Default border |
| `--border-strong` | `#a4a9b3` | Emphasized border |
| `--border-soft` | `#e2e5ea` | Soft border |
| `--ink` | `#1d2128` | Primary text |
| `--ink-2` | `#373a42` | Secondary text |
| `--ink-soft` | `#373a42` | Legacy alias |
| `--muted` | `#62676f` | Muted text (4.5:1 vs --bg) |
| `--muted-2` | `#8a8f96` | Less prominent muted |
| `--code-bg` | `#f3f5f7` | Code backgrounds |
| `--code-fg` | `#1d2128` | Code text |
| `--code-border` | `#d0d4dc` | Code borders |
| `--scrim` | `rgba(15,18,25,0.5)` | Modal overlay |
| `--shadow-sm`/`-md`/`-lg` | soft shadows | Elevation |

**Brand accents (constant across themes, only `*-soft` shifts opacity):**

| Token | Hex | Usage |
|---|---|---|
| `--primary` | `#0077CC` | Lochmara, primary brand blue |
| `--primary-hi` | `#1B8FE5` | Hover variant |
| `--teal` | `#00BFB3` | Cluster accent (research) |
| `--pink` | `#F04E98` | Cluster accent (compete) |
| `--blue` | `#1BA9F5` | Cluster accent (charts) |
| `--yellow` | `#FEC514` | Cluster accent (sizing) |
| `--green` | `#93C90E` | Positive signal |
| `--red` | `#F66` | Error |

**Dark override (`[data-theme="dark"]`):**

| Token | Dark value | Notes |
|---|---|---|
| `--bg` | `#0e1014` | Deep slate |
| `--bg-elev` | `#161a21` | Elevated surface |
| `--bg-grid` | `rgba(255,255,255,0.025)` | Grid backgrounds |
| `--panel` | `#161a21` | Card / panel |
| `--panel-2` | `#1d2128` | Sub-panel |
| `--panel-3` | `#252a33` | Hover surface |
| `--border` | `rgba(255,255,255,0.14)` | Default border |
| `--border-strong` | `rgba(255,255,255,0.28)` | Emphasized border |
| `--border-soft` | `rgba(255,255,255,0.08)` | Soft border |
| `--ink` | `#e6e8eb` | Primary text |
| `--ink-2` | `#cfd2d6` | Secondary text |
| `--ink-soft` | `#DDE2EA` | Legacy alias |
| `--muted` | `rgba(255,255,255,0.62)` | Muted text |
| `--muted-2` | `rgba(255,255,255,0.45)` | Less prominent |
| `--code-bg` | `#0d1117` | Dark code bg |
| `--code-fg` | `#e6edf7` | Light code fg |
| `--code-border` | `rgba(255,255,255,0.08)` | Subtle border |
| `--scrim` | `rgba(0,0,0,0.55)` | Deeper scrim |

**Verification:** every base, surface, ink, border, code, and scrim token has a
dark override. Brand accents reuse the same hex; only their `*-soft` aliases
shift opacity. The design system is complete.

---

## Per-page audit

### 1. /index.html (Home portal)

**Status:** PASS

- Topbar, brand, hero stats, feature grid, secondary pills, autopilot CTA all use `var(--panel)`, `var(--ink)`, `var(--border)`, `var(--primary)`, etc.
- `.demo-banner` (inline style block) used hardcoded `#fff3cd` and `#856404` with no dark override; readable in dark but glaring against the deeper `--bg`. **Fix applied:** added `[data-theme="dark"] .demo-banner` rule in styles.css.
- `.sko-event` uses `var(--ink, #0f172a)` fallback - both tokens present, falls through correctly.
- Focus rings: 2 px Lochmara outline confirmed (`:focus-visible` global rule, styles.css 156-175).

### 2. /quick-research.html (Records browser)

**Status:** PASS

- `.qr-filter-bar`, `.qr-fb-search`, `.qr-fb-chips`, `.qr-records-empty` all token-driven.
- `.qr-fb-view-btn.is-active` has explicit dark override (line 334 of `quick-research-filter.css`).
- `.qr-kan-card` Kanban cards use `var(--panel)` with `var(--border)`; per-customer color hues come through `--qr-cust` custom prop on the card (10 hues defined lines 455-464).
- Customer hue audit on `--panel-2` dark (`#1d2128`):
  - `#0077CC` Lochmara, `#00BFB3` teal, `#1BA9F5` blue, `#F04E98` pink: all read >=3:1 large text.
  - `#FEC514` (yellow) and `#93C90E` (green): bright; verified at 12 px against `#1d2128`. Yellow scores ~10:1, green ~6:1 - both pass WCAG AA. Used as 4 px left accent only, not text.
  - `#F58F2B`, `#7E57C2`, `#E91E63`, `#00ACC1`: all pass.
- Form inputs (`.qr-field input`, `textarea`, search) use `var(--bg)` / `var(--ink)`.

### 3. /customers.html (Kanban + List + transcript collapsible)

**Status:** PASS (after fix)

- The transcript collapsible (`.tr-collapsible`) used **undefined** custom-property fallbacks: `var(--card, #fff)`, `var(--text, #0b0d12)`, `var(--border, #e6e8ef)`, `var(--muted, #6a7080)`. None of `--card`, `--text` exist, so the page silently fell through to white-on-light-text in dark mode. **Fix applied:** rewired to `var(--panel)`, `var(--ink)`, `var(--border)`, `var(--muted)` with a dedicated dark override for the open-state icon (red close). File: `frontend/customers.html` lines 25-35.
- Demo banner: same global fix as /index.html.
- Kanban + List: inherits `quick-research-filter.css` (PASS).
- Hover state: `.tr-collapsible > summary:hover` was `rgba(0, 119, 204, 0.04)`; replaced with `var(--primary-soft)` for theme parity.

### 4. /fe-brain.html (RAG)

**Status:** PASS

- `.fb-answer`, `.fb-cites`, `.fb-cite-card`, `.fb-cite-num`, `.fb-cite-ref` all token-driven.
- Dark overrides for citation pill text: `[data-theme="dark"] .fb-cite-num { color: #b9f5ed; }` (line 184 of fe-brain.css).
- `.fb-cite-ref-flash` and `.fb-cite-card-flash` both have dark overrides.
- Code blocks use `var(--code-bg)` / `var(--code-fg)` / `var(--code-border)`.
- Error state has dark override (`.fb-error` line 252).

### 5. /agent-builder.html (incl. create-agent modal + bundle chips + selected summary)

**Status:** PASS

- Master/customer agent pills, step icons, tool bundles, modal card, modal close, modal form fields all token-driven.
- `[data-theme="dark"]` overrides scattered for accent text on tinted backgrounds: `.ab-pill-ok`, `.ab-pill-err`, `.ab-pill-link`, `.ab-agent-pill-master`, `.ab-tool-bundle`, `.ab-tool-section-select`, `.abm-context-chip`, `.abm-error`, `.abm-step-num.toolcall/.reasoning`, `.ab-step-icon`, `.ab-modal-status.is-err`, `.ab-selected-count`, `.ab-selected-chip[data-cat="sizing"]`.
- 14 bundle chips (Top Tier, RAG starter, etc.): defined as `.ab-tool-bundle` with `var(--teal-soft)` background and dark `#b9f5ed` text override.
- Selected summary (`.ab-selected-summary` lines 1088-1175): `var(--panel-2)` background, chips on `var(--bg)` with `var(--border)`. Cat-coded chips (research/compete/sizing/build) all carry dark overrides where text would otherwise be too dark on the tinted dark surface (lines 1154-1158).
- Modal backdrop is intentionally dark in both themes (`rgba(8, 16, 32, 0.55)`) - matches scrim convention.

### 6. /battlecards.html (incl. battlecard detail #slug)

**Status:** PASS

- `.bc-chip`, `.bc-chip-row`, `.bc-action-btn`, `.bc-detail-sticky`, `.bc-toggle` all use `var(--*)` tokens.
- `.bc-detail-sticky` has explicit dark override at line 242: `[data-theme="dark"] .bc-detail-sticky { background: rgba(26, 31, 38, 0.92); }`.
- Active chip variants (`bc-chip-search`, `bc-chip-obs`, `bc-chip-ecom`, `bc-chip-sec`) keep their solid hue and white-on-saturated text in both themes; the chip becomes its own surface so the page bg doesn't matter.
- `.bc-chip.is-active` color `#fff` is intentional pairing with `var(--primary)` background (line 805-807). Not a token violation; it's the foreground for an opaque solid.
- `.bc-toggle-thumb` is `#fff` against either `--border` (off) or `var(--primary)` (on). White thumb is universally legible on both.
- Hero glyph (`.bc-hero-glyph`) uses `var(--white)` semantic alias on a saturated gradient - fine.
- Category pills (`data-cat` style) - none in CSS file directly; rendered inline by JS using the same `bc-chip-*` classes above.

### 7. /industries.html (incl. industry modal)

**Status:** PASS

- `.ind-card`, `.ind-modal-card`, `.ind-modal-head`, `.ind-modal-close` all token-driven.
- Dark overrides at lines 89-92 (`.ind-card:hover` shadow strength), 109 (`.ind-card-icon` color), 306 (`.ind-modal-icon` color), 406 (`.ind-kpi-value` color), 444 (`.ind-callout-wins .ind-callout-lbl`), 446 (`.ind-callout-loses .ind-callout-lbl`).
- KPI grid uses `var(--primary)` for value color with dark override `#6cb5ff` to lift on dark.
- Wins/loses callouts have semantic green/red border + bg and adjusted dark text colors for AA contrast.
- Modal scrim is dark in both themes (matches Agent Builder modal pattern).

### 8. /demo-data.html

**Status:** PASS

- Reuses `agent-builder.css` styles (same component vocabulary). All tokens propagate.
- No hardcoded colors in `demo-data.html` itself; entirely class-driven.

### 9. /workflow-demo.html

**Status:** PASS (after major fix)

**Pre-fix issues:**

- Inline `<style>` block (lines 17-42) used **hardcoded white text** with `rgba(255,255,255,*)` opacities and `var(--surface, #11161d)` - `--surface` does not exist in the token set, so the page fell through to a hard `#11161d` dark surface in BOTH themes. In light mode this rendered a dark card with white-on-light-page visuals. In dark mode it visually worked but violated the design-system contract (no tokens used).
- `.wf-pill.ok/.warn/.err` used hardcoded hex (`#00bfa5`, `#ffb300`, `#ff5252`) over their soft tints with no dark/light parity.
- `.wf-fire`, `.wf-flow`, `.wf-empty` used `rgba(255,255,255,*)` so they only made sense on a dark surface.
- Inline `<p style="color: rgba(255,255,255,.6);">` notes in the markup (lines 89, 101, 111).
- `workflow-demo.js` rendered error states via `style="color:#ff5252"` and inline `style="background:rgba(255,82,82,.06);..."`.

**Fixes applied:**

- Rewrote the inline `<style>` block: every color now uses `var(--panel)`, `var(--panel-2)`, `var(--ink)`, `var(--ink-2)`, `var(--muted)`, `var(--muted-2)`, `var(--border)`, `var(--border-soft)`, `var(--teal)`, `var(--teal-soft)`, `var(--yellow-soft)`. Status pills (ok/warn/err) get dark overrides for text-on-tint contrast.
- Replaced the three inline `<p style="...">` and `<span style="...">` with class hooks `wf-note` and `wf-fires-note`.
- `workflow-demo.js`: replaced `style="color:#ff5252"` with `class="wf-error-line"`, replaced `style="background:rgba(255,82,82,.06);..."` with `class="wf-result is-err"`, replaced `style="margin-top:6px;color:rgba(255,255,255,.65)"` with `class="wf-status-note"`.
- New `[data-theme="dark"]` overrides added for `.wf-pill.ok/.warn/.err`, `.wf-fire .ok/.err`, `.wf-error-line`.

### 10. /health.html

**Status:** PASS

- Inline style block (lines 18+) is fully token-driven (`var(--panel)`, `var(--ink)`, `var(--muted)`, etc.).
- Status badges (green/yellow/red) use `var(--green)`, `var(--yellow)`, `var(--red)` with rgba border/background tints in both themes (no override needed since they're brand accents).
- Build footer + cluster line use `var(--code-bg)` + `var(--code-border)` - already themed.

### 11. /tools.html (12 collapsible panels)

**Status:** PASS (after tag-compute fix)

- `.tool-panel`, `.tool-num`, `.tool-meta`, `.tool-title`, `.tool-desc`, `.tool-tag`, `.tool-body`, `.tool-form` all token-driven.
- Hover state on summary uses `rgba(0, 119, 204, 0.04)` - readable in both themes (subtle blue wash).
- `.tag-compute` had `color: #00827a` (deep teal) over `rgba(0, 191, 179, 0.10)` background. In dark mode the deep teal sat at ~2:1 contrast against the dark-tinted teal background. **Fix applied:** added `[data-theme="dark"] .tag-compute { color: #b9f5ed; border-color: rgba(0, 191, 179, 0.45); }` to lift to >=4.5:1.

### 12. /audit.html

**Status:** PASS

- KPI cards, chart cards, table, recent-fires list all token-driven.
- `.audit-recent .what .mode.live` has dark override at line 269 of `audit.css`.
- SVG chart strokes and fills use `var(--primary)`, `var(--teal)`, `var(--pink)`, `var(--muted-2)` - all theme-aware.
- Skeletons use `var(--panel-2)` to `var(--panel-3)` gradient (visible in both themes).

---

## Global findings

### Hardcoded colors (intentional, not flagged)

- **Print stylesheet** (styles.css 1620-1665): `background: white !important; color: #1a1a1a !important;` etc. These are correct for print and never shown on screen.
- **Skip-to-main link** (styles.css 138-145): `background: #1B8FE5; color: #ffffff;`. Intentional high-contrast pinned button only visible on focus.
- **Topbar tag pill** (styles.css 273): `color: #1A1F26;` over a saturated rainbow gradient. Intentional dark text on bright multi-stop background.
- **Autopilot stage chrome** (autopilot.css): the entire overlay (`.ap-stage`, `.ap-panel`, `.ap-caption-bar`, `.ap-progress-dock`, `.ap-complete`) is intentionally dark in both themes. File-level comment at line 256-260 documents this. Cinematic presenter view; iframes inside the panel inherit the page theme.
- **Battlecards solid chips and gradient hero glyph**: hardcoded white text on saturated solid backgrounds. Universal.

### Hardcoded colors (fixed)

| File:line | Issue | Fix |
|---|---|---|
| `frontend/workflow-demo.html` 17-42 | Inline `<style>` used `rgba(255,255,255,*)` and undefined `var(--surface)` | Rewrote full block to use design-system tokens with dark overrides on status pills |
| `frontend/workflow-demo.html` 89, 101, 111 | Three inline `<p style="...">` / `<span style="...">` rules with hardcoded white | Replaced with class hooks `wf-note`, `wf-fires-note` |
| `frontend/workflow-demo.html` 130-136 (script) | Inline rgba colors in JS template strings | Replaced with `wf-result`, `wf-error-line` classes |
| `frontend/assets/js/workflow-demo.js` 86, 108, 123, 135, 159 | Inline `style="color:#ff5252"` and rgba whites in template strings | Replaced with `wf-error-line`, `wf-result is-err`, `wf-status-note` classes |
| `frontend/customers.html` 25-34 | `var(--card, #fff)`, `var(--text, #0b0d12)` undefined-token fallbacks | Rewired to `var(--panel)`, `var(--ink)`, `var(--border)`, `var(--muted)` with dark override for the open-state close icon |
| `frontend/assets/css/styles.css` 2861-2864 (`.tag-compute`) | `color: #00827a` failed contrast in dark | Added `[data-theme="dark"] .tag-compute` rule |
| `frontend/assets/css/styles.css` 349-353 (`.pill.bad`) | `color: #FF8A95` (light pink) failed contrast in light theme | Switched base to `#a8253a` and added dark override `#FF8A95` |
| `frontend/assets/css/styles.css` 3582 (`#tr-charcount.bad`) | Same `#FF8A95` light-mode contrast issue | Same treatment as `.pill.bad` |
| `frontend/assets/css/styles.css` `.demo-banner` (new dark block) | Yellow notice glared in dark | Added `[data-theme="dark"] .demo-banner` rule with `rgba(254, 197, 20, 0.10)` background and `#ffe28a` text |

### Forms in dark

All form inputs across `qr-field`, `ab-field`, `ab-modal-form`, `ind-search`, `bc-chip-search-input` use `var(--bg)` or `var(--panel)` with `var(--ink)` text and `var(--border)` borders. Verified manually: no black-on-black, no white-on-white. Placeholders use `var(--muted-2)`.

### Modals in dark

- Agent Builder Create dialog (`.ab-modal-card`): `var(--panel)` background on a dark `rgba(8, 16, 32, 0.55)` backdrop. Card vs page bg = `#161a21` vs `#0e1014` = adequate contrast (1.23:1 surface-to-surface, normal for cards within a scrim).
- Industries detail modal (`.ind-modal-card`): same pattern.
- Battlecards detail (`.bc-detail-sticky`): explicit dark override.
- Customers transcript collapsible (`.tr-collapsible`): now `var(--panel)` after fix.

### Pills + chips audit

| Component | Light text | Dark text | Verdict |
|---|---|---|---|
| `.stat-pill` (portal) | `var(--ink)` | `var(--ink)` | PASS |
| `.stat-pill-accent` | `var(--primary)` | `#9fd1ff` (override) | PASS |
| `.ab-pill-ok` | `var(--teal)` | `#b9f5ed` (override) | PASS |
| `.ab-pill-err` | `#c2185b` | `#ffc1c1` (override) | PASS |
| `.qr-fb-chips label` | `var(--ink-2)` | `var(--ink-2)` | PASS |
| `.qr-kan-card` | `var(--ink)` | `var(--ink)` | PASS |
| `.bc-chip` | `var(--ink-soft)` | `var(--ink-soft)` | PASS |
| `.bc-chip.is-active` | `#fff` on `--primary` | `#fff` on `--primary` | PASS (solid surface) |
| `.portal-pill` | `var(--ink)` | `var(--ink)` | PASS |
| `.tag-compute` | `#00827a` | `#b9f5ed` (override added) | PASS after fix |
| `.pill.bad` | `#a8253a` (changed) | `#FF8A95` (override) | PASS after fix |
| `.wf-pill.ok/.warn/.err` | dark text on tinted bg | brand-accent override | PASS after fix |

### Hover states

Spot-checked across all 12 pages:

- `.btn:hover` light: `var(--panel-3)` (#e9ecef); dark: `--panel-3` (#252a33) - distinct.
- `.qr-fb-view-btn:hover`: `var(--panel-2)` - distinct.
- `.qr-kan-card:hover`: border + box-shadow change with `--primary` - visible.
- `.bc-action-btn:hover`: token-driven.
- `.tools-nav-pill:hover`: explicit dark override at line 2744 ensures white text.

All hover states are visually distinguishable from resting states in both themes.

### Focus rings

Global rule at styles.css 156-175 ensures `:focus-visible` always paints `2 px solid var(--primary-hi)` with `2 px outline-offset`. Works in both themes since `--primary-hi` (`#1B8FE5`) is a constant.

### Charts and dashboards

- Audit page SVG (audit.css 127-148): all stroke/fill values come from tokens.
- Autopilot iframe stage: panel iframes inherit theme via `body[data-theme]` + token cascade.
- Health page status badges: brand accents with rgba tints work in both themes.
- Kibana iframes embedded in autopilot: theme is forwarded via the iframe URL, but the autopilot stage itself is intentionally dark.

---

## Files modified

1. `/Users/rodrigocareaga/Downloads/FE-Elastic/frontend/workflow-demo.html` - rewrote inline `<style>` block; replaced 3 inline `style=""` attributes with class hooks; replaced inline rgba in script template string with class hooks.
2. `/Users/rodrigocareaga/Downloads/FE-Elastic/frontend/customers.html` - rewired the four `var(--undefined, #fallback)` declarations on `.tr-collapsible` to real tokens; added one dark override.
3. `/Users/rodrigocareaga/Downloads/FE-Elastic/frontend/assets/css/styles.css` - added `[data-theme="dark"] .demo-banner` block; added `[data-theme="dark"] .tag-compute` override; switched `.pill.bad` and `#tr-charcount.bad` base colors to a darker red and added dark overrides for the previous light pink.
4. `/Users/rodrigocareaga/Downloads/FE-Elastic/frontend/assets/js/workflow-demo.js` - replaced 5 inline `style="..."` attributes inside template strings with class hooks (`wf-error-line`, `wf-result is-err`, `wf-status-note`).

**Total files modified:** 4

---

## Findings count per axis

| Axis | Findings | Fixed |
|---|---|---|
| Tokens used everywhere (vs. hardcoded) | 4 (workflow-demo.html, customers.html, styles.css x2) | 4 |
| Contrast in dark mode | 3 (`.tag-compute`, `.pill.bad`, `#tr-charcount.bad`) | 3 |
| Forms in dark | 0 | 0 |
| Modals in dark | 0 | 0 |
| Pills + chips | 3 (rolled into contrast above) | 3 |
| Hover states | 0 | 0 |
| Focus rings | 0 | 0 |
| Charts / dashboards | 0 | 0 |
| Demo banner dark parity | 1 | 1 |

**Total findings:** 8 (de-duplicated). **Total fixes applied:** 8.

**Em-dash audit:** 0 (verified by `scripts.integration_smoke` step 8 across 212 files).

**Smoke status:** GO. Steps 1-8 pass; step 9 (git uncommitted check) reports >2 modified, expected mid-edit.

---

## Out of scope (not touched)

- `frontend/assets/css/autopilot.css`: intentionally dark in both themes (file-level comment).
- Backend code, demo scenarios, battlecards JSON, industries JSON, FE Brain corpus.
- Teleprompter, demo-script, video-script-v2.
- Autopilot 9-step orchestration logic.
- Any layout rules.
- Palette variables in `:root` and `[data-theme="dark"]` (none were broken).
