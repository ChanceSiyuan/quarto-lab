# Issue #18 BB qLDPC Campaign Design

## Goal

Complete AutoQEC issue #18 by running the first bivariate-bicycle qLDPC
campaign end to end through the M2 search pipeline.

The completed work should produce:

- a paper-backed BB72 `[[72,12,6]]` finite CSS instance
- a BB campaign and benchmark suite using the general CSS rsinter path
- per-candidate manifests, leaderboard, frontier, run summary, and report
- exact-distance and published-reference validation artifacts
- promotion of the accepted BB instance into `zoo/codes/bivariate-bicycle-code`
- updated Zoo browse/index artifacts showing the promoted BB instance

The design intentionally separates fast software-contract checks from heavier
paper-reference numerical checks. That keeps the normal development loop
usable while preserving the verification teeth requested by issue #18.

## Upstream Status

The blocking rstim work has landed:

- `nzy1997/rstim#101`, merged via rstim PR #104, adds exact CSS distance output
  for `qec-code code css-distance exact`.
- `nzy1997/rstim#102`, merged via rstim PR #105, adds explicit logical
  observables for general CSS memory benchmarks.
- `nzy1997/rstim#103`, merged via rstim PR #107, adds BB72 BP+OSD rsinter
  benchmark support, `predict-zero`, seed/result provenance, and paper-facing
  rbposd parameter labels.

Local capability probes on 2026-06-18 found:

- `/Users/nzy/rcode/rstim` is on `master` at rstim PR #107.
- `cargo test -p qec-code --features distance-ilp-highs --test cli
  code_css_distance_exact_bb72_known_distance_with_ilp -q` passed in about
  149 seconds.
- `/Users/nzy/rcode/rstim/target/debug/rsinter` can run
  `rsinter/tests/fixtures/bench/bb72_css_bposd_decoder.toml`.
- That fast fixture emits `decoder_impl`, `seed`, `bp_algorithm`, `bp_iters`,
  `osd_method`, `osd_order`, explicit observable metadata, and
  `logical_failure_aggregation = "any_logical"`.
- The heavier manual paper-reference fixture is not suitable for interactive
  probing or routine fast CI.

The current PATH-level `rsinter` is still an older `0.1.1` binary, and
`qec-code` is not on PATH. Implementation and verification should either
install fresh binaries or explicitly point AutoQEC tests at the current rstim
checkout binaries.

## Scope

In scope:

- Normalize the checked-in BB72 instance under
  `zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6`.
- Record the Bravyi et al. Table 3 paper parameters for BB72:
  `l = 6`, `m = 6`, `A = x^3 + y + y^2`, `B = y^3 + x + x^2`.
- Preserve the generator shift-pair representation needed by the local matrix
  generator, and explicitly map it to the paper polynomial representation.
- Record exact distance `6` with citation/provenance.
- Add explicit logical-observable artifacts for the BB72 X-memory benchmark.
- Add a BB campaign, search space, task, suite, and promotion rules.
- Extend explicit-instance candidate resolution so run-loop, frontier, report,
  and promotion see a positive exact distance instead of empty parameters.
- Generate rsinter CSS specs with `hx`, `hz`, `observables`, `seed`, and
  paper-facing BP+OSD parameters.
- Add a published-reference checker backed by a Bravyi Table 6 fixture.
- Add negative controls for noncommuting matrices, reference misses, and failed
  promotion rules.
- Commit a finalized BB run artifact set when the run is reproducible and small
  enough for review.

Out of scope:

- Other qLDPC families.
- Randomized upper-bound distance methods.
- Replacing rstim's CSS circuit generation or decoder implementations.
- Making the full paper-reference BP+OSD run part of every normal CI cycle.
- Large BB codes beyond the small `n = 72` fixture.

## Main Decision

Use a layered acceptance design.

The main AutoQEC run should use a recorded exact BB72 distance from the curated
instance and the existing `copied-zoo-exact` distance method. A focused
`qec-code` exact-distance probe remains available to verify the recorded
distance, but it is not run in the hot path because the local BB72 ILP probe
takes about 149 seconds.

