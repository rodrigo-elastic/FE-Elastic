# Workflow 2: Orphan high-impact action items

This is the second Kibana alerting + webhook workflow shipped by FE Copilot.
It closes the loop after Workflow 1: when the post-meeting agent indexes a
record into `fec-post-meetings`, this rule reacts and auto-creates a
Salesforce mock Task for any high-impact action item that has no owner email.

## Why it matters

Workflow 1 (`fec-transcript-inbox` -> post-meeting agent) already proves the
"agent triggered by workflow" direction. Workflow 2 proves the inverse: the
agent's output is itself a workflow trigger. Together they form a closed loop:

> doc -> workflow 1 -> agent -> agent output doc -> workflow 2 -> SFDC task

That bi-directional coupling is the strongest demonstration of the
"Use of Workflows + Agent Builder" judging criterion.

## Identifiers

After running `POST /api/v1/workflows/sync`:

- Rule name: `FE Copilot - Orphan Action Item Workflow`
- Rule type: `.es-query`
- Connector name: `FE Copilot Orphan Action Webhook`
- Connector type: `.webhook`
- Watched index: `fec-post-meetings`
- Time field: `generated_at`
- Webhook target: `<ngrok>/api/v1/workflows/post-meeting-action-orphan`

The concrete `rule_id` and `connector_id` are recorded in
`runtime/workflow_state.json` under the keys `orphan_rule_id` and
`orphan_connector_id`. The `/api/v1/workflows/status` endpoint reports both
workflows side by side under the `workflows` object.

## Trigger condition

The rule fires every minute via `.es-query` against `fec-post-meetings` over
the last `1m` time window using `excludeHitsFromPreviousRun: true`. Threshold
is `> 0` matched documents.

### Filter strategy and fallback

`action_items` is a `nested` field. Expressing
`action_items.impact:"high" AND action_items.owner_email:null` correctly
inside a `.es-query` rule's flat JSON body is brittle (Kibana resolves the
filter as a top-level Lucene query, not a `nested` query).

We therefore use the documented fallback:

1. The rule fires on every new post-meeting doc with `match_all` over the
   last minute.
2. The backend webhook handler at
   `POST /api/v1/workflows/post-meeting-action-orphan` re-reads the recent
   documents, applies the orphan predicate
   (`impact == "high" AND (owner_email is null OR empty)`), de-duplicates
   against `runtime/sfdc_auto_tasks.jsonl`, and creates SFDC tasks only for
   genuine orphans.

This makes the rule a coarse trigger and the backend the source of truth for
orphan semantics. Behavior is identical to a server-side filter would have
been; only the cost of the filter moves from Kibana to the backend.

## Webhook handler

`POST /api/v1/workflows/post-meeting-action-orphan`

1. Read recent docs from `fec-post-meetings` (Elasticsearch first, disk
   fallback under `runtime/post_meeting/*.json`).
2. For each doc, find action items where
   `impact == "high"` and `owner_email` is null or empty.
3. De-duplicate against existing entries in
   `runtime/sfdc_auto_tasks.jsonl` keyed on `(meeting_id, action_title)`.
4. For each new orphan, call `salesforce_mock.create_task(...)` assigned to
   the meeting account's `OwnerName`. Subject is prefixed with `[Auto]`.
5. Append one record per task to `runtime/sfdc_auto_tasks.jsonl`.
6. Append a fire event to `runtime/workflow_fires_orphan.jsonl`.
7. Return `{ok: true, tasks_created: N, tasks: [...]}`.

The handler reuses the existing `app.integrations.salesforce_mock` module; it
does not introduce a parallel Salesforce path.

## End-to-end flow diagram

