---
name: generate-code-instance
description: Use when generating a finite-size CSS parity-check instance for a supported code family and storing it under zoo/codes/**/instances/.
---

# generate-code-instance

## Overview

This is a project-level AutoQEC skill for generating finite-size CSS instances with `tensorQEC.jl` and storing them in the structured Zoo layer.

Supported v1 families:

- `rotated-surface-code`
- `surface-code`
- `bivariate-bicycle-code`

## Workflow

1. Confirm that `julia/tensorqec_env/` is already set up. If not, stop and point the user to `setup-tensorqec`.
2. Resolve the target family:
   - if the user says `surface code`, ask whether they want `rotated` or `unrotated`
3. Collect required parameters one at a time:
   - rotated/unrotated surface code: `distance`
   - bivariate bicycle code: the current adapter contract fields `m`, `n`, `vc`, `hd`
4. Compute the target instance slug:
   - rotated surface code: `rotated-surface-code-d<distance>`
   - unrotated surface code: `surface-code-d<distance>`
   - BB code: `bivariate-bicycle-code-m<m>-n<n>`
5. Refuse to overwrite an existing directory under `zoo/codes/<code-id>/instances/<instance-slug>/`.
6. Run the Julia generator into a temporary directory:

```bash
julia --project=julia/tensorqec_env julia/tensorqec_env/scripts/generate_instance.jl \
  --code-id <code-id> \
  ...family-specific args... \
  --output-root <tmp-output-root>
```

7. Validate the generated bundle with the repo's existing Python validation/build path if practical, then move it into:

```text
zoo/codes/<code-id>/instances/<instance-slug>/
```

8. Report the created instance id, path, parameters, and matrix dimensions.
9. Read the generated `instance.json`.
10. If `derived_properties.n <= 200`, ask whether to compute code distance now.
11. If the user agrees, run the `compute-code-distance` workflow on the new instance.
12. If `derived_properties.n > 200`, report that automatic distance computation is skipped because the instance exceeds the threshold.
13. Report whether code distance was computed.

## Rules

- Do not edit `card.json`.
- Do not route generated data through `zoo/evidence/`.
- Do not guess unsupported families.
- Stop if generation output fails schema or matrix validation.