The main rsinter benchmark should be a fast, explicit-observable BB72 CSS
contract run that proves AutoQEC can generate the correct backend spec, parse
the new result fields, render the report, and run promotion. A separate
published-reference artifact and validator should carry the Bravyi Table 6
comparison. If the full reference run is too slow for CI, it remains an
explicit manual or committed-artifact validation rather than silently weakening
the check.

## Architecture

`rstim`, `rsinter`, and `qec-code` own:

- CSS circuit and detector-error-model generation
- explicit logical-observable validation
- BP+OSD and predict-zero runner behavior
- exact CSS distance computation

AutoQEC owns:

- BB72 instance metadata and paper provenance
- campaign/search-space definitions
- task/suite/decoder registry entries
- run-loop artifacts and result parsing
- published-reference checks
- reports and promotion into the Zoo

The BB72 instance remains a curated Zoo object. Search runs copy it into
candidate artifacts, evaluate it, and then promote accepted output in the same
way the surface-code M1 demo promotes accepted candidates.

## BB72 Instance Contract

The curated BB72 instance should contain enough information to answer two
questions without reading source code:

1. Is this the Bravyi et al. Table 3 `[[72,12,6]]` code?
2. How were the checked-in matrices generated?

Recommended `instance.json` shape:

- `id`: `bivariate-bicycle-code-m6-n6`
- `code_id`: `bivariate-bicycle-code`
- `family_id`: `bivariate-bicycle-code`
- `parameters.distance`: `6`, as a search-layer compatibility mirror of the
  exact derived distance
- `parameters.paper`:
  - `l`: `6`
  - `m`: `6`
  - `A`: `x^3 + y + y^2`
  - `B`: `y^3 + x + x^2`
  - `paper_ref`: `2308.07915`
- `parameters.generator`:
  - current shift-pair fields needed by TensorQEC or the fallback generator
  - enough naming to make the `A`/`B` mapping obvious
- `derived_properties`:
  - `n`: `72`
  - `k`: `12`
  - `distance`: `6`
  - `mx`: `36`
  - `mz`: `36`
- `artifacts`:
  - `hx`: `hx.json`
  - `hz`: `hz.json`
  - `observables_x`: an explicit logical-X observable artifact, if stored in
    the Zoo bundle
- `provenance`:
  - matrix generator script and parameters
  - paper evidence references for parameters and distance
  - optional exact-distance verification command

If the existing fallback-generator output is matrix-identical to the paper
BB72 convention after translating terms, keep the matrices and update metadata.
If not, regenerate the instance from the paper polynomial convention and update
tests accordingly.

The duplicated `parameters.distance` field is deliberate. Existing
search-layer frontier and promotion code treats a candidate's distance as part
of its parameter payload. Issue #18 should keep that compatibility while adding
tests that require `parameters.distance`, `derived_properties.distance`,
`distance.json.distance`, and frontier distance to agree.

## Candidate Resolution

Existing explicit-instance search-space specs allow `instance_path`, but the
run-loop and promotion layers still assume every candidate has parameters with
a positive integer `distance`.

Issue #18 should tighten that path:

- Resolving an explicit Zoo instance should copy instance parameters into the
  `CandidateInput`.
- The resolved candidate should include exact distance from
  `instance.derived_properties.distance` when present.
- Candidate payloads written into runs should preserve the paper/generator
  parameter object and expose a consistent positive distance.
- Directory-candidate loading should follow the candidate schema and accept
  nested JSON parameter values, instead of rejecting the BB72 `paper` and
  `generator` objects.
- Strategy code should be able to rank explicit-instance candidates by the
  resolved exact distance.
- Promotion should compare `distance.json`, candidate payload, frontier item,
  and instance `derived_properties.distance` consistently.

This change is not a broad sampled-parameter BB search engine. It is the
minimum contract needed for explicit curated instances to flow through
autoresearch and promotion safely.

