---
name: setup-tensorqec
description: Use when setting up or verifying the repository-local Julia environment for TensorQEC-based finite code-instance generation.
---

# setup-tensorqec

## Overview

This is a project-level AutoQEC skill for preparing the repository-local `tensorQEC.jl` environment under `julia/tensorqec_env/`.

Use it when the user asks to install, configure, or verify the local TensorQEC generation environment.

## Workflow

1. Check that `julia` is available on the machine.
2. Run:

```bash
julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/setup.jl
```

3. Report:
   - Julia availability
   - environment path
   - whether `TensorQEC` imported successfully
   - the smoke-test matrix dimensions
4. If the setup succeeds, recommend `generate-code-instance` for the next step.

## Failure Conditions

Stop and report clearly if:

- Julia is not installed
- package instantiation fails
- `TensorQEC` cannot be imported
- the smoke test fails
