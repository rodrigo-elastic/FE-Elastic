# QA W26C - SEO and social meta audit

Author: Rodrigo Careaga
Date: 2026-05-04
Scope: Overnight Batch 4, Eje C. Add SEO, OpenGraph, and Twitter card
metadata to every public HTML page in `/frontend`. Ship a sitemap, a
robots file, and a web app manifest. Validate end to end with curl + grep.

## Summary

- 13 public HTML pages audited and patched.
- 3 new files created: `sitemap.xml`, `robots.txt`, `manifest.webmanifest`.
- Zero em or en dashes anywhere in the deliverables.
- Integration smoke: 8 of 9 PASS. The one FAIL (`git status`) is the
  expected uncommitted-work tripwire and is unrelated to this batch.

## What was added per page

Every page now exposes a `<!-- seo:meta:start --> ... <!-- seo:meta:end -->`
block immediately after `<title>`. The block always contains:

1. `<meta name="description">` (140 to 160 characters per page).
2. `<link rel="canonical">` pointing at the absolute path under the host.
3. `<meta name="theme-color" content="#0077CC">` (Lochmara).
4. `<meta name="author" content="Rodrigo Careaga">`.
5. `<meta name="application-name" content="FE Copilot">`.
6. OpenGraph: `og:type=website`, `og:title`, `og:description`,
   `og:image=/assets/img/elastic/glyph-cluster-color.svg`, `og:url`,
   `og:site_name=FE Copilot`.
7. Twitter card: `twitter:card=summary_large_image`, `twitter:title`,
   `twitter:description`, `twitter:image`.
8. `<link rel="manifest" href="/manifest.webmanifest">`.

Note on the OG image: the spec called for `assets/hero-dashboard.png`,
which does not exist in the repo. To avoid shipping a broken social
preview, the OG image points at the existing Elastic glyph SVG
(`/assets/img/elastic/glyph-cluster-color.svg`), which renders cleanly
in social card scrapers that accept SVG and degrades to a 200 OK link
otherwise. Swap to a real `hero-dashboard.png` when available by
replacing the path in the meta block.

## Per-page meta presence table

Validated by `curl http://127.0.0.1:8123/<page>.html | grep -c <pattern>`.
A `1` means present, `0` means missing.

| Page                  | desc | og:title | og:desc | og:image | og:url | tw:card | tw:title | canonical | theme | author | app-name | manifest |
|-----------------------|:----:|:--------:|:-------:|:--------:|:------:|:-------:|:--------:|:---------:|:-----:|:------:|:--------:|:--------:|
| /index.html           |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /agent-builder.html   |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /audit.html           |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /battlecards.html     |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /customers.html       |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /demo-data.html       |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /fe-brain.html        |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /health.html          |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /industries.html      |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /meeting.html         |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /quick-research.html  |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /tools.html           |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |
| /workflow-demo.html   |  1   |    1     |    1    |    1     |   1    |    1    |    1     |     1     |   1   |   1    |    1     |    1     |

## Per-page titles and descriptions

| Page                  | Title                            | Description (chars) |
|-----------------------|----------------------------------|---------------------|
| /index.html           | FE Copilot - Dashboard           | 141                 |
| /agent-builder.html   | FE Copilot - Agent Builder       | 154                 |
| /audit.html           | FE Copilot - Self Observability  | 148                 |
| /battlecards.html     | FE Copilot - Battlecards         | 158                 |
| /customers.html       | FE Copilot - Customers           | 150                 |
| /demo-data.html       | FE Copilot - Demo Data           | 143                 |
| /fe-brain.html        | FE Copilot - FE Brain            | 152                 |
| /health.html          | FE Copilot - System Health       | 154                 |
| /industries.html      | FE Copilot - Industries          | 152                 |
| /meeting.html         | FE Copilot - Meeting             | 155                 |
| /quick-research.html  | FE Copilot - Quick Research      | 148                 |
| /tools.html           | FE Copilot - Tools               | 149                 |
| /workflow-demo.html   | FE Copilot - Workflow demo       | 148                 |

All descriptions land in the 140 to 160 character window.

## New files

### /frontend/sitemap.xml

Lists all 13 public HTML pages with `<lastmod>2026-05-04</lastmod>` and
priority weights. Served at `http://localhost:8123/sitemap.xml`.

### /frontend/robots.txt

Allows everything under `/`, points crawlers at `/sitemap.xml`. This is
a hackathon submission, not a sensitive site, so the policy is open.

### /frontend/manifest.webmanifest

PWA manifest with `name=FE Copilot`, `theme_color=#0077CC`,
`background_color=#ffffff`, `display=standalone`, and three icon
entries pointing at the existing Elastic SVG glyph and horizontal logo.

## Validation: curl + grep

```bash
$ curl -s http://127.0.0.1:8123/customers.html | grep -E 'name="description"|og:title|twitter:card'
  <meta name="description" content="FE Copilot customers and records browser. Filter and group every meeting, brief, post meeting summary and transcript across all accounts in one place." />
  <meta property="og:title" content="FE Copilot - Customers" />
  <meta name="twitter:card" content="summary_large_image" />
```

Static asset reachability:

```bash
$ curl -s -o /dev/null -w "sitemap:%{http_code}\n"  http://127.0.0.1:8123/sitemap.xml
sitemap:200
$ curl -s -o /dev/null -w "robots:%{http_code}\n"   http://127.0.0.1:8123/robots.txt
robots:200
$ curl -s -o /dev/null -w "manifest:%{http_code}\n" http://127.0.0.1:8123/manifest.webmanifest
manifest:200
```

Coverage sweep across all 13 pages (12 of 12 patterns present per page):

```text
index                desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
agent-builder        desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
audit                desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
battlecards          desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
customers            desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
demo-data            desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
fe-brain             desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
health               desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
industries           desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
meeting              desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
quick-research       desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
tools                desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
workflow-demo        desc=1 ogT=1 ogD=1 ogI=1 ogU=1 twC=1 twT=1 can=1 thm=1 aut=1 app=1 man=1
```

## Em-dash and en-dash audit

Project-wide grep for em (U+2014) or en (U+2013) dashes in the touched
files:

```bash
$ grep -nP "\x{2014}|\x{2013}" frontend/*.html frontend/sitemap.xml \
    frontend/robots.txt frontend/manifest.webmanifest
(no output)
```

Smoke step 8 confirms the same across the whole repo: `scanned=221
files, dash hits=0`.

## Smoke verdict

```
[PASS] step 7: Frontend pages reachable
[PASS] step 8: Em/en dash audit (backend + frontend + docs + data)  --  dash hits=0
VERDICT: CAUTION  --  passed=8, failed=1
```

The one FAIL (`step 9: Git status`) is the standard uncommitted-work
guardrail and is unrelated to SEO. All other steps green. Functional GO.

## Notes for next batch

- When a real `hero-dashboard.png` lands, swap the OG image path in
  every page's `<!-- seo:meta:start -->` block. One sed call covers it.
- Consider adding `<link rel="alternate" hreflang>` once i18n routes
  exist on disk; today the pages share a single language toggle.
- The canonical paths are intentionally root-relative since the app is
  not yet deployed to a stable hostname. Promote to absolute URLs when
  a production domain is chosen.
