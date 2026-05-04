# Demo Freshness Cron

## Why this exists

The five demo scenarios (`black-friday-outage`, `credential-stuffing`,
`noisy-microservice`, `gdpr-audit-timeline`, `supply-chain-attack`) bake their
event timestamps at the moment they are seeded. Kibana's default time picker
windows are relative to `now` (last 24h, last 7d). Once the data falls behind
those windows, the dashboards render blank by default and the demo loses its
punch.

To keep the demo evergreen with zero manual effort, this cron job re-seeds all
five scenarios once a day. A fresh seed pushes the most recent events to a few
seconds ago, so every dashboard works under the default time picker.

## What runs

`runtime/cron/freshness.sh` does, in order:

1. `cd` to the repo root.
2. Source `.env` using the same loader as `runtime/overnight/batches/_lib.sh`.
3. `GET /api/v1/health`. If the backend is not up, log a SKIP and exit 0.
   The script never tries to start the backend itself.
4. `POST /api/v1/demo-data/<scenario>/seed` for each of the five scenarios in
   sequence, logging the HTTP code and the doc counts.
5. Append everything to `runtime/cron/freshness-YYYY-MM-DD.log`.
6. Delete `freshness-*.log` files older than 30 days.
7. Exit 0 on full success, exit 1 if any scenario failed (the others still
   ran).

The script is safe to run twice in a row. A single scenario failure does not
abort the others.

## Manual run

```bash
bash /Users/rodrigocareaga/Downloads/FE-Elastic/runtime/cron/freshness.sh
```

Tail the log:

```bash
tail -f /Users/rodrigocareaga/Downloads/FE-Elastic/runtime/cron/freshness-$(date +%F).log
```

## Dry run

Prints what it would seed without making any POSTs:

```bash
FRESHNESS_DRY_RUN=1 bash runtime/cron/freshness.sh
```

`FRESHNESS_VERBOSE=1` mirrors log lines to stdout when running non-interactively.

## Install on macOS (launchd)

```bash
cp runtime/cron/com.fecopilot.freshness.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.fecopilot.freshness.plist
```

The job runs every day at **06:00 local**. `RunAtLoad` is `false` on purpose:
loading the plist will NOT trigger an immediate seed.

Verify it is registered:

```bash
launchctl list | grep com.fecopilot.freshness
```

Force a one-off run (matches what cron will do at 06:00):

```bash
launchctl start com.fecopilot.freshness
```

stdout and stderr land in `runtime/cron/freshness.stdout` and
`runtime/cron/freshness.stderr` respectively. The structured per-day log is
`runtime/cron/freshness-YYYY-MM-DD.log`.

### Disable

```bash
launchctl unload -w ~/Library/LaunchAgents/com.fecopilot.freshness.plist
```

### Update the plist after editing

```bash
launchctl unload -w ~/Library/LaunchAgents/com.fecopilot.freshness.plist
cp runtime/cron/com.fecopilot.freshness.plist ~/Library/LaunchAgents/
launchctl load -w ~/Library/LaunchAgents/com.fecopilot.freshness.plist
```

## Linux / cron alternative

For non-mac hosts, drop this in your crontab (`crontab -e`):

```
0 6 * * * bash /Users/rodrigocareaga/Downloads/FE-Elastic/runtime/cron/freshness.sh >> /tmp/freshness.log 2>&1
```

## Caveats

* Each scenario takes roughly 20 to 30 seconds to seed; a full pass is around
  2 minutes. Do not schedule the job during the demo window.
* The script will SKIP cleanly if the backend is unreachable. It will not try
  to bring the backend up.
* The script does not delete pre-existing indices; the scenario `seed()`
  functions handle their own re-indexing semantics.
* Logs older than 30 days are removed automatically.
* If you change `APP_PORT` in `.env`, the script picks it up on the next run.
