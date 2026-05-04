# FE Copilot - Fly.io Deployment Guide

This is the operational runbook for hosting the FE Copilot backend (and the
static frontend it serves) on Fly.io. It replaces the ngrok tunnel that the
hackathon demo currently relies on, so the Kibana Agent Builder connector and
the standalone webapp can hit a stable HTTPS URL.

Target shape:

- Region: `mia` (Miami), closest Fly POP to the demo Elastic Cloud cluster in `us-west-1`.
- VM: `shared-cpu-1x`, 256 MB RAM, free tier, auto-stop on idle.
- Public URL after first deploy: `https://fe-copilot.fly.dev` (or
  `https://fe-copilot-rcareaga.fly.dev` if the short name is taken).

Files involved:

- `Dockerfile` - multi-stage Python 3.13 image, weasyprint runtime libs, non-root `feuser`.
- `.dockerignore` - keeps `.venv`, `runtime/`, `docs/screenshots/`, `docs/gifs/` out of the build context.
- `fly.toml` - app name, region, http service, healthcheck, 1 GB persistent volume at `/app/runtime`.

---

## 1. Prerequisites

1. Install the Fly CLI.

   ```bash
   # macOS
   brew install flyctl

   # or vendor-neutral installer
   curl -L https://fly.io/install.sh | sh
   ```

2. Authenticate. This opens a browser tab the first time.

   ```bash
   fly auth login
   ```

3. Confirm Docker Desktop is running locally. Fly can build remotely (`fly deploy --remote-only`),
   but a local build is faster for the first round-trip and matches the CI image bit-for-bit.

   ```bash
   docker version
   ```

4. Have these values ready before step 3 of the first-time deploy:

   - `ANTHROPIC_API_KEY`
   - `ELASTICSEARCH_URL` (full https URL, including `:443` if non-default)
   - `ELASTICSEARCH_API_KEY` (base64 `id:api_key` form, NOT the encoded id alone)
   - `KIBANA_URL`
   - `KIBANA_API_KEY` (only required for `/api/agent_builder/*`; leave unset to run in dry-run mode)

---

## 2. First-time deploy

Run from the repo root: `/Users/rodrigocareaga/Downloads/FE-Elastic`.

### 2a. Initialise the Fly app without deploying

```bash
fly launch --no-deploy --copy-config --name fe-copilot --region mia
```

`--copy-config` tells Fly to honour the existing `fly.toml` instead of regenerating it. If the
launcher complains that `fe-copilot` is already taken, re-run with:

```bash
fly launch --no-deploy --copy-config --name fe-copilot-rcareaga --region mia
```

and update the `app =` line in `fly.toml` to match.

### 2b. Provision the persistent volume referenced by `fly.toml`

```bash
fly volumes create fe_copilot_runtime --region mia --size 1
```

Skip if `fly launch` already created it (it usually does when it detects the `[[mounts]]` block).
You can verify with `fly volumes list`.

### 2c. Set runtime secrets

Paste the values inline. These are encrypted at rest and only injected into the running VM as
environment variables, so they never appear in `fly.toml` or the image.

```bash
fly secrets set \
  ANTHROPIC_API_KEY="sk-ant-XXXXXXXXXXXXXXXX" \
  ELASTICSEARCH_URL="https://my-cluster.es.us-west-1.aws.found.io:443" \
  ELASTICSEARCH_API_KEY="BASE64_ID_COLON_KEY" \
  KIBANA_URL="https://my-cluster.kb.us-west-1.aws.found.io:443" \
  KIBANA_API_KEY="OPTIONAL_BASE64_KIBANA_KEY"
```

To rotate one secret without disturbing the others:

```bash
fly secrets set ANTHROPIC_API_KEY="sk-ant-NEW"
```

`fly secrets list` shows fingerprints (never the values).

### 2d. Deploy

```bash
fly deploy
```

The first build takes 5 to 8 minutes (multi-stage Python 3.13 + cairo/pango toolchain). Subsequent
deploys are 30 to 90 seconds because the venv layer is cached.

When `fly deploy` returns, hit the public URL:

```bash
curl https://fe-copilot.fly.dev/api/v1/health
```

You should see `{"status": "ok", ...}`.

---

## 3. Point the Kibana Agent Builder connector at Fly

After the deploy succeeds, repoint the connector that currently targets the ngrok URL.

```bash
export BACKEND_BASE_URL="https://fe-copilot.fly.dev"
PYTHONPATH=backend python -m scripts.sync_agent_builder
```

If you launched the app under the fallback name, use the matching URL:

```bash
export BACKEND_BASE_URL="https://fe-copilot-rcareaga.fly.dev"
PYTHONPATH=backend python -m scripts.sync_agent_builder
```

The script reads `BACKEND_BASE_URL` and writes the connector tool definitions
into Kibana via `KIBANA_API_KEY`. Re-run it any time the Fly URL changes (it
will not change unless you rename the app).

---

## 4. Standalone webapp URL

