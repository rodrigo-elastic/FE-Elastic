# README badges

Drop-in shields.io URLs for the FE Copilot README hero. Order them on a single
line so they render as a strip directly under the project title.

## Suggested layout

```markdown
![tests](https://img.shields.io/badge/tests-30%2F30%20passing-brightgreen?style=flat-square&logo=pytest&logoColor=white)
![python](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square&logo=python&logoColor=white)
![elastic stack](https://img.shields.io/badge/elastic%20stack-9.3.4-005571?style=flat-square&logo=elastic&logoColor=white)
![license](https://img.shields.io/badge/license-MIT-blue?style=flat-square)
![hackathon](https://img.shields.io/badge/FY27%20SKO%20FE%20Summit-deadline%202026--05--10-orange?style=flat-square)
![built with claude](https://img.shields.io/badge/built%20with-Claude-D97757?style=flat-square&logo=anthropic&logoColor=white)
```

## Per-badge breakdown

| Purpose | Markdown |
|---|---|
| Tests passing | `![tests](https://img.shields.io/badge/tests-30%2F30%20passing-brightgreen?style=flat-square&logo=pytest&logoColor=white)` |
| Python version | `![python](https://img.shields.io/badge/python-3.11%2B-blue?style=flat-square&logo=python&logoColor=white)` |
| Elastic stack version | `![elastic stack](https://img.shields.io/badge/elastic%20stack-9.3.4-005571?style=flat-square&logo=elastic&logoColor=white)` |
| License | `![license](https://img.shields.io/badge/license-MIT-blue?style=flat-square)` |
| Hackathon submission deadline | `![hackathon](https://img.shields.io/badge/FY27%20SKO%20FE%20Summit-deadline%202026--05--10-orange?style=flat-square)` |
| Built with Claude (Anthropic) | `![built with claude](https://img.shields.io/badge/built%20with-Claude-D97757?style=flat-square&logo=anthropic&logoColor=white)` |

## Notes

- License badge resolves to MIT to match the `LICENSE` file in repo root.
  Confirmed in W23B compliance audit and re-verified in W27D docs lint.
- The Elastic stack badge color `#005571` is the Elastic brand teal.
- The Claude badge color `#D97757` is the Anthropic brand terracotta.
- Style is `flat-square` for visual consistency. Switch to `for-the-badge` if
  the README hero needs more weight.
- The hackathon badge encodes the date with a literal hyphen as `--` so the
  shields.io URL parser keeps it as a single dash in the rendered text.
- For a dynamic test badge later, replace the hardcoded count with a GitHub
  Actions workflow status badge:
  `https://img.shields.io/github/actions/workflow/status/[ORG]/FE-Elastic/tests.yml?style=flat-square&label=tests`.
