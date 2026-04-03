# AGENTS.md

## Purpose
This repository generates and serves three-party-preferred (3PP) visualisations as SVG.

## Project map
- `visualise.py`: primary logic for winner calculation, geometry, SVG generation, CLI argument parsing/validation.
- `threeparty.py`: WSGI wrapper that maps query parameters to `visualise` arguments and returns SVG.
- `index.html`: browser UI for setting preference flows and loading/downloading generated graphs.
- `index_cpv.html`: alternate/static UI variant.
- `points.csv`: sample points-of-interest data source.
- `nginx.conf`, `threeparty.ini`, `threeparty.service.conf`: deployment config examples.

## Practical workflow for agents
1. Read `README.md` plus any touched source files.
2. Prefer minimal, localised changes; preserve existing query parameter names and defaults.
3. For Python changes, run:
   - `python3 -m py_compile visualise.py threeparty.py`
   - `python3 visualise.py --step 0.02 --start 0.2 --stop 0.6 > /tmp/3pp.svg`
4. If changing UI/query interactions, confirm `index.html` form fields still align with `threeparty.make_args()`.

## Behavioural invariants to preserve
- Preference flow pairs are expected to remain bounded and validated by `validate_args()`.
- `threeparty.py` should continue sanitising point labels via `esc()` before emitting SVG.
- WSGI output should remain an SVG response with inline display by default and optional download via `dl` query param.
- Keep compatibility with the current no-extra-dependencies Python 3 setup.

## Coding notes
- This is a small, script-first codebase; avoid adding frameworks/tooling unless asked.
- Keep functions straightforward and readable; avoid large refactors unless necessary for correctness.
- Prefer deterministic output formatting where possible, as SVG files are inspected directly.

## Personalisation
- Alex prefers Australian spelling in written text (for example, "visualisation", "behaviour", "optimise").
