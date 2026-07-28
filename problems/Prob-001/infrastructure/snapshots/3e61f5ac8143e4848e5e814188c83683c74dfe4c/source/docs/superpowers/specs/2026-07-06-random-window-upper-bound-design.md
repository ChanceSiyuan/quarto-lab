# Random Window Upper Bound Distance Method Design

## Context

Issue #42 adds a first-class search distance method named
`random-window-upper-bound`. The search layer already records exact method
metadata and rejects upper-bound payloads during promotion, but the method
registry only accepts exact methods and the loader only treats
`randomized-upper-bound` as a supported upper-bound payload.

## Approach Options

1. Add `random-window-upper-bound` as a named method in
   `autoqec_search.distance_methods`.
   This is the selected approach because the existing CLI and run paths already
   normalize distance methods through one registry.
2. Accept any method containing `upper`.
   This is rejected because the issue explicitly requires unknown names such as
   `some-upper-bound` to fail instead of being silently accepted.
3. Special-case upper bounds in the CLI only.
   This is rejected because reports, promotion, resume metadata, and direct API
   callers all load the same payloads outside the CLI.

## Selected Design

`autoqec_search.distance_methods` will define a canonical
`RANDOM_WINDOW_UPPER_BOUND` method. Normalization will accept only the exact
methods plus `random-window-upper-bound`, while preserving
`randomized-upper-bound` as a backward-compatible payload name. Method metadata
will report `bound_type: "upper"` for upper-bound methods and `bound_type:
"exact"` for exact methods.

Upper-bound payload generation will produce:

```json
{
  "status": "completed",
  "method": "random-window-upper-bound",
  "bound_type": "upper",
  "upper_bound": 5
}
```

When the candidate source already has a positive recorded
`derived_properties.distance`, that value is used as the screening upper bound.
The payload will not include `distance`, so downstream code cannot mistake the
screening result for an exact code distance.

## Data Flow

CLI `eval` and `run` commands pass `--distance-method` through
`normalize_distance_method_options`. Eval writes the method payload to
`distance.json` via the existing candidate artifact copy path. Autoresearch
`env.json` stores `distance_method` metadata, and reports expose
`distance_method` plus `distance_bound_type` from loaded candidate artifacts.

For fixed-round CSS tasks, a missing exact distance remains valid when
`upper_bound` exists. Exact-distance-scaled consumers continue to fail clearly
because `LoadedDistancePayload.distance` is `None` for the new upper-bound
method.

## Guardrails

Promotion remains exact-only through the existing `loaded.bound_type !=
"exact"` check. Payload validation continues to reject any method containing
`upper` when paired with `bound_type: "exact"`. Supported upper-bound payload
names are exactly `random-window-upper-bound` and the legacy
`randomized-upper-bound`; unknown upper-bound names are rejected.

## Tests

Add `tests/test_search_upper_bound_distance_method.py` with six checks:

- CLI normalization accepts `random-window-upper-bound` and records upper
  metadata.
- Candidate artifact writing produces `upper_bound` without an exact `distance`.
- Report models expose `distance_bound_type: "upper"`.
- Promotion rejects a candidate whose only distance payload is an upper bound.
- Corrupted upper-bound payloads with `bound_type: "exact"` are rejected.
- Unknown upper-bound method names such as `some-upper-bound` are rejected.
