# Issue 91: Quantum Tanner Proposal Import Design

## Goal

Import proposal-derived quantum Tanner materialization bundles into campaign
`search_space.json` files as explicit AutoQEC candidates that validate and
resolve through the existing explicit-instance path. The import must preserve
proposal provenance and keep unknown exact distance as `null`.

## Scope

The CLI accepts a repository root, a campaign id, an output `search_space.json`
path, and either a materialized instance root or a materialization manifest path.
It writes or updates an `explicit_list` search space whose imported candidates
have `code_family: "quantum-tanner-code"`, `instance_path`, and a proposal
provenance object linking to the source proposal, validator fingerprint,
qec-code spec, materialization manifest, output hashes, and materialization run
metadata.

The importer preserves unrelated existing candidates in the output search
space. Duplicate proposal or candidate fingerprints are rejected by default.
This issue does not add curated Zoo semantics, compute distance, run rbposd, or
promote upper-bound evidence into exact-distance fields.

## Approaches Considered

1. Add a focused search-space importer module and a thin CLI command. This is
   the chosen approach because it keeps proposal import separate from #90
   materialization, reuses explicit-instance candidates, and localizes duplicate
   fingerprint logic.
2. Extend the #90 materializer to also update search spaces. This would couple
   materialization and campaign import and make it harder to import existing
   bundles without rerunning qec-code.
3. Add a new proposal-derived candidate kind. This would expand the search
   runner surface unnecessarily when the existing explicit-instance path can
   already carry resolved CSS artifacts.

## Data Flow

1. Resolve the input source. `--instance-root` scans child directories that
   contain `instance.json` and `materialization_manifest.json`. `--manifest`
   imports the candidate directory adjacent to the manifest.
2. For each materialized bundle, load `instance.json`,
   `materialization_manifest.json`, `hx.json`, `hz.json`, and
   `qec_code_quantum_tanner_spec.json`.
3. Validate the bundle before writing a search-space candidate:
   candidate id alignment, quantum Tanner code id, required null exact-distance
   fields, manifest proposal id/fingerprint, validator fingerprint, qec-code
   spec presence, and output hashes.
4. Compute a stable candidate fingerprint from non-transient content: proposal
   fingerprint, validator fingerprint, CSS dimensions, output hashes, and
   normalized qec-code spec hash. Do not include absolute output paths.
5. Build an explicit-instance candidate with `instance_path` relative to the
   repository root and provenance fields under `provenance.proposal`.
6. Merge imported candidates into an existing search space if present, replacing
   prior candidates with the same candidate id only when the proposal/candidate
   fingerprints match exactly. Any duplicate proposal fingerprint or candidate
   fingerprint across distinct candidates fails the command.
7. Atomically write the updated search space and validate it with the local
   schema. The caller can then run `autoqec-search validate --root <workspace>`
   to prove schema validity and explicit instance resolution.

## Schema And Resolver Contract

`benchmarks/schemas/search-space.schema.json` gains a nested optional
`provenance.proposal` object for imported proposal-derived candidates. The
base provenance contract remains `kind` and `label`. The proposal object
requires the fields written by the importer: proposal id/fingerprint, validator
fingerprint, materialization manifest path, qec-code spec path, output hashes,
materializer version, exact-distance status, and stable candidate fingerprint.

The explicit-instance resolver must accept proposal-derived instances whose
`derived_properties.distance` and `parameters.distance` are `null`. For these
instances it returns `parameters.distance: None` instead of inventing a positive
distance. Existing Zoo-style explicit instances with exact distances keep the
current positive-distance normalization and mismatch checks.

`autoqec-search validate --root` must resolve every search-space candidate with
an `instance_path`, loading `instance.json`, `hx.json`, and `hz.json` and
checking path safety. It should not broaden validation for parameter-only
candidate specs in this issue.

## Failure Handling

Invalid input fails before writing a misleading candidate. The importer rejects
missing files, malformed JSON, unsafe output-relative paths, mismatched proposal
metadata, missing proposal provenance fields, and duplicate proposal/candidate
fingerprints. The CLI exits nonzero with actionable error text; duplicate
proposal fingerprints include the phrase `duplicate proposal fingerprint`.

## Testing

Add `tests/test_search_quantum_tanner_proposal_import.py` covering:

- importing one #90-style materialized bundle into a temporary campaign
  workspace, then proving `validate --root` exits 0 and
  `resolve_campaign_candidate_spec(...)` loads the imported instance and keeps
  exact distance unknown;
- duplicate proposal/candidate fingerprint rejection with a nonzero CLI result
  containing `duplicate proposal fingerprint`;
- schema/import negative control where removing required proposal provenance
  fields fails before or during validation instead of accepting a misleading
  candidate.

Run the three required issue tests, the full `PYTHONPATH=src python3 -m pytest`
suite, and a manual temporary-workspace `validate --root` check.

## Self-Review

- No placeholders remain.
- The design preserves existing explicit-instance candidate semantics.
- Proposal-derived bundles stay search artifacts and are not promoted into the
  curated Zoo.
- Unknown exact distance remains unknown in both imported candidates and
  resolved candidate parameters.
- Duplicate handling is conservative and rejects by default.