Nothing to do. The static frontend (`frontend/index.html`, `frontend/tools.html`,
`frontend/agent-builder.html`, etc.) is mounted by FastAPI at `/` and only ever
calls `/api/v1/...` on its own origin. Once the backend is on Fly, the frontend
talks to the same Fly hostname automatically. No ngrok URLs are baked into the
HTML files.

---

## 5. Rollback

List recent releases (each `fly deploy` creates one):

```bash
fly releases list
```

Roll back to a known-good release ID:

```bash
fly releases revert <release-id>
```

Reverts are atomic and skip the build step, so they finish in 10 to 20 seconds.

For a faster panic stop (machine off, no traffic) without rolling back the image:

```bash
fly scale count 0
# ... investigate ...
fly scale count 1
```

---

## 6. Cost expectations

- The `shared-cpu-1x` / 256 MB / 1 GB volume sizing fits inside Fly's always-allocated free
  resources for a single app.
- `auto_stop_machines = "stop"` plus `min_machines_running = 0` means an idle machine costs zero
  CPU-seconds. Expect roughly **$0/month** for hackathon-level demo traffic.
- If you keep the machine pinned warm (see section 7), expect $1.94/mo for the shared CPU plus
  $0.15/GB-month for the volume, so under $3/mo worst case.
- Outbound bandwidth: 160 GB/mo free, plenty for any number of demo runs.

---

## 7. Honest caveats and gotchas

These are the things that will bite during a live demo if you do not plan around them.

1. **Cold start is 3 to 5 seconds.** The Fly free-tier policy spins the machine down after about
   5 minutes of inactivity. The first hit after that pays for the VM boot, weasyprint shared-object
   load, and Anthropic + Elasticsearch client warm-up. For a recorded demo, keep the machine warm
   by tailing logs in a side terminal:

   ```bash
   fly logs
   ```

   `fly logs` keeps a TCP stream open, which counts as activity and prevents auto-stop. Start it
   30 seconds before you hit record.

2. **ELSER inference latency on cold ES cluster.** The first semantic search query after a long
   idle period rehydrates the ELSER model on the Elastic Cloud side and can take 10 to 20 seconds
   before it warms up to its normal sub-second latency. This is independent of Fly. If your demo
   leads with a search-heavy step, fire one warm-up query during setup.

3. **Elasticsearch API key permissions.** The key you load into `ELASTICSEARCH_API_KEY` needs:
   `read`, `view_index_metadata`, and `monitor` cluster privileges, plus index-level
   `read`, `write`, `create_index` on the `fe-*` index pattern. A read-only key will silently fail
   the `ensure_indices` startup hook and you will see `app.startup.es_ensure_failed` in `fly logs`.
   Generate the key with the `kibana_admin` builtin role plus a custom role that grants the
   index-level rights.

4. **WeasyPrint shared libraries.** The Dockerfile installs the runtime variants (`libcairo2`,
   `libpango-1.0-0`, `libpangoft2-1.0-0`, `libgdk-pixbuf-2.0-0`, `libffi8`) plus
   `shared-mime-info` and DejaVu/Liberation fonts. If you ever bump weasyprint past a major
   version, re-check that the .so names did not change in Debian Trixie. Symptom of a missed lib:
   `OSError: cannot load library 'libpangocairo-1.0.so.0'` at first PDF render.

5. **256 MB ceiling.** Concurrent PDF renders peak around 180 MB. The fly.toml caps soft
   concurrency at 20 requests but a worst-case burst of three simultaneous brief generations can
   OOM the VM. If you see `out of memory` in `fly logs`, bump to `shared-cpu-1x@512mb` (still
   inside the cheap tier):

   ```bash
   fly scale memory 512
   ```

6. **The `/app/runtime` volume is single-machine.** Fly volumes do not auto-replicate. If you
   ever scale to multiple regions, move audit.jsonl and the brief artefacts to S3-compatible
   storage (Tigris on Fly is one option) instead of the local volume.

7. **Region pinning.** `primary_region = "mia"` is for proximity to the `us-west-1` Elastic Cloud
   cluster used in the demo. Despite the name, `mia` is one of the lowest-latency Fly POPs to
   `us-west-1` over the public Internet for transcontinental hops; `sjc` is closer geographically
   but is heavily oversubscribed on the free tier. If you migrate the cluster to `us-east-1`,
   change to `iad` and redeploy.

8. **No ngrok required.** The Kibana connector script writes the Fly hostname directly. Do not
   leave the old ngrok tunnel running; it will race the Fly URL on whichever resolves first.

---

## 8. Quick reference

```bash
fly status                       # is the machine up
fly logs                         # tail logs (also keeps it warm)
fly ssh console                  # shell into the running container
fly secrets list                 # fingerprint-only, no values
fly releases list                # deploy history
fly scale memory 512             # bump RAM
fly scale count 0                # stop all machines
fly scale count 1                # start one machine
fly volumes list                 # check the runtime volume
fly apps destroy fe-copilot      # nuke everything (irreversible)
```
