# Issue 92: Quantum Tanner Proposal Observable Completion Design

## Goal

Complete `observables_x.json` for proposal-derived quantum Tanner explicit
instances so the CSS memory-X benchmark path receives exactly `k` valid,
independent logical-X observable rows.

## Scope

Add a focused CLI command,
`complete-quantum-tanner-proposal-observables`, that operates on imported
proposal-derived explicit candidates in a `search_space.json`. Each candidate
must provide an X-like upper-bound witness through `upper_bound_witness_path`.
For every accepted candidate, the command writes `observables_x.json`, updates
`instance.json.artifacts.observables_x` to `observables_x.json`, and writes
`observables_x_provenance.json` beside the instance artifacts.

The command does not compute exact distance, run rbposd, call a live proposal
generator, or promote upper-bound evidence into exact-distance fields. It only
uses the verified witness as a seed for completing a benchmark observable
basis.

## Approaches Considered

1. Add a focused completion command after proposal import. This is the chosen
   approach because witnesses may arrive after #90 materialization and #91
   import, and it keeps materialization distance-neutral.
2. Extend the proposal importer to complete observables automatically. This
   would couple search-space import to witness availability and make it harder
   to import proposal bundles before screening data exists.
3. Extend the materializer to call witness or observable logic. This would mix
   qec-code matrix export with logical-observable completion and would make
   materialization depend on inputs outside the validated proposal.

## Data Flow

1. The command resolves `--root` and loads `--search-space`. The search-space
   schema allows `upper_bound_witness_path` on explicit-instance candidates so
   proposal-derived candidates can carry the same witness reference already
   used by catalog-backed quantum Tanner screening.
2. The command selects explicit candidates with `provenance.kind:
   "proposal-derived"`. Candidates without `instance_path` are ignored because
   they are not proposal-derived materialized bundles.
3. For each selected candidate, `resolve_campaign_candidate_spec(...)` loads
   the instance bundle. The candidate must resolve to
   `code_family: "quantum-tanner-code"` and `source_kind:
   "explicit-zoo-instance"`.
4. The command loads the candidate witness from `upper_bound_witness_path`.
   The witness is verified with the existing `verify_css_upper_bound_witness`
   path. The requested command basis is `x`; any Z-like or otherwise
   incompatible witness fails before rbposd can run.
5. The verified X vector is passed to the existing #82
   `complete_logical_observable_basis` helper. Matrix conversion between
   sparse-row artifacts and dense GF(2) rows is an adapter detail; quotient
   basis completion remains centralized in the shared helper.
6. The completed dense rows are converted to the existing
   `{"format": "sparse_rows", "num_cols": n, "rows": [...]}` observable
   artifact shape.
7. The command validates the final observable rows before writing: row count is
   exactly `k = n - rank(HX) - rank(HZ)`, every row lies in `ker(HZ)`, and the
   rows are independent modulo `rowspan(HX)`.
8. Writes are staged per instance. Without `--force`, existing
   `observables_x.json` or `observables_x_provenance.json` causes a nonzero
   failure. With `--force`, the command replaces only those completion
   artifacts and the `instance.json` artifact reference.

## Provenance

`observables_x_provenance.json` records deterministic completion metadata:

- method: `complete_logical_observable_basis`
- method_version: `quantum-tanner-proposal-observables-v1`
- basis: `x`
- candidate id and proposal id when present
- input witness source path and witness basis
- command options: root, search-space path, basis, force
- matrix dimensions and computed `k`
- row count and SHA-256 hash of `observables_x.json`

This sidecar is not distance evidence. It records only how benchmark
observables were completed.

## Failure Handling

The command fails before writing for missing or unsafe witness paths, malformed
witness payloads, non-X witness basis for memory-X completion, invalid CSS
matrices, noncommuting CSS checks, zero or negative logical dimension, an
incomplete observable set, or rows that are not valid logical-X rows. The
incomplete-row error uses the existing text:

```text
explicit X observables define 1 rows, expected k = 2
```

The CLI exits nonzero with actionable stderr and prints no partial success for
a failed candidate. Existing artifacts are preserved unless `--force` is set.

## Testing

Add `tests/test_search_quantum_tanner_proposal_observables.py` covering:

- a positive temporary workspace where a proposal-derived `k = 2` instance,
  imported search space, and X witness produce `observables_x.json`, update
  `instance.json.artifacts.observables_x`, validate both rows as X logicals,
  and resolve with `candidate.observables_x` present;
- an incomplete-row negative control that validates an explicit one-row
  observable payload for the same `k = 2` instance and fails with
  `explicit X observables define 1 rows, expected k = 2`;
- a wrong-basis negative control where a Z-like witness for memory-X completion
  exits nonzero before rbposd is called.

Run the issue-specified focused tests, `PYTHONPATH=src python3 -m pytest`, and
a temporary-workspace `validate --root` check after observable completion.

## Self-Review

- No placeholders remain.
- The design reuses the #82 logical-basis completion helper and does not add a
  second GF(2) quotient-basis implementation.
- Proposal-derived bundles stay search artifacts, and exact distance remains
  unknown.
- The command is conservative about overwrites and validates observable
  semantics before writing.
