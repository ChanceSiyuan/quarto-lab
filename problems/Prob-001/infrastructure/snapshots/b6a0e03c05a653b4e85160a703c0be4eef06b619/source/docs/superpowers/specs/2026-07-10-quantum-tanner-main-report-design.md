# Quantum Tanner Main Report Design

## Goal

Make every `quantum-tanner-autoresearch` run automatically produce an English,
human-readable `report.html` matching the manually reviewed master-table layout,
plus a linked construction-definition page. The report must include every
attempted finite code, including candidates skipped before rsinter, while
excluding untouched run-skeleton placeholders.

## Scope

- Apply the new layout only when `campaign_id` is
  `quantum-tanner-autoresearch`.
- Preserve the existing generic report for all other campaigns.
- Generate `report.html` and `construction-definitions.html` together from the
  normal `write_report_html` path used by autoresearch finalization and the
  `autoqec-search report` command.
- Keep both pages self-contained and offline-safe, with no network assets.
- Use English only in generated pages.

## Architecture

`autoqec_search.report` remains the campaign-neutral model loader and dispatches
Quantum Tanner runs to a new focused module,
`autoqec_search.quantum_tanner_report`. The generic model exposes candidate
parameters, provenance, and upper-bound distance values needed by the specialized
renderer. The specialized module reads each proposal-derived candidate's
repository-relative `qec_code_spec_path`, or the candidate's recorded catalog
spec with a validated default-catalog fallback, derives display metadata, and
renders the two pages.

The launcher needs no extra report step: `run_loop` already calls
`write_report_html` during finalization, so both long runs and explicit
`autoqec-search report` invocations use the same implementation.

## Main Report

The top of `report.html` contains:

1. Run title and provenance summary.
2. Cards for processed candidates, rsinter-evaluated candidates, skipped
   candidates, and frontier candidates.
3. One master-table row per attempted finite code, with these columns in order:
   finite code/candidate, base group, A/B generator indices, local classical
   codes, CSS parameters, code rate, X upper bound, screening status,
   errors/shots, LER, 95% confidence interval, and decoding time.
4. Human-readable interpretation notes and benchmark configuration.

The existing LER plot and embedded report JSON remain available below the
summary so no scientific evidence is lost.

## Construction Definitions

`construction-definitions.html` contains one anchored section per candidate. It
shows the base-group name, order, element-order convention, A/B generator
indices, and the complete `H_A` and `H_B` parity-check matrices.

For small binary local codes, the renderer computes rank, dimension, minimum
distance, and weight enumerator. It recognizes the reviewed invariant classes:

- `[2,1,2]` as `Rep(2)`;
- `[4,2,2]` with weight enumerator `{2: 2, 4: 1}` as
  `Rep(2) direct sum Rep(2)`;
- `[8,4,4]` with weight enumerator `{4: 14, 8: 1}` as
  `Extended Hamming / RM(1,3)`.

All other codes are labeled `Unnamed [n,k,d]`. If exact enumeration exceeds the
bounded analysis budget, the label uses `d=?` and the full matrix remains linked.

## Error Handling

Construction metadata is presentation evidence, not a numerical-run gate. A
missing, unsafe, or malformed proposal spec must not make an otherwise finalized
run fail report generation. The master row and definition section instead show
`Construction metadata unavailable` and record the reason in embedded report
data. The renderer validates GF(2) parity-check semantics and generator-index
bounds before presenting a definition. All values and paths are HTML-escaped.

## Testing

- A Quantum Tanner report fixture proves automatic campaign dispatch, four-row
  inclusion including a skipped candidate, English-only copy, group/local-code
  columns, upper-bound and LER formatting, and linked definitions.
- Local-code unit tests prove the recognized-code labels and unnamed fallback.
- A missing-spec test proves graceful degradation.
- Existing generic-report tests prove other campaigns are unchanged.
- Full repository tests and `validate --root .` remain green.
