# Issue #15 Distance Method Registry Completion Design

## Goal

Complete the AutoQEC side of issue #15 by turning the current distance handling
into an exact-first distance-method registry with a normalized, auditable
`distance.json` contract.

The implementation should align with the latest issue discussion: AutoQEC should
standardize exact distance result records, preserve safe downstream behavior,
and be ready to consume `rstim` exact/ILP distance once that CLI or API contract
is stable. Randomized upper-bound search remains an `rstim` backend concern and
must not be presented as the second AutoQEC method for closing this issue.

## Scope

In scope:

- keep `src/autoqec_search/distance_methods.py` as the registry boundary
- keep `copied-zoo-exact` as the default exact method for existing curated
  instances with recorded exact distances
- normalize every completed exact `distance.json` payload to include
  `distance`, `method`, `bound_type`, `options`, and `provenance`
- add a named `rstim-ilp-exact` registry entry only as a guarded external exact
  backend, with a clear unavailable/unsupported error until a stable exact CSS
  distance command is available
- reject any randomized or upper-bound payload that is missing explicit
  `bound_type: "upper"` or has inconsistent `distance`/`upper_bound` fields
- keep report readers compatible with old exact payloads while never promoting
  unknown or heuristic payloads to exact
- keep promotion exact-only by default
- update README and CLAUDE guidance to match the exact-first scope
- update PR #34 semantics so it no longer claims randomized upper bounds close
  issue #15
- add regression tests for the upper-bound misclassification bug and the exact
  result contract

Out of scope:

- implementing randomized upper-bound search inside AutoQEC
- treating `randomized-upper-bound` as a first-class `autoqec-search eval/run`
  distance method for this issue
- adding a native Python ILP solver stack
- changing the Zoo source-of-truth schema for curated instance distances
- recomputing or replacing committed M1 demo search results
- closing the separate `rstim` randomized-upper-bound work

## Main Decision

Use an exact-first registry and remove the randomized method from the AutoQEC
CLI surface for issue #15.

The current PR already made a useful boundary in
`autoqec_search.distance_methods`, but it overreached by wiring
`randomized-upper-bound` through `autoqec-search eval` and `run`. That creates a
scope mismatch with the latest issue comments and introduces a safety bug:
legacy fallback logic can coerce a randomized payload without `bound_type` into
`exact`.

The corrected design keeps the registry, hardens the payload loader, and makes
the external exact backend a guarded registry entry rather than a heuristic
stand-in.

## Registry Contract

`DistanceMethodOptions` should describe exact method selection:

- `method`
- `qec_code_bin`
- backend-specific exact options such as `backend`, `timeout_seconds`, or
  `solver` only when they are supported

Supported method names for this issue:

- `copied-zoo-exact`
- `rstim-ilp-exact`

`copied-zoo-exact`:

- reads `candidate.instance.derived_properties.distance`
- requires that value to be a positive integer
- emits `bound_type: "exact"`
- does not require `qec-code`
- records source instance id/path in provenance

`rstim-ilp-exact`:

- converts dense AutoQEC `hx`/`hz` matrices to the sparse-row JSON contract
  expected by `qec-code`
- probes for a stable exact CSS distance command before running
- if the command is unavailable, fails with a clear message such as
  `rstim exact CSS distance backend is not available; use copied-zoo-exact for
  recorded instances or install a qec-code build with exact CSS distance`
- when a stable exact backend exists, accepts only JSON results with
  `bound_type: "exact"`
- rejects heuristic or upper-bound results from this method path

The local sibling `rstim` checkout currently exposes
`code css-distance randomized-upper-bound` and exact distance internals, but not
a stable general CSS exact-distance CLI command. The AutoQEC implementation
should reflect that reality instead of inventing an unsupported command.

## Distance Payload Contract

Every newly written completed exact payload should look like:

```json
{
  "status": "completed",
  "distance": 3,
  "method": "copied-zoo-exact",
  "bound_type": "exact",
  "options": {
    "method": "copied-zoo-exact"
  },
  "provenance": {
    "source": "zoo-instance",
    "source_instance_id": "rotated-surface-code-d3",
    "source_instance_path": "zoo/codes/rotated-surface-code/instances/rotated-surface-code-d3"
  }
}
```

