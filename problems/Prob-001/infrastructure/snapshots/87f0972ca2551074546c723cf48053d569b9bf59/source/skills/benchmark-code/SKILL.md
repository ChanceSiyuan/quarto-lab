---
name: benchmark-code
description: Use when a user wants to benchmark an AutoQEC code or campaign through distance or Monte Carlo LER workflows.
---

# benchmark-code

## Overview

This is the top-level benchmark orchestrator for AutoQEC. It conducts
conversation-first intake, runs preflight, summarizes the proposed execution,
requires explicit approval, and dispatches to `bench-runner-distance` or
`bench-runner-mc-ler`.

It is intentionally thin. It drives the existing `autoqec-search` CLI and does
not implement distance algorithms, rsinter dispatch, manifest parsing, report
rendering, or Zoo promotion.

## Workflow

1. Resolve the target:
   - an existing campaign id,
   - an existing run directory,
   - a candidate directory,
   - or an exact Zoo instance path.
2. Resolve benchmark type:
   - `distance`
   - `mc-ler`
3. Run:

```bash
PYTHONPATH=src python3 -m autoqec_search.cli preflight --root .
```

4. Summarize the execution plan in natural language:
   - target
   - benchmark type
   - suite/task/decoder choices when known
   - p-list or distance method when known
   - run id and output directory when applicable
   - budget or wall-clock limit when applicable
5. Ask for explicit approval.
6. Before approval, you must not run benchmark commands or write run artifacts.
7. After approval, dispatch:
   - distance work to `bench-runner-distance`
   - MC-LER work to `bench-runner-mc-ler`
8. Report generated run and report paths.

## Approval Gate

Accepted approval language includes "approved", "looks good", "run it", and
"continue".

Non-approval language includes "wait", "not yet", "show me first", and "do not
run". In those cases, say that no benchmark command is run and no run artifacts
are written.

## Rules

- Always run or propose `autoqec-search preflight` before execution.
- Stop on a failing preflight unless the user explicitly asks only for a dry
  command summary.
- Do not silently reinterpret a distance upper bound as exact distance.
- Do not promote results into `zoo/`; use the existing promotion workflow only
  after a separate user decision.
- Do not claim BB72 OSD1 smoke data satisfies the deferred published OSD10
  reference validation.
- Missing backend messages must remain precise; do not mask them with generic
  advice.
