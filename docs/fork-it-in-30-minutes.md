# Fork FE Copilot in 30 minutes

> Goal: any Elastic Solutions Architect, Customer Architect, or partner SE clones this repo on Monday and is running their region's version on Friday. This guide is the seven-step path; nothing else is required.
>
> The whole repo is MIT licensed. Fork it, brand it, ship it.

---

## What you need before you start

| Requirement | Why | Where |
|---|---|---|
| Docker Desktop or equivalent | Backend container | docker.com |
| Anthropic API key | Powers the agents (Haiku 4.5 default; ~$5 covers a week of demoing) | console.anthropic.com |
| Elastic Cloud trial or local 9.x cluster | FE Brain + Agent Builder + Workflows | cloud.elastic.co (14-day trial) |
| Kibana API key with `agent_builder:write` | Sync the 14 MCP tools into your cluster | Kibana > Stack Management > API Keys |
| 30 minutes of focus | The whole point | your calendar |

You do NOT need: a Salesforce sandbox, Klue access, Highspot. The portal demos cleanly without any of those connected.

---

## The seven steps

### Step 1: Clone and bootstrap (3 min)

```bash
git clone https://github.com/rodrigo-elastic/FE-Elastic.git my-fe-copilot
cd my-fe-copilot
cp .env.example .env
```

Open `.env` and fill in four values:

```
ANTHROPIC_API_KEY=sk-ant-...
ELASTICSEARCH_URL=https://<your-cluster>.es.cloud.es.io:9243
ELASTICSEARCH_API_KEY=<your-es-api-key>
KIBANA_URL=https://<your-cluster>.kb.cloud.es.io:9243
KIBANA_API_KEY=<your-kibana-api-key>
```

The other env vars have sensible defaults. Do not change `MODEL_DEFAULT` until step 7.

### Step 2: Swap the customers (5 min)

The demo ships with twelve fictional customers (Northwind Pay, Banco Atlántico, etc). Replace them with three real accounts in your patch.

Open `backend/app/services/scenarios/` and pick the scenario file closest to your typical deal (`fsi_banking_fraud.py`, `healthcare_hipaa_audit.py`, `supply_chain_attack.py`, etc). Copy it to a new file:

```bash
cp backend/app/services/scenarios/fsi_banking_fraud.py \
   backend/app/services/scenarios/my_first_account.py
```

Inside the new file, change five things:
1. `SCENARIO_ID` (top of file): give it a slug for your account.
2. `CUSTOMER_NAME` and `INDUSTRY`: real values.
3. The transcript fixture (`SAMPLE_TRANSCRIPT` or similar): paste 2-3 minutes of a redacted call you actually had.
4. The MEDDPICC fields: real signals from the deal.
5. The competitor list: real names you compete against in this account.

Repeat for two more accounts. Three real customers is the minimum for the workspace timeline to feel populated.

Keep the original twelve as fallback fixtures so the autopilot demo (`/quick-research.html`) still works without your live data.

### Step 3: Swap the industries (4 min)

Edit `data/seed/industries.json`. Each entry is:

```json
{
  "id": "fsi-real-time-payments",
  "name": "Real-Time Payments",
  "industry": "Financial Services",
  "summary": "...",
  "elastic_use_cases": ["fraud detection", "transaction tracing", "regulatory reporting"],
  "elastic_blog_posts": [
    "https://www.elastic.co/blog/..."
  ]
}
```

Keep the JSON shape, change the values to your top 5 verticals. The portal renders directly from this file. No backend rebuild required.

### Step 4: Swap the battlecards (6 min)

Edit `backend/data/seed/battlecards.json`. Each card is roughly 50 lines: `competitor`, `key_pain`, list of `objections` (each with `q`, `a`, `proof`).

Trim the existing 31 down to your top 5-10 competitors, or add new ones. The battlecard panel renders in marketshare order; set `marketshare_rank` if you want to override the sort.

### Step 5: Swap the personas (4 min)

Open `backend/app/agents/prompts/tools.py`. The personas (Marta, Diego, Priya, Aiko, Kenji, Lyra, Mei, Ravi, Sloane, Auro, Carmen, Sage, Astrid, Lina) are inline system prompts. Each persona is roughly 30 lines.

To rebrand to your team's voice:
1. Replace the persona name with someone from your team (with their permission).
2. Replace the `# Your background` block with their real bio (years at Elastic, regions, deal types).
3. Leave the `# How a great X looks (your method)` block intact - that is the prompt engineering you want to keep.

If you do not want to use real names, swap to a region naming scheme: "Maya, EMEA Senior SA" / "Diego, LATAM Senior SA". The personality survives.