Backward compatibility rules:

- legacy `copied-from-zoo-instance` payloads remain exact
- legacy completed integer-distance payloads may be treated as exact only when
  no known heuristic method is present
- `method: "randomized-upper-bound"` without `bound_type: "upper"` is invalid
- `bound_type: "upper"` requires a positive `upper_bound`
- for upper-bound payloads, `distance` may be absent or equal to `upper_bound`
  for compatibility, but it must never be treated as exact

## Eval And Run Data Flow

For `autoqec-search eval`:

1. parse `--distance-method`, defaulting to `copied-zoo-exact`
2. normalize method options once in the CLI layer
3. resolve the candidate and validate CSS structure
4. compute or copy the distance payload through the registry
5. use the exact distance for rounds, `rsinter` spec generation, manifest
   validation, and plots
6. write artifacts and the normalized `distance.json`

For `autoqec-search run`:

1. persist distance-method metadata into `env.json`
2. resume existing runs with their recorded distance-method metadata
3. evaluate each candidate through the same registry path as `eval`
4. record crashes when an exact backend is unavailable or unsupported

`run_spec.json` does not need a new required field for this issue because the
existing run compatibility surface already has strategy-era metadata churn.
`env.json` is enough for run provenance and resume behavior.

## Report And Promotion Behavior

Reports should expose:

- `distance`
- `distance_method`
- `distance_bound_type`

Reports may render legacy completed exact payloads, but invalid heuristic
payloads should fail fast rather than silently downgrade safety.

Promotion should keep `require_distance_verified` defaulting to `true`. With
that setting:

- candidate distance status must be `completed`
- `bound_type` must be `exact`
- `distance.json`, candidate parameters, frontier item, and instance
  `derived_properties.distance` must agree

With `require_distance_verified: false`, promotion may still require positive
distance consistency, but should not write an upper bound into Zoo
`derived_properties.distance` as if it were exact.

## Error Handling

Errors should be specific and actionable:

- unknown method: `unknown distance method: <name>`
- missing recorded exact distance:
  `copied-zoo-exact requires instance derived_properties.distance`
- unavailable external backend:
  `rstim exact CSS distance backend is not available`
- malformed upper-bound payload:
  `randomized-upper-bound distance payload must use bound_type upper`
- unsafe promotion:
  `candidate <id> promotion requires an exact distance`

The implementation should avoid broad fallback behavior that guesses exactness
from `status: completed` alone when a known non-exact method is present.

## Verification

Automated verification:

- unit tests for `normalize_distance_method_options`
- exact payload contract tests for `copied-zoo-exact`
- loader tests proving randomized payloads cannot be classified as exact
- eval CLI tests proving the default exact payload includes options and
  provenance
- run-loop tests proving method metadata persists and resumes
- promotion tests proving explicit and malformed upper-bound payloads are
  rejected when verification is required
- report tests proving method and bound type are exposed

Human verification for issue #15:

- document a known-distance table in test output or fixtures for rotated
  surface `d = 3, 5, 7`
- include the bivariate bicycle `[[72,12,6]]` fixture only if an exact backend
  is available locally; otherwise record the precise unavailable-backend result
  and leave the external exact backend as a guarded follow-up
- run:

```bash
PYTHONPATH=src python3 -m pytest tests -q
PYTHONPATH=src python3 -m autoqec_search.cli validate --root .
```

## Completion Criteria

Issue #15 is complete for AutoQEC when:

- PR #34 no longer exposes randomized upper bounds as the AutoQEC method that
  closes the issue
- all new exact payloads contain method, bound type, options, and provenance
- legacy exact payloads still read
- known upper-bound or randomized payloads cannot be promoted or reported as
  exact by omission
- unsupported exact backends fail clearly
- docs describe the exact-first registry and the external `rstim` boundary
- tests and workspace validation pass
