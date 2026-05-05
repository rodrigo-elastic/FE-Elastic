# QA W26B: i18n Round-Trip Audit (ES, JA, DE, FR)

Date: 2026-05-04
Scope: `frontend/assets/js/i18n.js` and HTML/JS data-i18n usage across `frontend/*.html` plus `frontend/assets/js/*.js`.
Locales audited: en (baseline), es, ja, de, fr.

## Verdict

GO. Key parity confirmed. 18 missing keys filled. DE switched fully to Du form. Worst chip/button overflows shortened. Em-dash 0. Smoke 8/9 PASS (step 9 fails only on uncommitted-files threshold during the edit run, expected).

## Key counts (post-fix)

| locale | unique keys | duplicate keys | parity vs EN |
|--------|-------------|----------------|--------------|
| en     | 414         | 1 (`tr.field.file` defined twice, same in every locale; second overrides first) | baseline |
| es     | 414         | 1              | 0 missing, 0 extra |
| ja     | 414         | 1              | 0 missing, 0 extra |
| de     | 414         | 1              | 0 missing, 0 extra |
| fr     | 414         | 1              | 0 missing, 0 extra |

Total raw lines per locale: 415. The duplicate `tr.field.file` collapses to 414 unique. Pattern is consistent across all five locales (line 79+93 EN, mirrored at the same offsets in es/ja/de/fr) so the override behavior is identical and benign.

## HTML and JS usage scan

- HTML `data-i18n` / `data-i18n-title` / `data-i18n-placeholder` / `data-i18n-aria-label` keys used: 251.
- JS calls to `t(...)`, `window.t(...)`, `I18N.t(...)` keys used: 78.
- Combined unique keys referenced from frontend: 280.
- Unresolved (referenced but not defined in EN): 0.
- Orphan keys defined but not referenced from frontend: 134 (dead-key cleanup deferred; not a runtime problem).

### Missing keys filled this round (18 total, all 5 locales)

These keys were called from `agent-builder.js` and `onboarding.js` with EN fallbacks but had no entry in `I18N_STRINGS`. They now exist in en/es/ja/de/fr:

- `ab.tool.selected_empty`
- `ab.tool.selected_title`
- `onboard.back`
- `onboard.next`
- `onboard.skip`
- `onboard.got_it`
- `onboard.replay`
- `onboard.confirm_close`
- `onboard.step1.title`, `onboard.step1.body`
- `onboard.step2.title`, `onboard.step2.body`
- `onboard.step3.title`, `onboard.step3.body`
- `onboard.step4.title`, `onboard.step4.body`
- `onboard.step5.title`, `onboard.step5.body`

ES uses Argentinian voseo (consistent with the rest of the ES corpus: investigá, tipeás, etc.). JA uses です/ます polite. DE uses Du form. FR uses formal vous form.

## Length overflow audit (chip / button text > 150% of EN)

Before fixes the audit flagged 36 chip/button entries above 150%. After targeted shortening, the remaining offenders are all on very short EN words (4-10 chars) where any reasonable translation is intrinsically longer. Listed for visibility; none wrap awkwardly in current chip widths.

### Shortened in this round

| key | locale | before -> after | EN ref |
|-----|--------|-----------------|--------|
| `qr.filter.group.none` | es | "Sin agrupar" -> "Ninguno" | "None" |
| `section.past` | de | "Vergangene" -> "Letzte" | "Past" |
| `bc.filter.industry_clear` | de | "Zurücksetzen" -> "Leeren" | "Clear" |
| `customers.transcript.cta_open` | es | "Ocultar formulario" -> "Ocultar form" | "Hide form" |
| `customers.transcript.cta_open` | de | "Formular ausblenden" -> "Form ausblenden" | "Hide form" |
| `customers.transcript.cta_open` | fr | "Masquer le formulaire" -> "Masquer" | "Hide form" |
| `qr.filter.range.all` | es | "Todo el tiempo" -> "Todo" | "All time" |
| `qr.filter.range.all` | de | "Gesamter Zeitraum" -> "Alles" | "All time" |
| `wf.btn.fire_renewal` | fr | "Déclencher un signal de renouvellement" -> "Signal renouvellement" | "Fire renewal signal" |
| `qr.filter.group_by` | de | "Gruppieren nach" -> "Gruppe" | "Group by" |
| `wf.btn.sync` | es | "Sincronizar workflow" -> "Sync workflow" | "Sync workflow" |
| `wf.btn.sync` | de | "Workflow synchronisieren" -> "Sync Workflow" | "Sync workflow" |
| `wf.btn.sync` | fr | "Synchroniser le workflow" -> "Synchroniser" | "Sync workflow" |
| `wf.btn.trigger` | de | "Jetzt auslösen (Wartezeit überspringen)" -> "Jetzt auslösen" | "Trigger now (skip wait)" |
| `wf.btn.trigger` | fr | "Déclencher maintenant (sauter l'attente)" -> "Déclencher" | "Trigger now (skip wait)" |
| `topbar.dashboard` | fr | "Tableau de bord" -> "Dashboard" | "Dashboard" |
| `bc.toggle.mains` | fr | "Concurrents principaux uniquement" -> "Concurrents principaux" | "Main competitors only" |
| `wf.btn.fire` | fr | "Déclencher le transcript de démo" -> "Déclencher transcript" | "Fire demo transcript" |
| `dd.btn.seed` | fr | "Injecter le scénario" -> "Injecter" | "Seed scenario" |
| `ab.tool.clear` | fr | "Effacer la recherche" -> "Effacer" | "Clear search" |
| `ab.tool.section.research` | es | "Investigación" -> "Research" | "Research" (cognate, brand-style) |
| `ab.tool.section.sizing` | es | "Dimensionar" -> "Sizing" | "Sizing" (cognate, brand-style) |
| `ab.tool.section.build` | es | "Construir" -> "Build" | "Build" (cognate, brand-style) |
| `ab.tool.section.sizing` | fr | "Dimensionnement" -> "Sizing" | "Sizing" |
| `ab.tool.section.build` | fr | "Construction" -> "Build" | "Build" |

