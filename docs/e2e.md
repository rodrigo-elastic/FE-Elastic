# FE Copilot e2e suite

Playwright suite that exercises all eight frontend pages of FE Copilot against a live backend on `http://127.0.0.1:8123`. The CI / dev runner is responsible for starting the FastAPI backend before invoking the suite. Tests never call `/seed` or `/converse` so they do not burn Claude tokens, and they never mutate Kibana state.

## Layout

```
tests/e2e/
  package.json          # devDependency on @playwright/test
  playwright.config.ts  # chromium only, list reporter, 4 workers, 60s timeout
  tests/
    dashboard.spec.ts
    quick_research.spec.ts
    meeting_northwind.spec.ts
    agent_builder.spec.ts
    demo_data.spec.ts
    workflow_demo.spec.ts
    fe_brain.spec.ts
    tools_panels.spec.ts
```

## Install

```bash
cd tests/e2e
npm install
npx playwright install chromium
```

Requires Node 18+. If `node` / `npm` are not on PATH (this repo's machine did not have Node installed at the time of suite authoring), install via `brew install node` or `nvm install --lts`, then rerun the two commands above.

## Run

```bash
cd tests/e2e
npm run test:e2e
```

Expected runtime is roughly 90 seconds for the full eight specs at 4 workers. The `fe_brain` spec is the slowest (it can take up to 55s when the docs corpus is cold).

### Headed mode (debugging)

```bash
npx playwright test --headed
```

### Trace on failure

```bash
npx playwright test --trace on
```

Failed runs persist a trace bundle under `test-results/`. Open it with `npx playwright show-trace path/to/trace.zip`.

## Prerequisites for a green run

- Backend is up at `http://127.0.0.1:8123` and `/api/v1/health` returns `{"status":"ok"}`.
- The Agent Builder integration is wired so `/api/v1/agent-builder/status` reports `live: true` (otherwise the `agent_builder` and `fe_brain` specs fail on the Live pill assertion). If your env is dry-run only, expect those two specs to fail loudly; do not silently skip them.
- The workflow demo expects the rule + connector to have been synced once. The spec only asserts the keys render in the status panel, not their state, so this is informational.

## Conventions

- No live mutations: tests never click `Seed scenario`, `Fire demo transcript`, or `Send` in agent-builder.
- The fe-brain spec does click `Send` because the underlying `/tools/knowledge-search` call is read only over the docs corpus and is gated by a 55s graceful timeout that accepts either an answer card or the friendly error block.
- Selectors prefer ids and stable class names. Tabs use `data-tab` attributes. Sidebar tools use the `.tools-nav-pill` class with a numeric `.tools-nav-num` ordinal.
- Suite is chromium only on a 1440x2400 viewport so screenshots are dense enough for the wide rail layout.

## Install caveat

This suite was authored on a machine without Node / npm available. `npm install` was therefore not executed end to end during authoring; the configuration and specs are self consistent and should run cleanly once Node is installed. If the first `npm install` fails on your machine, double check the Node version (`node --version`) and the proxy / registry config.