## Campaign And Benchmark Suite

Add a campaign such as:

- `campaigns/examples/bb72-qldpc-campaign/campaign.json`
- `campaigns/examples/bb72-qldpc-campaign/search_space.json`
- `campaigns/examples/bb72-qldpc-campaign/promote_rules.json`

The search space should seed at least the published BB72 candidate:

```json
{
  "candidate_id": "bivariate-bicycle-code-m6-n6",
  "code_family": "bivariate-bicycle-code",
  "instance_path": "zoo/codes/bivariate-bicycle-code/instances/bivariate-bicycle-code-m6-n6",
  "provenance": {
    "kind": "paper-seed",
    "label": "Bravyi et al. BB [[72,12,6]]"
  }
}
```

The task should use the general CSS memory path:

- `input_type`: `css`
- `observable`: `logical_x`
- `basis`: `x`
- `schedule`: `greedy`
- fixed rounds, initially `3` unless the accepted paper-reference fixture
  requires a different value
- physical error rates including at least one published-reference point
- positive-shot budgets for any point used as evidence

The fast suite should include:

- a BB72 BP+OSD runner with `bp_algorithm = "min_sum"`,
  `osd_method = "combination_sweep"`, and explicit `osd_order`
- `predict-zero-v1` as a negative-control runner

If a fast BP+OSD point uses `max_shots = 0`, it is only an interface smoke.
Any point used for published-reference validation must have positive shots,
logical errors, LER, and Wilson confidence interval data.

## Rsinter Spec Contract

AutoQEC should generate a CSS rsinter spec containing:

```toml
[runner.params]
input_type = "css"
code_id = "bivariate-bicycle-code-m6-n6"
hx = "input/hx.css.json"
hz = "input/hz.css.json"
observables = "input/observables.css.json"
basis = "x"
schedule = "greedy"
rounds = [3]
p = [0.003]
seed = 12345
max_shots = 64
max_errors = 32
batch_size = 64
bp_algorithm = "min_sum"
bp_iters = 50
early_stop = true
osd_method = "combination_sweep"
osd_order = 10
```

The parser should preserve these rsinter result fields when present:

- `decoder_impl`
- `seed`
- `logical_observable_source`
- `logical_observable_basis`
- `logical_failure_aggregation`
- `logical_observable_count`
- `bp_algorithm`
- `bp_iters`
- `osd_method`
- `osd_order`

Unknown, unsupported, or silently dropped decoder parameters should fail before
claiming a completed benchmark.

## Published-Reference Check

Add a fixture such as `benchmarks/fixtures/bb72-reference/expected.json` with:

- paper id `2308.07915`
- BB72 parameter statement reference
- distance statement reference
- Table 6 coefficients:
  - `d_circ = 6`
  - `c0 = 11.09`
  - `c1 = 365.6`
  - `c2 = -16088`
- selected reference points such as:
  - `p = 0.003`, expected LER about `0.00458`
  - `p = 0.01`, expected LER about `0.507`

The checker should:

1. Load a completed manifest or committed reference artifact.
2. Find the selected `p` point for the BB72 BP+OSD runner.
3. Require positive shots and valid Wilson CI fields.
4. Check whether the published reference LER lies inside the observed CI band.
5. Write a machine-readable PASS/FAIL artifact.
6. Make `report.html` show the reference-check status clearly.

A reference miss should be visible in the report as `FAIL`. It may still leave
the raw run artifacts available for diagnosis, but it must not be presented as
a validated published-curve match.

## Promotion

`promote_rules.json` for the BB campaign should require:

- `min_distance = 6`
- `require_distance_verified = true`
- exact distance payloads only
- an LER gate or explicit reference-check gate, depending on the final
  artifact contract

Promotion must reject:

- missing or null distance
- upper-bound or unknown-bound distance
- mismatch between candidate, frontier, `distance.json`, and instance distance
- candidates whose reference-check status is required but failed

The successful promotion should copy `instance.json`, `hx.json`, `hz.json`, and
any supported observable artifact into the Zoo and rebuild:

