# FE Copilot Demo Supervisor

A single bash loop that keeps the FE Copilot backend and ngrok tunnel alive during a demo, and re-syncs the Kibana Agent Builder connector whenever ngrok rotates the public URL.

## What it does

Every `POLL_INTERVAL` seconds (default 30) the supervisor:

1. Probes `http://127.0.0.1:8123/api/v1/health`. If it is not 200, it relaunches uvicorn under `nohup` and records the new PID in `runtime/backend.pid`.
2. Probes the ngrok local API at `http://127.0.0.1:4040/api/tunnels`. If ngrok is not running or has no tunnel, it starts `ngrok http 8123 --log=stdout` (logs to `runtime/ngrok.log`).
3. Compares the current public URL against `runtime/last_ngrok_url`. If it changed, it writes the new value and runs `BACKEND_BASE_URL=<new> PYTHONPATH=backend ./.venv/bin/python -m scripts.sync_agent_builder` to re-register the Kibana connector and tools.
4. Appends a heartbeat line to `runtime/supervisor.log`.

The supervisor is a singleton. It refuses to start if `runtime/supervisor.pid` exists and the named PID is alive.

## Files

| Path | Purpose |
| --- | --- |
| `runtime/supervisor.sh` | The loop itself. |
| `runtime/supervisor_stop.sh` | Clean stop (and optional full teardown). |
| `runtime/supervisor.pid` | PID of the running supervisor. |
| `runtime/supervisor.log` | ISO-8601 prefixed log with heartbeats and events. |
| `runtime/backend.pid` | PID of uvicorn (only when the supervisor started it). |
| `runtime/ngrok.pid` | PID of ngrok (only when the supervisor started it). |
| `runtime/backend.log` | uvicorn stdout/stderr. |
| `runtime/ngrok.log` | ngrok stdout/stderr. |
| `runtime/last_ngrok_url` | The most recent public URL pushed to Kibana. |
| `runtime/supervisor_sync.log` | Output of every `sync_agent_builder` invocation. |

## How to start

```bash
cd /Users/rodrigocareaga/Downloads/FE-Elastic
nohup bash runtime/supervisor.sh > /dev/null 2>&1 & disown
```

Override the poll interval:

```bash
POLL_INTERVAL=15 nohup bash runtime/supervisor.sh > /dev/null 2>&1 & disown
```

## How to monitor

```bash
tail -f runtime/supervisor.log
```

You should see one heartbeat line per iteration, e.g.:

```
2026-05-03T17:01:00Z [supervisor] heartbeat backend=ok ngrok=ok url='https://abcd.ngrok-free.dev' fail_streak=0
```

## How to stop

Stop just the supervisor (backend and ngrok keep running, ideal mid-demo):

```bash
bash runtime/supervisor_stop.sh
```

Stop everything (supervisor, uvicorn, ngrok):

```bash
bash runtime/supervisor_stop.sh --full
```

## Troubleshooting

### "supervisor already running" but it is not

The PID file may be stale if the box was force-rebooted while the loop was running. The supervisor itself will reclaim a stale PID file automatically on next start, but if you want to clear it by hand:

```bash
rm runtime/supervisor.pid
```

### ngrok auth failures

ngrok free tier requires a one-time authtoken. If `runtime/ngrok.log` shows `ERR_NGROK_4018` or `authentication failed`, run once:

```bash
ngrok config add-authtoken <YOUR_TOKEN>
```

then restart the supervisor. The supervisor itself does not handle auth; it only restarts ngrok.

### Kibana 401 / 403 from sync_agent_builder

If `runtime/supervisor_sync.log` shows 401 or 403 from `/api/agent_builder/*`, the `KIBANA_API_KEY` in `.env` has expired or lacks the Agent Builder privileges. Mint a new key in Kibana and update `.env`. The supervisor does not edit `.env`; you must restart it (or it will keep retrying with the bad key on every URL rotation). To rerun the sync manually after fixing the key:

```bash
URL=$(cat runtime/last_ngrok_url)
BACKEND_BASE_URL="$URL" PYTHONPATH=backend ./.venv/bin/python -m scripts.sync_agent_builder
```

### Backend keeps failing to bind

If uvicorn fails to come up healthy 5 times in a row the supervisor logs a loud error and pauses for 5 minutes (`BACKEND_BACKOFF_SECONDS`) before retrying. Most common causes:

- Port 8123 already taken: `lsof -i :8123` to find the offender.
- Broken venv: recreate with `python3 -m venv .venv && .venv/bin/pip install -r backend/requirements.txt`.
- Import error in `backend/app/main.py`: tail `runtime/backend.log` for the traceback.

### Sync fails after a network blip

ngrok URL rotations are written to `runtime/last_ngrok_url` immediately, so a transient sync failure will not retry on its own. Re-run manually:

```bash
URL=$(cat runtime/last_ngrok_url)
BACKEND_BASE_URL="$URL" PYTHONPATH=backend ./.venv/bin/python -m scripts.sync_agent_builder
```

## Caveats

- ngrok free tier rotates the public URL on every restart. The supervisor handles this by re-running the Kibana sync whenever it sees a new URL.
- The supervisor leaves backend and ngrok alive on `Ctrl+C` or `SIGTERM` by design, so you can swap supervisors without dropping the demo. Use `supervisor_stop.sh --full` to actually take everything down.
- The supervisor does not rotate `runtime/supervisor.log`. For multi-day demos, prune it manually or wrap it in `logrotate`.
