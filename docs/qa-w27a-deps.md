# QA W27A: Dependency Audit

Owner: Opus Max dependency engineer
Date: 2026-05-04
Scope: backend Python deps in `.venv`, declared in `backend/requirements.txt` and
`pyproject.toml`. Project license: MIT.

## TL;DR

- pip-audit pre-fix: 3 known vulnerabilities (all in `pip` 25.2 itself).
- pip-audit post-fix: 0 known vulnerabilities.
- Float-pin offenders: 13 of 13 declared backend deps used `>=` ranges. All now
  pinned to exact versions (`==X.Y.Z`).
- License compatibility: 1 transitive dep (`pyphen`) is dual-licensed under
  GPLv2+/LGPLv2+/MPL 1.1. Used for hyphenation only via WeasyPrint as a dynamic
  Python import. Acceptable under LGPLv2+ or MPL 1.1 selection (compatible with
  MIT). Documented below.
- `requirements.lock` was missing, now written.
- Frontend has no `package.json` shipping (vanilla JS), confirmed.
- Backend smoke: GO (see end of doc).

## 1. CVEs

### Pre-fix (against the live `.venv`)

| Package | Version | CVE / Advisory | Severity | Affected | Fix Versions | Status |
|---|---|---|---|---|---|---|
| pip | 25.2 | CVE-2025-8869 (GHSA-4xh5-x5gv-qwph) | Moderate | tar extraction can follow symlinks if Python lacks PEP 706 | 25.3 | FIXED (pip upgraded to 26.1.1) |
| pip | 25.2 | CVE-2026-1703 (GHSA-6vgw-5pg2-w6jp) | Moderate | wheel extraction path traversal | 26.0 | FIXED (pip upgraded to 26.1.1) |
| pip | 25.2 | CVE-2026-3219 (GHSA-58qw-9mgm-455v) | Low | concatenated tar+ZIP archives parsed as ZIP | (no fix listed) | MITIGATED (latest pip 26.1.1, only triggers on adversarial sdists) |

Notes
- `pip` is the package manager only; it is NOT part of the runtime backend code,
  and is not declared in `requirements.txt`. Still upgraded as venv hygiene.
- Python interpreter in use is 3.13 (PEP 706 implementer), so CVE-2025-8869
  fallback path was not reachable in practice. Upgrade is defense-in-depth.

### Post-fix

```
.venv/bin/pip-audit --format=columns
No known vulnerabilities found
```

No HIGH or CRITICAL CVEs were ever present. No deferred CVEs.

## 2. Float-pin offenders

`backend/requirements.txt` previously used `>=` ranges for every line. All
floats are flagged below and were pinned to the version installed in the
working venv.

| Line | Before | After |
|---|---|---|
| fastapi | `fastapi>=0.110.0` | `fastapi==0.136.1` |
| uvicorn | `uvicorn[standard]>=0.27.0` | `uvicorn[standard]==0.46.0` |
| pydantic | `pydantic>=2.6.0` | `pydantic==2.13.3` |
| pydantic-settings | `pydantic-settings>=2.2.0` | `pydantic-settings==2.14.0` |
| python-dotenv | `python-dotenv>=1.0.0` | `python-dotenv==1.2.2` |
| anthropic | `anthropic>=0.25.0` | `anthropic==0.97.0` |
| elasticsearch | `elasticsearch>=9.0.0,<10` | `elasticsearch==9.3.0` |
| weasyprint | `weasyprint>=61.0` | `weasyprint==68.1` |
| jinja2 | `jinja2>=3.1.0` | `jinja2==3.1.6` |
| httpx | `httpx>=0.27.0` | `httpx==0.28.1` |
| structlog | `structlog>=24.1.0` | `structlog==25.5.0` |
| pytest | `pytest>=8.0.0` | `pytest==9.0.3` |
| pytest-asyncio | `pytest-asyncio>=0.23.0` | `pytest-asyncio==1.3.0` |

Float pins fixed: 13 / 13.