### Step 6: Sync the MCP tools into your Kibana (5 min)

The 14 MCP tools have to be registered in your Kibana cluster so Agent Builder can call them.

```bash
docker compose up -d   # backend on :8123
python backend/scripts/sync_agent_builder.py
```

The script reads your `KIBANA_URL` + `KIBANA_API_KEY` from `.env`, lists the 14 `fec_*` tools, and creates them in your cluster's Agent Builder. You should see:

```
synced 14 tools to <kibana-url>/api/agent_builder/tools
synced 1 master agent (FE Copilot) and 3 specialists (RFP Responder, Migration, Compliance)
```

Open Kibana > AI > Agent Builder. You will see the 14 tools listed.

### Step 7: Verify with the integration smoke (3 min)

```bash
python backend/scripts/integration_smoke.py
```

This walks through 9 checks: backend health, MCP tool count (asserts 14), `tools/list` endpoint, fec-tool fraction, frontend pages including `/workspace.html` and `/pov-health.html`, demo data, and git status. Expect:

```
PASS step 1: backend healthy
PASS step 2: tools/list returned 14 tools
PASS step 3: 14/14 fec_ tools present
PASS step 4: MCP count == 14
...
verdict: GO
```

If any step says FAIL, the message tells you which file to look at. The most common cause is a missing env var.

---

## What you have now

Open `http://localhost:8123/`. You should see:
- 14 chips on the home page, ending with POV Health (yours).
- Workspace tab populated with your 3 real customers.
- Industries tab with your top 5 verticals.
- Battlecards tab with your top 10 competitors.
- Agent Builder tab with the master + 3 specialists, all using your team's persona names.

Total elapsed: 30 minutes if you have your data ready, 60 if you have to dig for it.

---

## Optional polish (another 30 minutes if you want it)

| Polish | Time | What changes |
|---|---|---|
| Add your team's logo to `/frontend/assets/img/logo.svg` | 5 min | Header looks like yours |
| Add your team's color to `/frontend/assets/css/styles.css` `--primary` | 2 min | Whole UI shifts to your brand |
| Translate the strings to your language | 15 min | `frontend/assets/i18n/<lang>.json`; English/Spanish/Japanese/German/French already shipped |
| Connect Salesforce | 30 min | Workflows YAML in `/infra/workflows/`; one of the two ships as `salesforce-update.yaml` |
| Deploy to Fly.io | 10 min | `fly launch` reads the existing `fly.toml`; `fly secrets set` for your env vars |

---

## What NOT to change on the first fork

Resist the urge to rewrite these in the first 30 minutes. They are the plumbing that makes everything else work, and breaking them costs an hour to debug:

- The MCP tool schemas in `backend/app/api/routes_mcp.py`.
- The Pydantic schemas in `backend/app/agents/schemas.py`.
- The integration smoke script.
- The autopilot HTML page (`/quick-research.html`) - it is the canned demo for new viewers; keep it intact, it makes your fork demoable to your boss in 45 seconds.

---

## When something breaks

The 30-minute path assumes the four env vars are correct. Most "fork failures" are:

| Symptom | Cause | Fix |
|---|---|---|
| `tools/list` returns 0 | `ELASTICSEARCH_API_KEY` empty or wrong | Re-mint the key with read+write |
| Agent Builder tab in Kibana is empty | `KIBANA_API_KEY` lacks `agent_builder:write` | Re-mint with the right privilege |
| Pre-meeting agent returns "credit balance is too low" | Anthropic credits exhausted | Top up at console.anthropic.com; the demo will fall back to mock fixtures meanwhile |
| `/workspace.html` shows no customers | You did not write to `runtime/briefs/` yet | Run the autopilot once to seed |
| Smoke FAIL on step 9 (git status) | Local working tree dirty | Non-critical; ignore for development |

---

## Where to send your fork

If your fork is useful for your team, please open a PR back to `https://github.com/rodrigo-elastic/FE-Elastic` with:
- A new scenario file under `backend/app/services/scenarios/<your-region>.py` (with the customer name redacted to a fictional alias).
- A new battlecard if you cover a competitor not yet listed.
- A locale file under `frontend/assets/i18n/<lang>.json` if you translated.

This is how the project covers more of the FE org over time. The repo is the FE knowledge graph; every fork makes it denser.

---

## The 30-second elevator answer in your live Q&A

> *"It is MIT, the entire FE knowledge layer is in JSON and Markdown so any FE can fork and swap their region's customers, industries, battlecards, and personas in thirty minutes. The plumbing - 14 MCP tools, three context-driven agents, two Workflows - stays. The content is yours."*

That sentence is the Reusability rubric, in your own voice.