- `zoo/views/instance-index.json`
- `zoo/views/browse.md`
- rendered cards and static site artifacts

## Error Handling

Expected hard failures:

- malformed `hx` or `hz`
- noncommuting CSS checks
- missing explicit observables for the BB72 paper-facing task
- explicit observables with wrong width, rank, or logical class
- old rsinter that does not support `observables`, `bp_algorithm`,
  `osd_method`, or `predict-zero`
- old or missing `qec-code` for focused exact-distance verification
- missing recorded exact distance for promotion
- published-reference point missing positive shots or CI

AutoQEC should produce specific failure messages. In particular, an old backend
should not look like a bad BB candidate.

## Negative Controls

Add focused tests or fixtures for:

- a noncommuting BB-like candidate rejected before rsinter execution
- a published-reference miss that writes/report a clear FAIL
- tight promotion rules that prevent Zoo insertion
- malformed upper-bound or randomized distance payloads rejected under
  `require_distance_verified = true`
- unknown rbposd parameters rejected before backend work

## Testing Strategy

Fast tests:

- BB72 instance metadata and evidence references load correctly.
- The BB72 instance reports `n = 72`, `k = 12`, and `distance = 6`.
- Explicit-instance candidate resolution preserves parameters and exact
  distance.
- Run-loop strategy/frontier code can rank explicit-instance candidates.
- CSS rsinter TOML includes `observables`, `seed`, BP+OSD parameters, and no
  surface-style `distance = [...]`.
- Result parsing accepts and preserves observable metadata and decoder
  provenance.
- Noncommuting candidates fail before backend execution.
- Published-reference checker passes and fails on deterministic fixtures.
- Promotion accepts the passing BB72 candidate and rejects rule failures.

Light integration tests:

- A fake or light rsinter run completes the BB72 candidate and writes completed
  manifests, plot, leaderboard, and report.
- A `predict-zero` negative-control fixture lands in the expected broad LER
  window for the selected small budget.
- The report includes BB72, exact distance, observable metadata, and
  reference-check status.

Heavy/manual verification:

- Run the qec-code exact ILP BB72 distance check:

```bash
cd /Users/nzy/rcode/rstim
cargo test -p qec-code --features distance-ilp-highs --test cli \
  code_css_distance_exact_bb72_known_distance_with_ilp -q
```

- Run the rsinter manual BB72 BP+OSD reference fixture when a long local
  numerical check is intended:

```bash
cd /Users/nzy/rcode/rstim
target/debug/rsinter bench run \
  --spec rsinter/tests/fixtures/bench/bb72_css_bposd_reference.toml \
  --language rust \
  --out /tmp/bb72-css-bposd-reference
```

The first command is known to take about 149 seconds locally. The second should
not be required in the normal fast test loop unless a committed reference
artifact is being refreshed.

## Completion Criteria

Issue #18 is complete when:

- workspace validation passes
- the BB72 instance is paper-backed and exact-distance annotated
- the BB campaign can run through `autoqec-search run`
- run artifacts include completed manifests, leaderboard, frontier, summary,
  `run-summary.html`, and `report.html`
- the report displays BB72 LER curves and published-reference status
- exact-distance verification for BB72 is documented and reproducible
- promotion writes the accepted BB instance into the Zoo
- `zoo/views/browse.md` shows the promoted BB instance
- negative controls prove invalid commuting, reference, and promotion cases fail
  visibly

## Rollout

1. Normalize the BB72 Zoo instance and observables.
2. Update explicit-instance candidate resolution and distance propagation.
3. Add BB task/suite/campaign/promote rules.
4. Add rsinter CSS spec support for explicit observables and BP+OSD params.
5. Add result parsing/report support for observable and decoder provenance.
6. Add the published-reference fixture and checker.
7. Add negative-control tests.
8. Run the fast BB72 campaign.
9. Refresh report, promotion, and Zoo derived artifacts.
10. Run focused heavy verification only when refreshing exact-distance or
    paper-reference evidence.
