# Issue 56 Quantum Tanner Sweep Contract Design

Issue: #56, "[M3] Add a quantum Tanner sweep configuration contract"

## Context

The repository already has a strict quantum Tanner fixture catalog validator in
`src/autoqec_search/quantum_tanner_catalog.py` and a committed
`campaigns/examples/quantum-tanner-autoresearch/search_space.json` with the
hand-authored d4/d6/d8 candidate list. Issue #55 generalized non-default
fixture catalog validation, but operators still lack a small source config that
describes which generated toric candidates should exist and where the later
generator should write specs, instances, catalog, and search-space records.

This issue defines only the input contract and validator. It does not generate
matrices, call `qec-code`, write a catalog, or edit `search_space.json`.

## Non-Interactive Decisions

This Agent Desk run is non-interactive, so the standing policy resolves choices
from the issue text and repository context.

1. Add `src/autoqec_search/quantum_tanner_generator.py` for the sweep config
   parser, validator, normalized dataclasses, and CLI summary rendering.
2. Add a top-level CLI subcommand named `validate-quantum-tanner-sweep` with
   `--config <path>`, matching the issue's proposed command exactly.
3. Treat every example field except `qec_code_bin` as required:
   `campaign_id`, `distances`, `code_id`, `output_root`, `spec_root`,
   `instance_root`, `catalog_path`, `search_space_path`, and
   `expected_bound_type`.
4. Default omitted `qec_code_bin` to `qec-code`.
5. Accept `expected_bound_type` values `exact` and `upper`, matching the
   existing distance payload vocabulary.
6. Validate paths as repository-relative contract paths: reject absolute paths,
   empty/current-directory values, and any `..` segment. The validator does not
   require the paths to exist because this is pre-generation configuration.
7. Reject duplicate distances before sorting so `[4, 4]` is visibly invalid
   instead of silently normalizing away operator intent.
8. Reject bools as non-integer distances because Python `bool` is an `int`
   subclass but JSON `true` is not a distance.

## Approaches Considered

Recommended: add a focused sweep contract module and CLI validator. This keeps
the generated-input contract separate from fixture-catalog validation while
exposing normalized metadata that later generator issues can consume directly.

Alternative: extend `quantum_tanner_catalog.py`. That file validates generated
catalog entries and matrix artifacts; putting source sweep intent there would
mix two different lifecycle stages.

Alternative: add only a JSON Schema. A schema could reject some malformed
payloads, but it would not produce deterministic candidate ids or per-candidate
output paths for later generator steps.

## Contract

The minimal valid JSON object is:

```json
{
  "campaign_id": "quantum-tanner-autoresearch",
  "distances": [4, 6],
  "code_id": "quantum-tanner-code",
  "output_root": "campaigns/examples/quantum-tanner-autoresearch/generated",
  "spec_root": "campaigns/examples/quantum-tanner-autoresearch/generated/quantum_tanner_specs",
  "instance_root": "benchmarks/distance_ladders/generated-quantum-tanner/instances",
  "catalog_path": "campaigns/examples/quantum-tanner-autoresearch/generated_fixture_catalog.json",
  "search_space_path": "campaigns/examples/quantum-tanner-autoresearch/generated_search_space.json",
  "expected_bound_type": "exact",
  "qec_code_bin": "qec-code"
}
```

`qec_code_bin` is optional and normalizes to `qec-code` when omitted.

The normalized object includes:

- sorted `distances`;
- safe path strings for every root/path field;
- `expected_bound_type`;
- `qec_code_bin`;
- one candidate record per distance with deterministic ids such as
  `quantum-tanner-toric-d4`;
- per-candidate `qec_code_spec`, spec path, instance directory, instance JSON
  path, `hx.json`, and `hz.json` paths.

## CLI Behavior

`PYTHONPATH=src python3 -m autoqec_search.cli validate-quantum-tanner-sweep --config <path>`
loads the JSON file, validates it, normalizes it, and prints a reviewer-readable
summary. The summary includes the campaign id, code id, output roots, catalog
and search-space paths, expected bound type, qec-code binary, and candidate
lines. For `[4, 6]`, the candidate lines contain exactly
`quantum-tanner-toric-d4` and `quantum-tanner-toric-d6`.

Invalid configs exit nonzero through the existing CLI error path. Error
messages include the invalid field name, for example `distances` for duplicate
or non-integer distances and `catalog_path` for unsafe path traversal.

## Testing

Add `tests/fixtures/quantum_tanner_sweep/good.json` as a minimal valid config
fixture. Add `tests/test_search_quantum_tanner_generator.py` with module and
CLI tests for:

1. valid config normalization, sorted distances, candidate ids, and generated
   paths;
2. CLI success on the committed fixture;
3. duplicate distance rejection mentioning `distances`;
4. non-integer and `< 2` distance rejection mentioning `distances`;
5. unsafe path rejection mentioning the invalid path field.

Required verification:

```bash
PYTHONPATH=src python3 -m pytest tests/test_search_quantum_tanner_generator.py -q
PYTHONPATH=src python3 -m autoqec_search.cli validate-quantum-tanner-sweep --config /tmp/qt-sweep-good.json
PYTHONPATH=src python3 -m autoqec_search.cli validate-quantum-tanner-sweep --config /tmp/qt-sweep-bad.json
PYTHONPATH=src python3 -m pytest
```

## Self-Review

No placeholders remain. The design implements the issue's input-output
contract, keeps matrix generation out of scope, and covers both requested
positive and negative CLI controls.
