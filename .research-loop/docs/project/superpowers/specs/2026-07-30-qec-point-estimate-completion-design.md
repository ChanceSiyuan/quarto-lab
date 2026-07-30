# QEC Point-Estimate Completion Design

Date: 2026-07-30
Status: Approved design, pending implementation

## Goal

Keep all 21 quantum error-correction problems in the local portfolio while ensuring every comparison row has complete, point-valued assessment metrics. The user-facing portfolio and detailed assessment reports must not show pending technical evaluations or numeric ranges.

## Scope

This change applies to the QEC portfolio, problem assessment panel, and generated detailed assessment reports in the `codex/quantum-problem-valuation` worktree. It covers:

- Research Value (V), Autoresearch Fit (A), and Combined Priority (S).
- Scientific Attention.
- Technical Success Estimate.
- Industry/Social Enabling-Value Proxy.
- Commercial Investment Proxy.
- Existing completed assessment artifacts for Prob-001 through Prob-021.

The underlying assessment interval data remains available for machine audit and recalculation. Only user-facing numeric presentation changes to point estimates.

## Completion Rules

A portfolio row is complete when it has:

1. A completed assessment summary with V, A, and S point estimates.
2. A scientific-attention point value derived from confirmed anchor-paper citation counts.
3. A modeled technical-success point estimate.
4. Public industry/social and commercial-investment proxy point values.

Rows are not removed merely because no sealed benchmark has run. Instead, an unmeasured technical gate receives a transparent model estimate and is labeled as such. A real sealed-benchmark result, when available, takes precedence over the model estimate.

## Point-Estimate Model

### Scientific Attention

Use the sum of OpenAlex `cited_by_count` values for the accepted anchor papers in the frozen valuation snapshot. Store and present this as a citation count with a degenerate interval (`low = base = high`) when the existing quantitative-value contract requires interval-shaped data.

If an accepted anchor lacks a citation count, treat its contribution as zero and record the missing source in the audit rationale. Every completed portfolio row must still receive a numeric citation total.

### Technical Success Estimate

When the frozen assessment contains no known measured technical-feasibility value, derive a point estimate from five existing assessment dimension estimates:

| Assessment dimension | Weight |
|---|---:|
| Plausibility | 35% |
| Executable Objective | 20% |
| Correctness & Anti-gaming | 20% |
| Incremental Feedback | 15% |
| Attempt Runtime | 10% |

Each dimension is scored from 0 to 5. Normalize it to a percentage and compute:

```text
technical_success_percent =
  100 / 5 * (
    0.35 * plausibility
    + 0.20 * executable_objective
    + 0.20 * correctness_and_anti_gaming
    + 0.15 * incremental_feedback
    + 0.10 * attempt_runtime
  )
```

Round the result to one decimal place. Store it as a public percentage with `low = base = high`. Its provenance must identify it as a model estimate derived from assessment dimensions, not a measured gate result.

If a known measured technical-feasibility value already exists, preserve it and use its central value. Do not replace it with the model.

### Economic Proxies

Use the central value (`interval.base`) of the existing public proxy evidence. Preserve currency and price-base year in the display. Existing fallbacks remain available:

- Industry/Social Enabling-Value Proxy: USD 57 billion in 2035 dollars.
- Commercial Investment Proxy: USD 10 billion in 2026 dollars.

These values remain explicitly labeled as broad proxies, not problem-specific capturable value.

## Presentation Rules

All user-facing surfaces display one value only:

- Score interval `{ min, estimate, max }` displays `estimate`.
- Quantitative interval `{ low, base, high }` displays `base`.
- Percentages display one percentage, such as `64.8%`.
- Money displays one abbreviated amount plus currency and base year, such as `$57B · USD 2035`.
- Scientific attention displays one citation count, such as `3 citations`.

Replace `Technical gate status` with `Technical Success Estimate`. Do not render `Pending sealed evaluation`, `Pending measurement`, or low/high ranges on the portfolio, assessment panel, or generated report.

The detailed report must include a short method note stating that the value is a model estimate and listing the five weighted inputs. It must continue to distinguish modeled estimates from measured sealed-benchmark results.

## Data Flow

1. The completed assessment envelope supplies dimension estimates and frozen valuation evidence.
2. A pure point-estimate helper derives missing scientific-attention and technical-success values.
3. Assessment summary creation includes the completed quantitative values for new runs.
4. Portfolio reading applies the same helper as a backward-compatible fallback for existing completed runs.
5. A backfill command updates the 21 existing completed assessment artifacts and regenerates their reports without changing problem lifecycle state.
6. Portfolio, problem panel, and HTML report formatters render central values only.

The derivation helper is the single source of truth so new assessments, old artifacts, and all display surfaces use the same formula.

## Error Handling

- Missing required dimension estimates is a validation error for the backfill and must identify the problem and missing dimension.
- Missing anchor citation counts do not abort completion; they contribute zero and produce an audit note.
- Private evidence remains redacted. Derivation must not convert private inputs into public estimates.
- Existing known measured values always win over modeled values.
- Backfill writes are staged and validated before replacing an existing assessment artifact.

## Testing

Follow red-green-refactor for each behavior:

1. Unit tests for the exact technical-success formula, rounding, measured-value precedence, citation aggregation, missing-citation behavior, and privacy handling.
2. View-model tests proving score, percent, citation, and money formatting contain no ranges.
3. Portfolio-reader tests proving all 21 rows receive numeric scientific-attention and technical-success values.
4. Report tests proving the model label and method note appear while pending copy and interval syntax do not.
5. Backfill tests using temporary artifact directories before touching the 21 local records.
6. Full unit suite, build, and browser smoke test of `/qec-portfolio` and one detailed report.

## Acceptance Criteria

- The QEC portfolio still contains 21 problems.
- No visible row contains an unvalued comparison metric.
- No visible score or quantitative metric contains a low/high range.
- `Pending sealed evaluation` and `Pending measurement` do not appear in the portfolio, problem assessment panel, or detailed reports.
- Modeled technical success is visibly labeled and reproducible from the documented formula.
- Existing measured technical results remain authoritative.
- Private evidence remains private.
- Tests, build, and local browser verification pass.
