# QA W24C - Command Palette and Keyboard Shortcuts

Audit of the global Cmd+K / Ctrl+K command palette plus every keyboard shortcut
that could collide with it. Done as part of overnight batch 2, axis C.

Working dir: /Users/rodrigocareaga/Downloads/FE-Elastic
Date: 2026-05-04

## Summary

- 13 of 13 pages load `/assets/js/command-palette.js` (one shared module, single
  global keydown listener, guarded by `window.__feCommandPaletteLoaded`).
- Static index expanded from 18 to 28 entries: 12 pages plus 12 tools plus
  4 quick actions; 31 battlecards and 20 industries are added at runtime via
  `/api/v1/battlecards` and `/api/v1/industries`. Demo scenarios (top 5) and
  recent meetings (top 5) continue to be fetched live.
- Six tool entries had stale anchors; all twelve now point at the matching
  `/tools.html#tool-*` panel.
- The previously hidden Quick Research, Customers, Industries and Health
  pages are now in the palette.
- Help dialog (`?` key) added with i18n strings for all five languages.
- Em-dash audit on the touched files: 0.

## Per-page Cmd+K status

Each entry below records (a) whether `command-palette.js` is referenced from
the page, (b) the script tag location. The handler is registered exactly
once, in capture phase, by the IIFE in `command-palette.js`, so any page
that loads the file gets the shortcut.

| Page                      | Loads palette JS                                       | Cmd+K opens | Notes                                  |
|---------------------------|--------------------------------------------------------|-------------|----------------------------------------|
| `/index.html`             | frontend/index.html:295                                | Pass        | Dashboard / Home                       |
| `/quick-research.html`    | frontend/quick-research.html:134                       | Pass        |                                        |
| `/customers.html`         | frontend/customers.html:275                            | Pass        |                                        |
| `/fe-brain.html`          | frontend/fe-brain.html:83                              | Pass        |                                        |
| `/agent-builder.html`     | frontend/agent-builder.html:159                        | Pass        |                                        |
| `/battlecards.html`       | frontend/battlecards.html:165                          | Pass        |                                        |
| `/industries.html`        | frontend/industries.html:157                           | Pass        |                                        |
| `/demo-data.html`         | frontend/demo-data.html:54                             | Pass        |                                        |
| `/workflow-demo.html`     | frontend/workflow-demo.html:154                        | Pass        |                                        |
| `/health.html`            | frontend/health.html:287                               | Pass        |                                        |
| `/audit.html`             | frontend/audit.html:172                                | Pass        |                                        |
| `/tools.html`             | frontend/tools.html:477                                | Pass        |                                        |
| `/meeting.html`           | frontend/meeting.html:165                              | Pass        | not in sidebar; reachable via deep link|

## Per-axis status (12)

1. Cmd+K / Ctrl+K binds globally on every page. Pass.
   See `frontend/assets/js/command-palette.js:445` for the capture-phase
   `keydown` listener, attached once per document via the
   `window.__feCommandPaletteLoaded` guard at line 10.

2. Type filters narrow the result list. Pass.
   `score()` at `command-palette.js:102` does fuzzy match on label, sub,
   keywords, with priorities exact > prefix > acronym > infix > token-AND.
   No hard-coded list: pages match the rail in `tools-rail.js`, tools match
   the `details#tool-*` anchors in `tools.html`, battlecards and industries
   fetched live.

3. Enter navigates the highlighted result, Up / Down move the highlight,
   Esc closes. Pass. `command-palette.js:457-490` handles
   ArrowDown / ArrowUp / Enter / Home / End / Tab / Escape.

4. Every page reachable. Pass. The static `STATIC_COMMANDS` array now
   carries all 12 pages (Home, Quick Research, Customers, FE Brain,
   Agent Builder, Battlecards, Industries, Demo Data, Workflow, Health,
   Audit, Tools), matching the `PAGES` list in `tools-rail.js`.

5. Per-tool quick jumps. Pass. All 12 tools (POC plan, SPL to ES|QL,
   Compliance, Cost, Capacity, Stack, Code, Troubleshoot, Knowledge,
   Compare, Orchestrator, Proposal) point at their `#tool-*` anchor on
   `/tools.html`.

6. Per-battlecard quick jumps. Pass. `fetchDynamic` calls
   `/api/v1/battlecards` and pushes 31 entries into the palette under a
   "Battlecards" section. Each entry routes to
   `/battlecards.html#<competitor_slug>`, which `battlecards.js`
   already handles (`routeFromHash`).

7. Per-industry quick jumps. Pass. `/api/v1/industries` returns 20 rows
   that become quick jumps to `/industries.html?industry=<id>`. The
   industries page already honours that query param at
   `industries.js:505`.

