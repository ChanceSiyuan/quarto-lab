# Issue #12 Zoo Promotion Design

## Goal

Close the M1 autoresearch loop by promoting accepted search candidates into the
curated `zoo/` layer when explicit promotion rules pass.

The feature adds a reviewable but automatic path:

```text
finished autoresearch run + promote_rules.json
  -> evaluate frontier candidates
  -> copy accepted instances into zoo/codes/<code>/instances/<candidate_id>/
  -> rebuild Zoo views and static site
  -> commit everything on autoresearch/<tag>
```

Promotion is automatic once rules are present. The safety valve is the ruleset
and overwrite protection, not a manual click. Autoresearch branches remain local
review branches; nothing is pushed.

## Scope

In scope:

- `benchmarks/schemas/promote-rules.schema.json`
- campaign-local `promote_rules.json`
- CLI command:

  ```bash
  autoqec-search promote --root . --run results/search/<campaign>/<run-id>
  ```

- optional `--rules <path>` override for one-off checks
- optional `--force` for explicit replacement of an existing promoted instance
- promotion evaluator for:
  - `min_distance`
  - `max_ler_at_p: {p, ler}`
  - `require_distance_verified`
- copying accepted candidate `instance.json`, `hx.json`, and `hz.json` into
  `zoo/codes/<code_family>/instances/<candidate_id>/`
- using the run candidate id as the promoted Zoo instance id
- adding autoresearch provenance to promoted instance payloads
- writing `promotion_summary.json` inside the run directory
- rebuilding the Zoo with `autoqec_zoo.build.build_zoo`
- automatic promotion at the end of `autoqec-search run` when rules are present
- tests for accepted, rejected, missing-rules, overwrite, and invalid-Zoo cases
- documentation updates in `README.md`, `CLAUDE.md`, and docs tests

Out of scope:

- drafting full benchmark-derived evidence records
- changing canonical code card facts from benchmark results
- comparing candidates across independent runs
- pushing or opening pull requests for autoresearch branches
- promoting candidates that do not have complete `artifacts/`
- supporting families beyond the existing stored CSS instance layout
- changing the `autoqec-zoo build` CLI contract

## Main Decision

Implement promotion as a new `autoqec_search.promote` module used by both a new
CLI command and the autoresearch finalization path.

This keeps boundaries clear:

- `run_loop.py` owns worktree orchestration, candidate evaluation, reports, and
  final commits.
- `promote.py` owns rule loading, rule evaluation, safe copying, provenance, and
  Zoo rebuild.
- `autoqec_zoo.build` remains a pure builder from curated source files to
  derived views.

The alternative of embedding promotion directly into `run_loop.py` would make
manual re-runs and focused failure tests awkward. The alternative of teaching
`autoqec-zoo build` to read search runs would blur the distinction between
curated source data and search artifacts.

## Rule Location

Campaigns keep promotion policy in a sibling file:

```text
campaigns/examples/<campaign-id>/promote_rules.json
```

The campaign schema remains focused on campaign intent. A separate rules file
also lets local experiments tighten or loosen promotion without rewriting the
core campaign metadata.

The CLI resolves rules in this order:

1. `--rules <path>`, resolved from the current working directory unless
   absolute.
2. `promote_rules.json` next to the campaign's `campaign.json`.
3. no rules: promotion is skipped and recorded as `skipped_no_rules`.

Missing rules are not an error for `autoqec-search run`; they are an explicit
skip. Missing rules are also a clean no-op for `autoqec-search promote`, so a
script can safely call promote on any run and inspect the summary.

## Rule Schema

The MVP schema is strict and small:

```json
{
  "min_distance": 3,
  "max_ler_at_p": {
    "p": 0.005,
    "ler": 0.5
  },
  "require_distance_verified": true
}
```

Rules:

- `min_distance`: optional positive integer. A candidate passes only when its
  recorded distance is at least this value.
- `max_ler_at_p`: optional object with `p` and `ler`. A candidate passes only
  when its frontier manifest contains an exact point for this physical error
  rate and that point's LER is at most the limit.
- `require_distance_verified`: optional boolean, default `true`. When true,
  `distance.json` must have `status: "completed"` and a positive integer
  `distance`.

