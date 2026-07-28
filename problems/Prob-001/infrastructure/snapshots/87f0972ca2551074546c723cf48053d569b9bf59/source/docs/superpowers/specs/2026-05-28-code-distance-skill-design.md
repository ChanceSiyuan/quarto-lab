# Code Distance Skill Design

## Goal

Add a repository workflow for computing code distance from an existing finite CSS instance stored in the structured Zoo layer, then recording the result on that instance.

This design also extends the existing `generate-code-instance` skill so that new instances can optionally compute code distance immediately after generation when the instance size is small enough.

## Scope

This design covers:

- one new project-level skill for computing code distance on an existing instance
- one Julia helper script for running the distance computation through `tensorQEC.jl`
- one schema extension to record computed distance on `instance.json`
- one post-generation decision step in `generate-code-instance`
- loader, build, and rendering updates needed to tolerate and display the new field
- focused tests for schema, integration, and threshold behavior

## Non-Goals

- no support for arbitrary external matrix files in v1
- no standalone `distance.json` artifact in v1
- no automatic distance computation for large instances
- no background batch processing over many instances
- no change to canonical code cards or paper evidence records

## Main Decision

The workflow will use a separate project skill, `compute-code-distance`, and keep it distinct from `generate-code-instance`.

The reason is structural:

- computing distance for an existing instance is a real standalone workflow
- new-instance generation and post-generation evaluation are related but not identical tasks
- a dedicated distance skill can be reused later for backfilling older instances without regenerating them

The `generate-code-instance` skill remains the creation entry point, but gains a narrow optional post-step that asks whether to compute distance when the generated instance is below a size threshold.

## Data Contract

### Instance Storage

Distance is stored directly on `instance.json` under:

```json
"derived_properties": {
  "n": 17,
  "kx": null,
  "kz": null,
  "mx": 8,
  "mz": 8,
  "distance": 3
}
```

### Field Choice

The new field lives in `derived_properties.distance`, not in `provenance` and not in a separate top-level block.

This treats distance the same way as `n`, `mx`, and `mz`: it is an instance property derived from the stored parity-check matrices and intended for later display and querying.

### Schema Rules

`zoo/schemas/code-instance.schema.json` will be extended so that:

- `derived_properties.distance` is required
- allowed type is `integer` or `null`
- if integer, it must be at least `1`

Semantics:

- `null` means not computed or not yet known
- a positive integer means a completed distance computation has been recorded

### Default Value

Newly generated instances will write:

```json
"distance": null
```

This keeps the schema explicit and avoids ambiguity between "field absent" and "not computed yet".

## Skill Design

### New Skill: `compute-code-distance`

Location:

```text
.claude/skills/compute-code-distance/SKILL.md
```

#### Goal

Compute the code distance for an existing Zoo instance and write the result back to that instance's `instance.json`.

#### Input Boundary

V1 operates on an existing instance under:

```text
zoo/codes/<code-id>/instances/<instance-id>/
```

The skill should accept an instance identity the user can specify naturally, such as:

- exact `instance id`
- exact instance directory path

It should not accept arbitrary external matrix files in v1.

#### Workflow

1. Confirm that `julia/tensorqec_env/` is already set up. If not, stop and point the user to `setup-tensorqec`.
2. Resolve the target instance directory.
3. Read `instance.json`, `hx.json`, and `hz.json`.
4. Validate that the instance is a finite CSS instance with the expected matrix artifacts.
5. Check `derived_properties.distance`.
6. If a distance value already exists, ask whether to overwrite it.
7. Run the Julia distance-computation script.
8. Parse the returned distance result.
9. Update `instance.json` in place with the computed distance.
10. Report the instance id, path, `n`, and computed distance.

#### Rules

- Do not edit `card.json`.
- Do not create evidence records under `zoo/evidence/`.
- Do not overwrite an existing recorded distance without explicit user confirmation.
- Do not partially write results if the Julia computation fails.

### Existing Skill: `generate-code-instance`

The skill remains responsible for creating a new instance bundle.

After successful generation, it gains one additional decision point based on the generated instance's qubit count:

- if `derived_properties.n <= 200`, ask the user whether to compute code distance now
- if `derived_properties.n > 200`, do not ask; report that automatic distance computation is skipped because the instance exceeds the threshold