### Acceptable residual overflow (>150% of EN, but tiny absolute width)

These are all single-word labels where the EN baseline is 4-10 chars; the 160-175% ratio is at most a 4-7 char absolute increase and fits the available chip width without wrapping.

| key | locale | EN | locale text | ratio |
|-----|--------|----|-------------|-------|
| `qr.filter.group.none` | es | None (4) | Ninguno (7) | 175% |
| `section.past` | es | Past (4) | Pasadas (7) | 175% |
| `section.past` | fr | Past (4) | Passées (7) | 175% |
| `fb.btn.send` | fr | Send (4) | Envoyer (7) | 175% |
| `ab.tool.select_all` | es | Select all (10) | Seleccionar todas (17) | 170% |
| `ab.tool.select_all` | fr | Select all (10) | Tout sélectionner (17) | 170% |
| `customers.transcript.cta_open` | de | Hide form (9) | Form ausblenden (15) | 167% |
| `qr.filter.search` | fr | Search (6) | Rechercher (10) | 167% |
| `meeting.btn.download` | de | Download (8) | Herunterladen (13) | 162% |
| `qr.filter.range` | de | Range (5) | Zeitraum (8) | 160% |
| `meeting.btn.print` | es | Print (5) | Imprimir (8) | 160% |
| `meeting.btn.print` | fr | Print (5) | Imprimer (8) | 160% |
| `ab.tool.section.compete` | fr | Compete (7) | Concurrence (11) | 157% |

Long body strings (lede, banner, hint): 0 strings exceed 160% of EN length in any locale (German occasionally hits 140-150% on `dd.lede`, `bc.lede.prefix`, etc., but body copy has flow-wrap room and that is within healthy localization tolerance for German).

## Tone consistency

| locale | required tone | finding | action |
|--------|---------------|---------|--------|
| es     | tú/voseo (informal) | 0 `usted` hits. Existing voseo (investigá, dejá, tipeás) preserved. New onboarding strings use voseo. | OK |
| ja     | です/ます polite | All new strings use polite forms (ください, できます, します). Existing JA keys already polite. | OK |
| de     | Du (informal, consistent) | 7 `Sie/Ihr` hits in original (`tpl.hint`, `dd.lede`, `dd.toast.seeded`, `fb.title.1`, `fb.placeholder`, `fb.empty`, `bc.lede.prefix`). All converted to Du / dein / dir / hast / wähl / frag / setz. New onboarding strings use Du. One residual "Sie" in `onboard.step3.body` is third-person plural ("Spezialisten ... Sie persistieren" = they persist), not formal address. | OK |
| fr     | vous (formal) | 0 informal `tu/ton/tes` hits. Existing vous form preserved. New onboarding strings use vous (Choisissez, Appuyez, Vous pourrez). | OK |

## Terminology consistency

Brand and product names kept literal across all locales:

- "FE Brain", "FE Copilot", "FE Tools", "Battlecards", "Agent Builder", "Quick Research", "Workflow", "Customers", "Kibana", "Elastic", "Splunk", "Datadog" - present unchanged in every locale.
- Tool ids (`fec_*`) are inside HTML / data attributes; not strings, not translated.
- Persona names (Marta, Diego, Priya, etc.) are in `demo-data.js` / `industries.js`, which the brief explicitly excluded from this audit. Not touched.

## Em-dash and en-dash

grep for U+2014 (em-dash) in `frontend/assets/js/i18n.js` -> 0 hits
grep for U+2013 (en-dash) in `frontend/assets/js/i18n.js` -> 0 hits

The repo-wide step 8 of `integration_smoke` reports `dash hits=0` across 223 files (backend + frontend + docs + data).

## Smoke test

```
PYTHONPATH=backend .venv/bin/python -m scripts.integration_smoke
```

Result: 8 PASS, 1 FAIL (step 9 = git uncommitted threshold; this is expected and unrelated to i18n - it counts the in-progress edits to `i18n.js` and the new doc). Steps 1-8 all green, including step 8 dash audit at 0.

## Files touched

- `/Users/rodrigocareaga/Downloads/FE-Elastic/frontend/assets/js/i18n.js` (only this file changed in scope of this batch)
- `/Users/rodrigocareaga/Downloads/FE-Elastic/docs/qa-w26b-i18n.md` (this report)

## Recommendation

Ship. The 134 orphan keys are dead-key cleanup work and can be deferred - they do not break the UI. Future i18n batches should add a CI lint that enforces parity (count match per locale + every used key must exist in EN).
