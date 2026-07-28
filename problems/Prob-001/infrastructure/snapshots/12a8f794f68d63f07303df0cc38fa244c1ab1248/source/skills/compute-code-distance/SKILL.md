---
name: compute-code-distance
description: Use when computing code distance for an existing finite-size CSS instance stored under zoo/codes/**/instances/.
---

# compute-code-distance

## Overview

This is a project-level AutoQEC skill for computing code distance from an existing stored CSS instance and recording the result on `instance.json`.

## Workflow

1. Confirm that `julia/tensorqec_env/` is already set up. If not, stop and point the user to `setup-tensorqec`.
2. Resolve the target instance from an exact instance id or exact instance directory path.
3. Read `instance.json`, `hx.json`, and `hz.json`.
4. Stop if `instance_kind` is not `finite_css_instance` or the matrix artifacts are missing.
5. If `derived_properties.distance` already has a value, ask whether to overwrite it.
6. Run:

```bash
julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/compute_distance.jl \
  --hx-path <instance-root>/hx.json \
  --hz-path <instance-root>/hz.json
```

7. Parse the JSON result and update `instance.json` so `derived_properties.distance` equals the computed value.
8. Report the instance id, path, `n`, and computed distance.

## Rules

- Do not edit `card.json`.
- Do not create evidence records.
- Do not overwrite an existing recorded distance without explicit user confirmation.
- Stop if the Julia command fails or returns malformed JSON.
