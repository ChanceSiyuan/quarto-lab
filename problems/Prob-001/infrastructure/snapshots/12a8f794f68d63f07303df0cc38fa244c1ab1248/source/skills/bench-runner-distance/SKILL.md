---
name: bench-runner-distance
description: Use when running or reviewing deterministic AutoQEC code-distance benchmark results.
---

# bench-runner-distance

## Overview

This skill handles deterministic distance benchmarking for existing AutoQEC
campaign candidates and run artifacts. It is a thin wrapper over existing
`autoqec-search` candidate evaluation and `distance.json` contracts.

## Workflow

1. Resolve the target as one of:
   - a run candidate directory containing `distance.json`,
   - a campaign candidate selectable by `autoqec-search eval`,
   - or an exact Zoo instance path.
2. Run or inspect preflight:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
```

3. For an existing candidate directory, read:
   - `candidate.json`
   - `structure.json`
   - `distance.json`
4. For a campaign candidate, use the existing eval path after approval:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli eval --root . --campaign <campaign-id> --distance <d> --run-id <run-id>
```

5. Report:
   - candidate id
   - code family
   - structure status
   - distance
   - method
   - `bound_type`
   - whether the result is promotion-safe

## Rules

- Exact distance results must be reported as exact only when `bound_type: "exact"`
  is present or the legacy payload is clearly an exact copied Zoo
  distance.
- Upper-bound, unavailable, or malformed distances are not promotion-safe.
- The known rotated surface `d=3` check should report distance 3.
- Stop on missing backend or missing instance artifacts with the exact error
  message.
- Do not overwrite curated Zoo instance files.
- Do not run expensive external distance backends unless the user explicitly
  approves the command.

## Negative Controls

- If `distance.json` has `bound_type: "upper"`, say it is not promotion-safe.
- If the target has no exact recorded distance, stop and say which artifact is
  missing.
- If preflight reports a missing backend, do not write partial run artifacts.
