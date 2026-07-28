---
name: bench-runner-mc-ler
description: Use when running or reviewing AutoQEC Monte Carlo logical-error-rate benchmark workflows.
---

# bench-runner-mc-ler

## Overview

This skill handles Monte Carlo logical-error-rate benchmarking through the
existing `autoqec-search eval`, `autoqec-search run`, and `autoqec-search
report` commands. It uses `autoqec-search report` to render run results.

It does not implement rsinter dispatch directly.

## Workflow

1. Resolve whether the user wants:
   - a single-candidate evaluation, or
   - a campaign sweep.
2. Run:
   `autoqec-search preflight`.

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
```

3. Summarize:
   - campaign id
   - suite id
   - task ids
   - decoder ids or decoder filters
   - p values or p filters
   - wall-clock budget for campaign runs
   - run id
   - report path
4. Ask for explicit approval before running benchmark commands.
5. For single-candidate work, run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli eval --root . --campaign <campaign-id> --distance <d> --run-id <run-id>
PYTHONPATH=src python3 -m autoqec_search.cli report --root . --run results/search/<campaign-id>/<run-id>
```

6. For campaign sweeps, run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli run --root . --campaign <campaign-id> --wall-clock <seconds>s --run-id <run-id> --allow-dirty-root
PYTHONPATH=src python3 -m autoqec_search.cli report --root . --run results/search/<campaign-id>/<run-id>
```

## Rules

- Preserve precise missing-dependency messages from preflight and eval.
- Do not write partial or garbage run artifacts after a missing-backend failure.
- Use committed or fixture-backed M1 data for fast verification.
- Real rsinter smoke runs are optional and should be called out as backend
  dependent.
- The BB72 OSD1 smoke artifact proves AutoQEC orchestration, report, and
  promotion flow. It does not satisfy the deferred BB72 OSD10 published
  reference validation tracked on the rstim side.

## Negative Controls

- If preflight cannot find rsinter, stop before eval/run.
- If general CSS support is missing for a CSS task, preserve the upstream
  required-feature message.
- If a manifest is placeholder or crash, report it as skipped rather than a
  completed MC-LER point.