If the user agrees and `n <= 200`, the skill should invoke the same distance-computation path used by `compute-code-distance`.

This keeps one implementation path for distance calculation while leaving generation as the primary responsibility of the original skill.

## Threshold Policy

The automatic decision policy uses `derived_properties.n`, the number of qubits.

Threshold:

- auto-offer distance computation when `n <= 200`
- auto-skip when `n > 200`

This is intentionally a policy on qubit count only. V1 does not try to estimate cost from check count, sparsity, or code family.

The threshold affects only the post-generation prompt behavior. It does not forbid a user from explicitly running `compute-code-distance` on a larger instance later, unless implementation work chooses to add a separate warning.

## Julia Support Layer

Add a new script:

```text
julia/tensorqec_env/scripts/compute_distance.jl
```

Responsibilities:

- read `hx.json` and `hz.json`
- reconstruct the CSS representation needed by `tensorQEC.jl`
- call the relevant `tensorQEC.jl` distance-computation routine
- emit a small JSON result for the caller to consume

Expected output shape:

```json
{
  "distance": 3
}
```

The Julia script should not mutate Zoo files directly. File updates remain controlled by the calling workflow layer.

## Repository Integration

### Source Data

The following source-of-truth records are affected:

- `.claude/skills/compute-code-distance/SKILL.md`
- `.claude/skills/generate-code-instance/SKILL.md`
- `julia/tensorqec_env/scripts/compute_distance.jl`
- `julia/tensorqec_env/scripts/support.jl`
- `zoo/schemas/code-instance.schema.json`

### Python Layer

The Python Zoo layer must be updated so the new schema contract is fully supported:

- `src/autoqec_zoo/load.py` should accept and validate the new `distance` field
- rendering/build code should tolerate `null` and display an integer distance when present

The change should remain backward-compatible with the repository after source records are regenerated or test fixtures are updated.

## Error Handling

The workflow should distinguish policy skips from actual failures.

### Stop Conditions

Stop without writing updates when:

- `julia/tensorqec_env/` is not ready
- the target instance cannot be found
- `instance.json`, `hx.json`, or `hz.json` is missing
- the instance does not match the finite CSS storage contract
- the Julia distance computation fails
- the Julia output is malformed or does not contain a valid positive integer distance

### Non-Error Skip

For `generate-code-instance`, the case `n > 200` is not an error. It should be reported as a policy-based skip.

### Existing Distance

If `derived_properties.distance` already has a value:

- `compute-code-distance` asks whether to overwrite it
- `generate-code-instance` should not hit this case for a fresh instance, but the shared update helper may still defend against it

### Partial Success

If instance generation succeeds and distance computation fails afterward, the overall result is:

- instance creation: success
- distance computation: failure

The stored instance remains valid with `distance: null`.

## Testing

### Schema Tests

Add or update tests so that:

- `distance: null` is valid
- `distance: 3` is valid
- `distance: 0` is invalid
- missing `distance` is invalid once the schema is updated

### Integration Tests

Add a focused integration path using a very small known code instance, such as a small surface-code fixture:

- generated instance starts with `distance: null`
- distance workflow computes a known positive integer
- the updated `instance.json` remains loadable by the Python data layer

### Loader and Build Tests

Update existing tests so derived views continue to build when:

- some instances have `distance: null`
- some instances have an integer distance

### Skill-Contract Coverage

Add tests or document assertions that confirm:

- `generate-code-instance` offers distance computation only when `n <= 200`
- `generate-code-instance` skips the prompt when `n > 200`
- `compute-code-distance` does not silently overwrite an existing value

## Minimal Implementation Shape

The implementation should stay narrow:

- one new skill
- one new Julia script
- one schema extension
- one small update to generation skill flow
- targeted loader/build/render changes
- focused tests

No broader instance-evaluation framework is needed in this pass.

## Success Criteria

This design is successful when the repository can do all of the following:

- generate a new supported finite CSS instance with `distance: null`
- offer optional distance computation for new instances with `n <= 200`
- skip the post-generation prompt for new instances with `n > 200`
- compute distance later for a chosen existing instance
- persist the result at `derived_properties.distance`
- validate, load, and render instances whether distance is present or still null
