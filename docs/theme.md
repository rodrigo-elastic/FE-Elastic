# Theme system: dark + light

FE Copilot ships with a dark default and a fully audited light theme. Theme
state lives on `<html>` as `data-theme="dark"` or `data-theme="light"`,
persisted in `localStorage.fec.theme`. First load respects
`prefers-color-scheme` from the OS unless a stored choice exists.

## Files touched

| File                                        | What it owns                                                                                  |
| :---                                        | :---                                                                                          |
| `frontend/assets/css/styles.css`            | Canonical token palette: `:root` defines the light theme, `[data-theme="dark"]` overrides it. |
| `frontend/assets/css/agent-builder.css`     | Agent builder chat bubbles, mini composer, demo-data cards.                                   |
| `frontend/assets/css/fe-brain.css`          | RAG answer column, citation cards, code blocks.                                               |
| `frontend/assets/css/battlecards.css`       | Battlecards grid + detail view + sticky toolbar.                                              |
| `frontend/assets/css/audit.css`             | KPIs, SVG charts (already used `currentColor` / tokens), rollup table.                        |
| `frontend/assets/css/autopilot.css`         | Hero CTA picks up tokens. The fixed-position autopilot stage stays dark by design.            |
| `frontend/assets/css/command-palette.css`   | Cmd-K modal, scrim now uses `--scrim`.                                                        |
| `frontend/assets/js/tools-rail.js`          | Theme bootstrap (FOUC-safe), toggle button, OS-pref listener.                                 |
| `frontend/assets/js/i18n.js`                | Two new keys, five locales: `theme.toggle.toLight`, `theme.toggle.toDark`.                    |

## Token table

Every selector that paints surface, text, border, code or shadow now reads a
semantic CSS variable. Component code never branches on theme.

| Token                                   | Light                                          | Dark                              |
| :---                                    | :---                                           | :---                              |
| `--bg`                                  | `#f7f8fa`                                      | `#0e1014`                         |
| `--bg-elev`                             | `#ffffff`                                      | `#161a21`                         |
| `--ink`                                 | `#1d2128`                                      | `#e6e8eb`                         |
| `--ink-2` / `--ink-soft`                | `#373a42`                                      | `#cfd2d6` / `#DDE2EA`             |
| `--muted`                               | `#62676f`                                      | `rgba(255,255,255,0.62)`          |
| `--muted-2`                             | `#8a8f96`                                      | `rgba(255,255,255,0.45)`          |
| `--panel` / `--panel-2` / `--panel-3`   | `#ffffff` / `#f3f5f7` / `#e9ecef`              | `#161a21` / `#1d2128` / `#252a33` |
| `--border` / `--border-strong` / `--border-soft` | `#d0d4dc` / `#a4a9b3` / `#e2e5ea` | `rgba(255,255,255,0.14)` / `0.28` / `0.08` |
| `--primary` / `--primary-hi` / `--primary-soft` | Lochmara `#0077CC` (constant) / `#1B8FE5` / 12% | Lochmara / `#1B8FE5` / 18%   |
| Brand accents (`--teal`, `--pink`, `--blue`, `--yellow`, `--green`, `--red`) | Same hue across themes; only `*-soft` opacity varies. |
| `--code-bg` / `--code-fg` / `--code-border` | `#f3f5f7` / `#1d2128` / `#d0d4dc`         | `#0d1117` / `#e6edf7` / 8% white  |
| `--scrim`                               | `rgba(15,18,25,0.5)`                           | `rgba(0,0,0,0.55)`                |
| `--shadow-sm` / `--shadow-md` / `--shadow-lg` | Subtle 2 / 8 / 14% drops on near-black ink | Heavier drops on pure black     |

## How the toggle works

The button lives in `.topbar .right`, injected by `tools-rail.js` just before
`.lang-host`. Click handler:

1. Read current `data-theme` from `<html>`.
2. Flip `dark <-> light`, write to `localStorage.fec.theme`.
3. Re-render the icon (sun = currently dark, moon = currently light) and
   `aria-label` (`theme.toggle.toLight` or `theme.toggle.toDark`).
4. Dispatch a `fec:themechange` window event so any chart code that wants to
   redraw can listen.

If no localStorage value exists, the bootstrap respects
`window.matchMedia('(prefers-color-scheme: dark)')`. If the OS pref later
changes and the user never toggled manually, the listener tracks it.

## FOUC mitigation

The bootstrap is the very first statement inside the `tools-rail.js` IIFE,
before any DOM render. It runs synchronously on `<script src="...">` parse
because we read localStorage and `prefers-color-scheme` and set the `<html>`
attribute immediately. Net result: even on a light-mode OS opening the app
for the first time, the page already paints with the light tokens.

## Audit before / after

`grep -cE 'rgba\(255,\s*255,\s*255'` across the seven owned CSS files:

| File                  | Before | After (excluding token defs and `[data-theme="dark"]` blocks) |
| :---                  | ---:   | ---:                                                          |
| `styles.css`          |  10    | 1 (translucent topbar fallback in `var()`)                    |
| `agent-builder.css`   |  41    | 0                                                             |
| `fe-brain.css`        |  25    | 0                                                             |
| `battlecards.css`     |  29    | 1 (translucent sticky toolbar fallback)                       |
| `audit.css`           |   4    | 0                                                             |
| `autopilot.css`       |  15    | 12 (intentional, cinematic dark presenter overlay)            |
| `command-palette.css` |   1    | 0                                                             |

Total token count added to `styles.css :root` and `[data-theme="dark"]`: 28
semantic tokens (bg, bg-elev, panel x3, border x3, ink/ink-2/ink-soft,
muted x2, primary x3, accent soft x4, code x3, scrim, shadow x3, plus
constants and aliases).

## Em / en dash audit

```
grep -P '[\x{2014}\x{2013}]' frontend/assets/css/*.css frontend/assets/js/i18n.js frontend/assets/js/tools-rail.js docs/theme.md
```

returns nothing for the files this change owns.

## Verification checklist

- `/`, `/tools.html`, `/meeting.html?id=...`, `/agent-builder.html`,
  `/demo-data.html`, `/workflow-demo.html`, `/fe-brain.html`,
  `/battlecards.html`, `/audit.html`: each renders cleanly in both themes.
- `--muted` (`#62676f`) on `--bg` (`#f7f8fa`) is approximately 5.9:1, so
  body copy passes WCAG AA.
- localStorage persistence: toggle, reload, choice survives.
- Cleared localStorage + DevTools "emulate prefers-color-scheme: light" +
  hard reload of `/`: app starts in light. Same with dark.
- The autopilot overlay (cinematic mode), command palette scrim, FE Brain
  citations panel, agent-builder mini chat, and battlecards detail view all
  look polished under both themes.