```
                 +---------------------------+
   user posts -> | POST /api/v1/transcripts  |
                 +-------------+-------------+
                               |
                               v
                  index doc into fec-transcript-inbox
                               |
                               v   (every 60s)
                 +---------------------------+
                 | Kibana .es-query rule #1  |
                 | "FE Copilot - Post-      |
                 |  Meeting Workflow"        |
                 +-------------+-------------+
                               |  webhook
                               v
                 +---------------------------+
                 | POST /workflows/triggered |
                 | runs PostMeetingAgent     |
                 | writes fec-post-meetings  |
                 | + Slack + Salesforce      |
                 +-------------+-------------+
                               |
                               v
                 indexed doc in fec-post-meetings
                               |
                               v   (every 60s)
                 +---------------------------+
                 | Kibana .es-query rule #2  |
                 | "FE Copilot - Orphan     |
                 |  Action Item Workflow"    |
                 +-------------+-------------+
                               |  webhook
                               v
       +-----------------------------------------------+
       | POST /workflows/post-meeting-action-orphan    |
       | filter high-impact + owner_email null         |
       | salesforce_mock.create_task per orphan        |
       | append runtime/sfdc_auto_tasks.jsonl          |
       +-----------------------------------------------+
                               |
                               v
              SFDC mock task assigned to account owner
```

## Manual test

Prerequisites:

- Backend on `http://127.0.0.1:8123` with the Kibana keys loaded from `.env`.
- ngrok URL recorded in `runtime/last_ngrok_url`.

Steps:

```bash
# 1. Register both rules + connectors.
curl -sS -X POST http://127.0.0.1:8123/api/v1/workflows/sync | jq

# 2. Confirm both workflows show registered.
curl -sS http://127.0.0.1:8123/api/v1/workflows/status | jq '.workflows'

# 3. Index a synthetic post-meeting doc with one orphan high-impact action item.
curl -sS -X POST http://127.0.0.1:8123/api/v1/workflows/orphan-demo-fire | jq

# 4. Wait 60 to 90 seconds for the Kibana rule to poll, then check fires.
curl -sS http://127.0.0.1:8123/api/v1/workflows/recent-fires | jq '.orphan_action_fires[0]'

# 5. Verify the auto-created SFDC task.
curl -sS http://127.0.0.1:8123/api/v1/workflows/sfdc-auto-tasks | jq '.tasks[0]'
ls -la runtime/sfdc_auto_tasks.jsonl
```

Expected end state:

- `workflow_state.json` contains both `rule_id` + `connector_id` and
  `orphan_rule_id` + `orphan_connector_id`.
- `runtime/workflow_fires_orphan.jsonl` contains a record with
  `processed: true`, `matched_orphans >= 1`, `tasks_created >= 1`.
- `runtime/sfdc_auto_tasks.jsonl` contains a record with `task_id` starting
  with `00T` and `account_owner: "Field Engineering"`.
- `runtime/salesforce.log` contains a matching SFDC Task record (the same
  log used by the agent's Salesforce writes).

## Direct webhook smoke test

To test the handler without waiting for Kibana:

```bash
curl -sS -X POST \
  http://127.0.0.1:8123/api/v1/workflows/post-meeting-action-orphan \
  -H 'Content-Type: application/json' \
  -d '{"alert_id":"smoke","rule_id":"smoke","rule_name":"smoke"}' | jq
```

The endpoint scans the most recent post-meeting docs on disk or in
Elasticsearch and creates tasks for any orphan high-impact items it has not
already auto-tasked.

## Demo talk track (5 minute video)

> "Here is the part that makes this submission a workflow story, not a chat
> demo. We have two Kibana alerting rules wired into the same backend.
>
> The first rule watches `fec-transcript-inbox`. When a transcript lands,
> the rule fires a webhook that runs the post-meeting agent. The agent
> indexes its output into `fec-post-meetings`, and that index write is the
> input for the second rule.
>
> The second rule, `FE Copilot - Orphan Action Item Workflow`, watches
> `fec-post-meetings`. The moment the agent writes a new record, the rule
> fires our orphan webhook. The webhook scans the action items, finds every
> high-impact item that has no owner email, and creates a Salesforce task
> assigned to the account owner so nothing falls through the cracks.
>
> So the loop is: doc triggers workflow, workflow triggers agent, agent
> output triggers another workflow, which writes back to Salesforce. The
> rep does nothing; Elastic and Salesforce stay aligned by themselves."

## Em / en dash audit

This document was reviewed for em dashes (U+2014) and en dashes (U+2013).
None are present. Replacements use plain hyphens or the word "to".
