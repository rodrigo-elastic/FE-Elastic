# QA W24D - Broken-link Crawler (depth 2)

- Generated: 2026-05-05T08:10:17Z
- Backend base: http://localhost:8123
- Seed: /index.html
- Max depth: 2
- Runtime: 0.26 s

## Summary

| Metric | Count |
| --- | ---: |
| URLs crawled | 55 |
| OK | 55 |
| 4xx | 0 |
| 5xx | 0 |
| Missing anchors | 0 |
| JS dynamic destinations | 6 (bad: 0) |
| i18n keys checked | 257 (bad: 0) |
| em-dash hits in repo | 0 |

## Failures

None. All links, anchors, dynamic destinations, and i18n keys resolve.
## All Crawled URLs

| Depth | Source page | Line | URL | Status | Anchor | Anchor OK |
| ---: | --- | ---: | --- | ---: | --- | --- |
| 0 | (seed) | 0 | /index.html | 200 | - | - |
| 1 | /index.html | 67 | / | 200 | - | - |
| 1 | /index.html | 115 | /health.html | 200 | - | - |
| 1 | /index.html | 147 | /quick-research.html | 200 | - | - |
| 1 | /index.html | 154 | /customers.html | 200 | - | - |
| 1 | /index.html | 161 | /fe-brain.html | 200 | - | - |
| 1 | /index.html | 168 | /agent-builder.html | 200 | - | - |
| 1 | /index.html | 175 | /battlecards.html | 200 | - | - |
| 1 | /index.html | 182 | /industries.html | 200 | - | - |
| 1 | /index.html | 189 | /demo-data.html | 200 | - | - |
| 1 | /index.html | 196 | /tools.html | 200 | - | - |
| 1 | /index.html | 212 | /tools.html#tool-poc | 200 | tool-poc | yes |
| 1 | /index.html | 213 | /tools.html#tool-spl | 200 | tool-spl | yes |
| 1 | /index.html | 214 | /tools.html#tool-compliance | 200 | tool-compliance | yes |
| 1 | /index.html | 215 | /tools.html#tool-stack | 200 | tool-stack | yes |
| 1 | /index.html | 216 | /tools.html#tool-code | 200 | tool-code | yes |
| 1 | /index.html | 217 | /tools.html#tool-cost | 200 | tool-cost | yes |
| 1 | /index.html | 218 | /tools.html#tool-capacity | 200 | tool-capacity | yes |
| 1 | /index.html | 219 | /tools.html#tool-knowledge | 200 | tool-knowledge | yes |
| 1 | /index.html | 220 | /tools.html#tool-troubleshoot | 200 | tool-troubleshoot | yes |
| 1 | /index.html | 221 | /tools.html#tool-compare | 200 | tool-compare | yes |
| 1 | /index.html | 222 | /tools.html#tool-orchestrator | 200 | tool-orchestrator | yes |
| 1 | /index.html | 223 | /tools.html#tool-proposal | 200 | tool-proposal | yes |
| 1 | /index.html | 229 | /workflow-demo.html | 200 | - | - |
| 1 | /index.html | 231 | /audit.html | 200 | - | - |
| 1 | /index.html | 245 | /api/v1/audit | 200 | - | - |
| 1 | /index.html | 276 | /docs-md/compliance.md | 200 | - | - |
| 2 | / | 67 | / | 200 | - | - |
| 2 | / | 115 | /health.html | 200 | - | - |
| 2 | / | 147 | /quick-research.html | 200 | - | - |
| 2 | / | 154 | /customers.html | 200 | - | - |
| 2 | / | 161 | /fe-brain.html | 200 | - | - |
| 2 | / | 168 | /agent-builder.html | 200 | - | - |
| 2 | / | 175 | /battlecards.html | 200 | - | - |
| 2 | / | 182 | /industries.html | 200 | - | - |
| 2 | / | 189 | /demo-data.html | 200 | - | - |
| 2 | / | 196 | /tools.html | 200 | - | - |
| 2 | / | 212 | /tools.html#tool-poc | 200 | tool-poc | yes |
| 2 | / | 213 | /tools.html#tool-spl | 200 | tool-spl | yes |
| 2 | / | 214 | /tools.html#tool-compliance | 200 | tool-compliance | yes |
| 2 | / | 215 | /tools.html#tool-stack | 200 | tool-stack | yes |
| 2 | / | 216 | /tools.html#tool-code | 200 | tool-code | yes |
| 2 | / | 217 | /tools.html#tool-cost | 200 | tool-cost | yes |
| 2 | / | 218 | /tools.html#tool-capacity | 200 | tool-capacity | yes |
| 2 | / | 219 | /tools.html#tool-knowledge | 200 | tool-knowledge | yes |
| 2 | / | 220 | /tools.html#tool-troubleshoot | 200 | tool-troubleshoot | yes |
| 2 | / | 221 | /tools.html#tool-compare | 200 | tool-compare | yes |
| 2 | / | 222 | /tools.html#tool-orchestrator | 200 | tool-orchestrator | yes |
| 2 | / | 223 | /tools.html#tool-proposal | 200 | tool-proposal | yes |
| 2 | / | 229 | /workflow-demo.html | 200 | - | - |
| 2 | / | 231 | /audit.html | 200 | - | - |
| 2 | / | 245 | /api/v1/audit | 200 | - | - |
| 2 | / | 276 | /docs-md/compliance.md | 200 | - | - |
| 2 | /tools.html | 405 | /api/v1/tools/knowledge-search/health | 200 | - | - |
| 2 | /tools.html | 443 | /meeting.html?id=atlantico-mtg-prev-001 | 200 | - | - |

## JS Dynamic Destinations

| File | Line | Raw | Resolved | Status | OK |
| --- | ---: | --- | --- | ---: | --- |
| frontend/assets/js/app.js | 150 | `/meeting.html?id=${encodeURIComponent(result.meeting_id)}&adhoc=1` | /meeting.html?id=test-001&adhoc=1 | 200 | yes |
| frontend/assets/js/app.js | 307 | `/meeting.html?id=${encodeURIComponent(mid)}&post=1&adhoc=1` | /meeting.html?id=test-001&post=1&adhoc=1 | 200 | yes |
| frontend/assets/js/app.js | 757 | `/meeting.html?id=${encodeURIComponent(m.id)}&brief=1` | /meeting.html?id=test-001&brief=1 | 200 | yes |
| frontend/assets/js/app.js | 783 | `/meeting.html?id=${encodeURIComponent(m.id)}&post=1` | /meeting.html?id=test-001&post=1 | 200 | yes |
| frontend/assets/js/meeting.js | 961 | `/meeting.html?id=${encodeURIComponent(t.meeting_id)}` | /meeting.html?id=test-001 | 200 | yes |
| frontend/assets/js/quick-research-filter.js | 527 | `/meeting.html?id=` | /meeting.html?id= | 200 | yes |

## i18n Keys

Checked 257 `data-i18n` keys across frontend HTML pages. Bad: 0.

## Raw JSON

```json
{
  "summary": {
    "crawled": 55,
    "ok": 55,
    "fail_4xx": 0,
    "fail_5xx": 0,
    "missing_anchor": 0,
    "js_total": 6,
    "js_bad": 0,
    "i18n_total": 257,
    "i18n_bad": 0,
    "em_dash_total": 0
  },
  "runtime_s": 0.25651762494817376
}
```