The schema uses `additionalProperties: false`. Invalid rules fail loudly before
any Zoo files are written.

## Promotion Inputs

Promotion reads a finished run directory:

```text
results/search/<campaign>/<run-id>/
  run_spec.json
  frontier.json
  leaderboard.csv
  candidates/<candidate-id>/
    candidate.json
    distance.json
    artifacts/
      instance.json
      hx.json
      hz.json
    evaluations/<task-id>/<decoder-id>/manifest.json
```

`frontier.json` is the candidate selection source. Only frontier candidates are
eligible; discarded and crashed candidates are ignored even if they appear in
other run files.

For each frontier item, promotion validates:

- candidate id is a safe single path segment
- candidate payload matches the run campaign id
- candidate status is `evaluated`
- candidate artifacts exist
- artifact `code_id` matches `candidate.json.code_family`
- artifact parameters match `candidate.json.parameters`
- `distance.json` matches the rule's distance requirement
- the frontier manifest exists and contains the LER point required by the rules

These checks deliberately duplicate some loader expectations near the trust
boundary. Promotion copies data into curated storage, so it should reject stale
or inconsistent run artifacts before touching `zoo/`.

## Instance Id And Payload

The promoted Zoo instance id is exactly the run `candidate_id`.

Example:

```text
results/.../candidates/rotated-surface-d3-example/
  -> zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/
```

The copied `instance.json` is rewritten only where promotion changes identity
or provenance:

- `id`: set to `candidate_id`
- `code_id`: preserved from the artifact
- `family_id`: preserved from the artifact
- `title`: preserved when present; otherwise generated from code id and
  distance
- `parameters`: preserved
- `derived_properties`: preserved, including the recorded distance
- `artifacts`: preserved as `{"hx": "hx.json", "hz": "hz.json"}`
- `provenance`: extended with:
  - `promoted_by: "autoqec-search promote"`
  - `promoted_at`
  - `source_run`
  - `source_candidate_id`
  - `source_manifest_path`
  - `promote_rules`

`hx.json` and `hz.json` are copied byte-for-byte after JSON validation by the
existing Zoo loader during rebuild.

## Overwrite Safety

By default, promotion never overwrites an existing curated instance directory.

If `zoo/codes/<code>/instances/<candidate_id>/` already exists, the candidate is
recorded as `failed_existing_instance` and the command exits nonzero after
writing no changed Zoo files for that candidate.

`--force` allows replacement of the exact target instance directory. It is
intended for rerunning a local autoresearch branch after fixing promotion logic.
Even with `--force`, the rebuilt Zoo must validate successfully before the
command reports success.

The MVP implementation should stage each promoted instance in a temporary
directory under the target `instances/` parent, then atomically install it. On
failure, partial target directories should not remain.

## Zoo Rebuild

After at least one candidate is promoted, promotion calls:

```python
build_zoo(root / "zoo", generated_at=date.today().isoformat())
```

This regenerates:

- `zoo/views/instance-index.json`
- `zoo/views/browse.md`
- `zoo/views/site/`
- `zoo/codes/**/card.md`

If the Zoo loader or view schemas reject the promoted data, promotion fails
loudly. The run branch should then show the candidate artifacts and failure
context, but no successful promotion summary.

## Promotion Summary

Every invocation writes:

```text
results/search/<campaign>/<run-id>/promotion_summary.json
```

The summary is deterministic and includes:

- campaign id
- run id
- generated timestamp
- rules path or `null`
- rules payload or `null`
- `force`
- promoted candidates with target instance paths
- skipped candidates with reason
- failed candidates with reason

When no rules are found, the summary contains no promoted candidates and one
run-level status `skipped_no_rules`. This makes automatic run finalization
auditable without turning missing rules into a crash.

## CLI Behavior

Add:

```bash
autoqec-search promote --root . --run results/search/<campaign>/<run-id>
```

Options:

- `--root <path>`: repository root; default `.`
- `--run <path>`: required run directory
- `--rules <path>`: optional rules file override
- `--force`: allow replacing existing target instance ids

If `--run` is relative, resolve it from the current working directory, matching
the existing `report` command behavior. The command still uses `--root` for
campaign metadata, schemas, and the Zoo root.

Exit behavior:

- `0`: rules were missing and promotion skipped, or all eligible candidates were
  cleanly promoted/skipped by rule evaluation.
- `1`: invalid run, invalid rules, missing artifacts, overwrite refusal,
  inconsistent candidate data, or Zoo rebuild failure.

The command prints a concise summary such as:

```text
promotion complete for rotated-surface-baseline/fixed-check: 1 promoted, 1 skipped
```

or:

```text
promotion skipped for rotated-surface-baseline/fixed-check: no promote_rules.json
```

## Autoresearch Integration

`autoqec-search run` invokes promotion during finalization after writing the
visual `report.html` and before the final commit.

The finalization order becomes:

1. write aggregate files
2. write `run_status.json`
3. write `report.html`
4. run promotion if rules are available
5. rebuild Zoo if promotion copied at least one instance
6. commit final artifacts on `autoresearch/<tag>`

If rules are missing, step 4 writes a skip summary and the run still finalizes.
If rules are invalid or promotion fails, the run command fails rather than
silently producing an apparently successful branch with broken curated data.

With `--cleanup-worktree`, the worktree is removed only after the final commit
that includes promotion outputs.

## Error Handling

Promotion failures should be explicit and actionable:

- invalid rules: include the schema validation path and message
- no frontier file or malformed frontier: identify the run path
- missing candidate artifacts: identify the candidate and missing file
- missing exact `p` point for `max_ler_at_p`: skip the candidate with a reason
  when the manifest is otherwise valid
- malformed manifest or inconsistent candidate identity: fail the command
- existing target instance without `--force`: fail the command
- Zoo rebuild failure: fail the command with the underlying Zoo integrity error

Rule-based rejection is a skip, not a failure. Data inconsistency is a failure.

## Testing

Add focused unit tests for `autoqec_search.promote`:

- schema accepts the documented rule shape
- schema rejects unknown keys and invalid probabilities/rates
- evaluator accepts a d=3 frontier candidate under
  `{min_distance: 3, max_ler_at_p: {p: 0.005, ler: 0.5}}`
- evaluator rejects the same candidate under `min_distance: 5`
- evaluator skips when the requested LER point is absent
- target instance payload rewrites `id` to `candidate_id` and preserves
  parameters and derived properties
- existing target instance fails without `--force`

Add CLI/integration tests using the existing fake-`rsinter` temporary repository
pattern:

- `autoqec-search promote` copies the kept d=3 candidate into
  `zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/`
- rebuilt `zoo/views/instance-index.json` includes the promoted id
- rebuilt `zoo/codes/rotated-surface-code/card.md` includes the promoted id
- tightened rules produce no target instance and no browse/card entry
- `autoqec-search run` writes `promotion_summary.json` and commits promoted Zoo
  files on `autoresearch/<tag>` when rules are present
- missing rules during `run` writes a skip summary and still finalizes

The existing checked-in example run is placeholder-only and should not be the
primary positive fixture. End-to-end tests should use fake `rsinter` to generate
real candidate artifacts, completed manifests, frontier data, and report files.

## Documentation

Update `README.md` and `CLAUDE.md` to document:

- campaign-local `promote_rules.json`
- `autoqec-search promote`
- automatic promotion at the end of `autoqec-search run`
- no-overwrite default and `--force`
- promoted instances becoming visible through `zoo/views/browse.md`,
  `zoo/views/instance-index.json`, and the static site

Extend `tests/test_search_docs.py` so docs coverage tracks the new CLI and the
automatic run behavior.

## Completion Criteria

Issue #12 is complete when:

- `python3 -m autoqec_search.cli promote --root . --run <finished-run>` works
  on an autoresearch run with passing rules
- the d=3 kept candidate is copied to
  `zoo/codes/rotated-surface-code/instances/<candidate_id>/`
- `autoqec_zoo.build.build_zoo` exits successfully after promotion
- `zoo/views/instance-index.json`, `zoo/codes/rotated-surface-code/card.md`,
  and `zoo/views/site/index.html` expose the promoted instance
- tight rules such as `min_distance: 5` block the d=3 candidate
- existing target ids are not overwritten without `--force`
- `autoqec-search run` performs the same promotion on the autoresearch branch
  when rules are present
- docs and tests cover the new behavior
