# CI / CD

This repo uses two GitHub Actions workflows:

- `.github/workflows/ci.yml` runs tests and lint on every push and pull request.
- `.github/workflows/deploy.yml` runs tests, lint, and a gated Fly.io deploy on push to `main` (and manual `workflow_dispatch`).

## What runs on PR vs push to main

### Pull requests and branch pushes (`ci.yml`)

| Job  | What it does                                                                 | Approx. runtime |
|------|-------------------------------------------------------------------------------|-----------------|
| test | Sets up Python 3.13, installs `backend/requirements.txt`, runs `pytest backend/tests -q` with `ANTHROPIC_API_KEY=""` (mock mode). | ~30s |
| lint | Installs `ruff`, runs `ruff check backend/`, runs `python -m compileall -q backend`, fails if any em-dash (`U+2014`) or en-dash (`U+2013`) is present in `backend/`, `frontend/`, or `docs/`. | ~10s |

The two jobs run in parallel. Pip wheels are cached via `actions/setup-python@v5`'s built-in cache (keyed on `backend/requirements.txt`).

### Push to `main` (`deploy.yml`)

The deploy workflow re-runs `test` and `lint` as gates, then runs `deploy` only if both pass.

| Job    | Purpose                                                       | Approx. runtime |
|--------|---------------------------------------------------------------|-----------------|
| test   | Same suite as CI, gating the deploy.                          | ~30s            |
| lint   | Same checks as CI, gating the deploy.                         | ~10s            |
| deploy | `superfly/flyctl-actions/setup-flyctl@master` then `flyctl deploy --remote-only`. | ~3min |

`concurrency: deploy` ensures two pushes do not race; the second push waits for the first deploy to finish.

If a commit message contains `[skip deploy]`, all three jobs are skipped (the workflow still runs, but every job's `if:` condition evaluates to `false`).

If `FLY_API_TOKEN` is not configured, the `deploy` job logs a warning and exits without invoking `flyctl`, so a missing secret does not turn the run red.

## Setting the `FLY_API_TOKEN` secret

Generate a token locally:

```bash
fly auth token
```

Then add it to the repository:

```bash
gh secret set FLY_API_TOKEN --repo rodrigo-elastic/FE-Elastic
# paste the token when prompted
```

Or via the UI: Settings -> Secrets and variables -> Actions -> New repository secret -> Name `FLY_API_TOKEN`.

## Useful commands

Inspect the latest CI runs:

```bash
gh run list --repo rodrigo-elastic/FE-Elastic --limit 10
gh run list --workflow ci.yml --limit 5
gh run watch                       # live-tail the most recent run
gh run view <run-id> --log-failed  # show logs of failed steps
```

Trigger a deploy manually (no commit needed):

```bash
gh workflow run deploy.yml --ref main
gh run list --workflow deploy.yml --limit 1
```

Re-run a failed run:

```bash
gh run rerun <run-id> --failed
```

## Local parity

Reproduce CI locally before pushing:

```bash
# Tests
PYTHONPATH=backend ANTHROPIC_API_KEY="" .venv/bin/python -m pytest backend/tests -q

# Lint
.venv/bin/ruff check backend/
.venv/bin/python -m compileall -q backend

# Em/en dash audit (the character class below contains U+2014 EM DASH and
# U+2013 EN DASH; we build it via printf so this doc stays ASCII-clean and
# the audit itself does not flag this file).
DASHES="$(printf '\xe2\x80\x94\xe2\x80\x93')"
grep -rn "[$DASHES]" backend frontend docs \
    --include='*.py' --include='*.html' --include='*.js' --include='*.css' --include='*.md' \
    && echo "FAIL: dashes found" || echo "OK"
```

## Status badge

Add this to `README.md` (top of the file) once the first CI run is green:

```markdown
[![CI](https://github.com/rodrigo-elastic/FE-Elastic/actions/workflows/ci.yml/badge.svg)](https://github.com/rodrigo-elastic/FE-Elastic/actions/workflows/ci.yml)
[![Deploy](https://github.com/rodrigo-elastic/FE-Elastic/actions/workflows/deploy.yml/badge.svg?branch=main)](https://github.com/rodrigo-elastic/FE-Elastic/actions/workflows/deploy.yml)
```

## Ruff configuration notes

The active ruff config lives in `pyproject.toml` under `[tool.ruff]` and `[tool.ruff.lint]`. We currently enable the `E` (pycodestyle) and `F` (pyflakes) rule families, with a small ignore list for patterns that are intentional in this codebase. Expanding to `I`, `B`, or `UP` would require a one-time auto-fix pass; track that as a follow-up rather than a CI gate.
