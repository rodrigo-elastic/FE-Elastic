# Analyze transcript flow

The "Analyze transcript" tab on the FE Copilot dashboard lets any FE drop a
Gong, Zoom, or plain-text transcript and run the full Post-Meeting agent on it
without needing a synthetic meeting fixture in `data/synthetic`.

## Where it lives

- UI: `frontend/index.html`, the section with `id="entry-tr"` (revealed when
  the user clicks the "Analyze transcript" tab in the entry-tabs row).
- Form wiring: `bindTranscriptUpload()` in `frontend/assets/js/app.js`.
- Endpoint: `POST /api/v1/agents/post-meeting/from-transcript` in
  `backend/app/api/routes_agents.py` (request model
  `AdHocPostMeetingRequest`).

The frontend never touches a synthetic meeting id. The backend mints a fresh
ad-hoc meeting id of the form `transcript-<slug>-YYYYMMDD-HHMMSS`, runs the
Post-Meeting agent through `PostMeetingAgent.run_ad_hoc`, persists the result
to `runtime/post_meeting/<meeting_id>.json`, indexes it into Elasticsearch,
and returns the record.

## How to use it

1. Open the dashboard, click the "Analyze transcript" entry tab.
2. Fill in:
   - Company name (required, 1 to 120 chars).
   - Transcript text (required, 20 to 200,000 chars). Either paste or use
     the file picker, which accepts `.vtt`, `.txt`, or `.srt` and auto-loads
     into the textarea. Drag and drop onto the textarea also works.
   - Optional: meeting title, industry, size, notes, source (zoom / gong /
     manual), output language, model override.
3. Click "Analyze transcript". The button enters a busy state, the status
   line announces "Running post-meeting agent (model)..." via aria-live.
4. On success the page redirects to
   `/meeting.html?id=<meeting_id>&post=1&adhoc=1` so the user lands on the
   Post-Meeting tab with the analysis already rendered.
5. On failure a toast surfaces the upstream error and the status line keeps
   the message until the user retries.

## Request shape

```json
POST /api/v1/agents/post-meeting/from-transcript
Content-Type: application/json

{
  "company_name": "Globex",
  "meeting_title": "Discovery call",
  "industry": "Fintech",
  "size": "Mid-market",
  "notes": "Follow-up on observability migration.",
  "transcript_text": "WEBVTT\n\n00:00:01.000 --> 00:00:05.000\nAlice (Customer): We saw a 30% spike in p99 latency last week.\n\n00:00:05.500 --> 00:00:09.000\nBob (Elastic FE): Got it. Walk me through the alerting setup...",
  "transcript_source": "zoom",
  "language": "English",
  "model": ""
}
```

`model` accepts `claude-haiku-4-5`, `claude-sonnet-4-6`,
`claude-opus-4-7`, or empty string for the server default.
`transcript_source` is one of `zoom`, `gong`, or `manual` and is passed
through to the audit record.

## Response shape (relevant fields)

```json
{
  "meeting_id": "transcript-globex-20260503-181203",
  "company_name": "Globex",
  "ad_hoc": true,
  "transcript_source": "zoom",
  "summary": "...",
  "action_items": [ ... ],
  "meddpicc_signals": { ... },
  "competitor_mentions": [ ... ],
  "follow_up_email": { ... },
  "salesforce_writes": { ... }
}
```

The frontend only needs `meeting_id`. Everything else is consumed by the
meeting page on the redirect.

## Validation rules

| Field | Rule |
|-------|------|
| `company_name` | required, 1 to 120 chars |
| `transcript_text` | required, 20 to 200,000 chars |
| `industry` | optional, 0 to 80 chars |
| `size` | optional, 0 to 80 chars |
| `notes` | optional, 0 to 2,000 chars |
| `meeting_title` | optional, 0 to 160 chars |
| `language` | one of English, Spanish, Japanese, German, French |
| `model` | empty or one of the 3 Claude model ids above |

The frontend short-circuits validation before the network call: empty
company name and transcripts shorter than 20 characters never reach the
endpoint.

## Smoke test (without burning Claude credits)

Probe that the endpoint and the static assets are reachable:

```bash
curl -sf -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8123/
curl -sf -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8123/assets/js/app.js
curl -s -X POST http://127.0.0.1:8123/api/v1/agents/post-meeting/from-transcript \
     -H 'Content-Type: application/json' -d '{}'
```

The first two return `200`. The third returns `422` with a JSON body
listing the missing fields, which proves the endpoint is wired and the
Pydantic model is enforced.

## Compliance notes

- Only the fields the FE typed leave the boundary. There is no synthetic
  data lookup on this path.
- The transcript text is part of the Claude prompt and is captured in the
  append-only audit log alongside the other agent calls.
- The ad-hoc record is written to `runtime/post_meeting/` and indexed into
  Elasticsearch the same way regular post-meeting runs are.

## i18n keys added

All keys live under `tr.*` in `frontend/assets/js/i18n.js`. The full set is:

- `tr.title`, `tr.subtitle`, `tr.hint`
- `tr.field.company`, `tr.field.title`, `tr.field.source`,
  `tr.field.industry`, `tr.field.size`, `tr.field.notes`,
  `tr.field.text`, `tr.field.file`, `tr.field.model`
- `tr.placeholder.company`, `tr.placeholder.title`,
  `tr.placeholder.industry`, `tr.placeholder.size`,
  `tr.placeholder.notes`, `tr.placeholder.text`
- `tr.source.zoom`, `tr.source.gong`, `tr.source.manual`
- `tr.submit`, `tr.status`

EN strings are canonical; ES, JA, DE, and FR carry working translations
that you can refine if the wording drifts.
