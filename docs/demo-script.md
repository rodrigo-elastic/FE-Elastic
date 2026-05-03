# FE Copilot Demo Script (3 minutes)

> All data is synthetic. Three companies (Acme, Globex, Initech) with hand-curated news, transcripts, and tickets.

## 0. Setup (already running)

```bash
PYTHONPATH=backend uvicorn app.main:app --port 8000
```

Open http://localhost:8000 in a browser. Acme is the headline narrative; Globex is the enterprise/Splunk variant; Initech is the existing-customer expansion play.

## 1. Pre-Meeting Researcher (~60s)

1. On the dashboard, find the upcoming meeting **"Acme x Elastic, observability consolidation"**.
2. Click **Run Pre-Meeting Agent**.
3. The browser jumps to the meeting page with the brief loaded:
   - Headline frames the August 15 Datadog renewal as the forcing function.
   - Sections cover Why now, Recent signals, Pain points, Discovery questions, Talking points (vs Datadog), and Risks.
4. Click **Download artifact** to show the PDF (or HTML fallback) brief.
5. Open `runtime/slack.log` in a terminal: the Slack mock recorded the post to `#fe-copilot-briefs`.

Talking point: "On the real account, this is a hosted Elastic Agent Builder workflow that fires 1 hour before the calendar event. The FE walks into the meeting with this on their phone."

## 2. Live Meeting Companion (~45s)

1. Switch to the **Live Companion** tab.
2. Click **Replay transcript with alerts**.
3. The transcript replays turn by turn; competitor mentions (Datadog, Grafana) and MEDDPICC signals surface as colored alert rows under the relevant turn, with a suggested whisper line.
4. Highlight that this runs on Haiku 4.5 per turn so the latency stays under a second.

## 3. Post-Meeting Action Engine (~60s)

1. Switch to the **Post-Meeting** tab.
2. Click **Run Post-Meeting Agent**.
3. The page renders:
   - **Summary** (3 to 4 sentences).
   - **Action items** with owner, due date, description, and a verbatim source quote.
   - **MEDDPICC signals** in a 2-column grid, one card per category.
   - **Competitor mentions**.
   - **Follow-up email draft** in a monospace block, ready to copy into Gmail.
4. Show `runtime/salesforce.log`: each action item became a Salesforce mock task with a UUID.
5. Show `runtime/emails/acme-mtg-prev-001.json`: the email is persisted as a draft.

Talking point: "Every action item is grounded in a verbatim transcript quote. The downstream Salesforce push is automatic, but every claim is auditable back to the call."

## 4. Wrap (~15s)

- Three discrete agents, chained, modeled in the demo as Elastic Agent Builder workflows.
- Opus 4.7 with adaptive thinking and `effort: "high"` for the two heavy reasoning agents; Haiku 4.5 for the live whisper.
- Synthetic data only; no customer data ever touched the system.

## Reset between runs

```bash
rm -rf runtime/briefs runtime/post_meeting runtime/emails runtime/slack.log runtime/salesforce.log
```