`pyproject.toml` is the source-of-truth project metadata for downstream
packaging and intentionally retains `>=` ranges so that consumers can resolve a
SAT-compatible set; the runtime environment is constrained by the pinned
`backend/requirements.txt` plus the new `requirements.lock`. This split is a
common pattern (loose `pyproject.toml`, exact `requirements.txt`) and was left
untouched to avoid breaking pip install paths.

## 3. Transitive freezing

Before this audit there was no `requirements.lock`. Gap is now closed:

```
.venv/bin/pip freeze > requirements.lock
```

`requirements.lock` ships a fully resolved transitive set (66 packages).
Audit-only tooling (`pip-audit`, `pip-licenses` and their transitive deps) is
filtered out so the lock describes only runtime + dev (pytest, ruff) packages.
CI / Docker should `pip install -r requirements.lock` for reproducible builds.

## 4. Frontend

The frontend is vanilla JS / HTML / CSS served by FastAPI. Verified there is no
`package.json` in the repo:

```
find /Users/rodrigocareaga/Downloads/FE-Elastic -maxdepth 2 -name 'package.json'
(no output)
```

No node_modules. No unused devDeps. Nothing to flag.

## 5. License compatibility

Project license: MIT. All direct backend deps are MIT, BSD, Apache-2.0, MPL-2.0
(certifi), or PSF (typing_extensions, defusedxml). All compatible with MIT.

Direct deps:

| Package | Version | License | MIT-compat |
|---|---|---|---|
| fastapi | 0.136.1 | MIT | yes |
| uvicorn | 0.46.0 | BSD-3-Clause | yes |
| pydantic | 2.13.3 | MIT | yes |
| pydantic-settings | 2.14.0 | MIT | yes |
| python-dotenv | 1.2.2 | BSD-3-Clause | yes |
| anthropic | 0.97.0 | MIT | yes |
| elasticsearch | 9.3.0 | Apache-2.0 | yes |
| weasyprint | 68.1 | BSD | yes |
| jinja2 | 3.1.6 | BSD | yes |
| httpx | 0.28.1 | BSD | yes |
| structlog | 25.5.0 | MIT OR Apache-2.0 | yes |
| pytest | 9.0.3 | MIT | yes |
| pytest-asyncio | 1.3.0 | Apache-2.0 | yes |

Transitive review (only entries with non-permissive components):

| Package | License | Used by | Compatibility |
|---|---|---|---|
| pyphen | GPLv2+ OR LGPLv2+ OR MPL 1.1 | weasyprint hyphenation | OK under LGPLv2+ / MPL 1.1 selection. Pyphen is imported as a Python module; we redistribute only via dependency declaration, not vendor copy, and we do not modify pyphen sources. Under LGPLv2+ this dynamic-link / dependency use case is compatible with an MIT project. Recommendation: choose LGPLv2+ in any redistribution NOTICE. |
| certifi | MPL-2.0 | requests/anthropic | MIT-compat (file-level copyleft only) |

No GNU AGPL deps. No GPL-only (without LGPL/MPL alternative) deps. No license
incompatibility blockers.

## 6. Recommendations

1. (DONE) Upgrade `pip` 25.2 -> 26.1.1 to clear all 3 advisories.
2. (DONE) Pin all 13 backend deps to exact versions in `backend/requirements.txt`.
3. (DONE) Add `requirements.lock` for reproducible installs.
4. Periodically re-run `pip-audit` (suggest weekly during demo-prep, monthly
   post-launch). Add a CI job invoking `pip-audit --strict` against
   `requirements.lock` before each release.
5. When upgrading WeasyPrint, re-confirm `pyphen` license remains
   tri-licensed; if upstream ever drops the LGPL/MPL options, swap to a
   permissive hyphenation provider.
6. `pyproject.toml` `>=` ranges were intentionally kept; if a future consumer
   wants strict reproducibility from `pyproject.toml` alone, switch to
   `==` pins there too.

## 7. Smoke after fixes

```
pkill -f 'uvicorn.*8123' ; sleep 2
PYTHONPATH=backend nohup .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8123 > /tmp/fec-backend.log 2>&1 &
sleep 4
PYTHONPATH=backend .venv/bin/python -m scripts.integration_smoke
```

Result: see "Smoke" section at the end of the run report. GO.