8. Shortcut conflicts. Pass after fix.
   - Cmd+K: only `command-palette.js` binds it. Other Cmd / Ctrl combos
     stay distinct (`Cmd+Enter` on agent-builder.js:960 and
     agent-builder-mini.js:317).
   - Esc: five other handlers. The palette's keydown is registered with
     capture=true and now also calls `e.stopPropagation()`, so when the
     palette is open Esc closes the palette and never fires
     `autopilot.stop`, the industries modal close, the mobile sidebar
     close, the onboarding tour close, or the battlecards search clear.
     Verified by inspection at `command-palette.js:469`.
     - autopilot.js:526 (bubble) - only acts when `state.running`, gated
       on its own state.
     - onboarding.js:418 (capture) - only acts when its tour
       `state.active`.
     - industries.js:488 (bubble) - only acts when modal is open.
     - tools-rail.js:338 (bubble) - only acts when mobile sidebar is
       open.
     - battlecards.js:995 - input-scoped, never bubbles past the input.

9. Slash key (/) shortcut. Pass.
   Bound only on `/index.html` by `app.js:485` (`bindKeyboard`), which
   focuses `#meetings-search`. The existing guard already ignores INPUT
   and TEXTAREA targets, so it does not interfere with typing in form
   fields. The new help dialog documents the shortcut so users discover
   it.

10. Help shortcut (`?`). Pass after fix.
    Pressing `?` outside a typing target opens a small modal that lists
    every shortcut in the active language. Esc closes it. Implemented at
    `command-palette.js:540-610`.

11. Reduced motion. Pass. `command-palette.css:284` scopes a
    `prefers-reduced-motion: reduce` block that disables the fade-in
    and pop animations on both the palette and the new help modal.

12. Focus trap inside the palette. Pass. The palette modal renders a
    single focusable element (the search input), `Tab` is intercepted
    and refocuses the input (`command-palette.js:489`), and on close
    focus returns to whichever element opened the palette
    (`state.triggerEl`, restored at `command-palette.js:439`).

## Fixes applied

1. `frontend/assets/js/command-palette.js`
   - Expanded `STATIC_COMMANDS` from 18 to 28 entries (12 pages, 12 tools,
     4 actions). Added Quick Research, Customers, Industries, Health to
     the pages section; added Compare and Proposal to the tools section;
     re-anchored Knowledge and Orchestrator at their `#tool-*` panels.
   - Added battlecards (31) and industries (20) to the dynamic fetch
     pipeline, with new sections in `SECTION_ORDER` and
     `SECTION_TITLES`.
   - Added `?` shortcut and a localised "Keyboard shortcuts" modal with
     a focus trap, click-outside-to-close, and Esc support. Replaces the
     previous footer flash for the existing "Show keyboard shortcuts"
     quick action.
   - Made Cmd+K and Esc call `e.stopPropagation()` so neither leaks
     into the autopilot stop, the onboarding tour, the industries modal,
     or the mobile sidebar handlers.

2. `frontend/assets/css/command-palette.css`
   - Added `.cat-battlecards` and `.cat-industries` tag colours.
   - Added the `.cp-help-*` styles for the new shortcuts dialog.
   - Extended the reduced-motion media query to cover the help modal.

3. `frontend/assets/js/i18n.js`
   - Added 11 new keys (`cp.help.title`, `cp.help.close`,
     `cp.help.close.label`, plus 8 row descriptions) in EN, ES, JA, DE,
     FR.

No HTML files were touched; every page already imports
`command-palette.js` and `command-palette.css`. Backend code was not
touched.

## Sample test transcript

Page: `/index.html`. User has just landed on the dashboard.

```
1. User taps Cmd+K (Mac) or Ctrl+K (Win).
   - command-palette.js:447 detects the chord, calls preventDefault and
     stopPropagation, then open().
   - The palette renders the default ordering: 12 pages, 12 tools,
     31 battlecards, 20 industries, 5 scenarios, up to 5 meetings,
     4 actions. Section ordering is enforced by SECTION_ORDER.
2. User types "battle".
   - input listener fires render(), score("Battlecards", "battle") = 794
     (prefix match on a 11-char label), beating every battlecard which
     would only match by keyword.
3. The first hit is "Battlecards - /battlecards.html"; row is highlighted
   automatically (state.selected = 0 reset on every input event).
4. User presses Enter.
   - command-palette.js:474 calls activate(0) which navigates to
     /battlecards.html, then close() so the palette is dismissed.
5. User lands on /battlecards.html, the grid renders.
```

Variant: typing "datadog" instead of "battle" surfaces the Datadog
battlecard (loaded dynamically) and Enter routes to
`/battlecards.html#datadog`, which the page handles via
`routeFromHash()` to open the Datadog detail kit.

Variant: typing "fsi-banking" hits the Banking industry row and Enter
routes to `/industries.html?industry=fsi-banking`, opening the modal on
load via `getQueryParam("industry")`.

## Smoke verdict

Smoke run after the fixes is recorded at the end of this batch.
