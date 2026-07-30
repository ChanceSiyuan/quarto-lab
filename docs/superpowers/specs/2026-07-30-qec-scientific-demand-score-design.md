# QEC Scientific Demand Score Design

Date: 2026-07-30
Status: Proposed for written review

## Goal

Replace the QEC portfolio's raw anchor-paper citation total with a systematic,
auditable problem-level measure of scientific demand. The score must not treat
missing citation records as zero, must remain distinct from research quality or
social value, and must be reproducible from a frozen OpenAlex evidence snapshot.

## Scope

The first implementation applies only to the 21 approved quantum error
correction problems. It covers citation-corpus construction, citation metric
calculation, immutable valuation snapshots, assessment summaries, the portfolio
page, the problem assessment panel, and detailed HTML reports.

The first implementation uses field/time-normalized influence, recent citation
momentum, and research breadth. Citation-network PageRank and full-text
citation-context weighting are recorded as a second-phase extension because the
current OpenAlex snapshot does not contain a complete citing graph or citation
contexts.

## Terminology

- **Selected Reference Paper** replaces the user-facing term "anchor paper."
  A selected paper seeds retrieval; it is not the complete literature set.
- **Problem Literature Set** is the deduplicated set of relevant works expanded
  from selected reference papers and OpenAlex topics.
- **Scientific Demand Score** is a 0--100 composite of normalized scholarly
  influence, momentum, and breadth. It measures attention and research demand,
  not novelty, correctness, technical feasibility, or economic value.

## Evidence Basis

The model follows four established method families:

1. Article-level field and time normalization, including FWCI/MNCS-style
   observed-to-expected citation ratios and RCR-style field definition.
2. Topic-level prominence models that combine normalized, log-transformed
   signals with explicit coefficients.
3. Bayesian or shrinkage treatment for immature, low-count evidence.
4. Citation-network and content-aware weighting as a future enhancement.

The external bibliography records these papers under the `bibliometrics` and
`research-valuation` literature indexes. They remain external evidence and are
not promoted into trusted knowledge by this change.

## Literature-Set Construction

For each problem:

1. Resolve every selected reference paper DOI or OpenAlex work identifier.
2. Expand through OpenAlex topic membership and works that cite the selected
   references.
3. Compute textual and topic relevance against the problem title, summary, and
   evaluation question.
4. Retain confirmed references regardless of automatic relevance, and retain
   expanded candidates only above the configured relevance threshold.
5. Deduplicate by DOI, then by normalized title. Prefer the record with a DOI,
   richer annual citation data, and the stronger citation record.
6. Record author and institution identifiers so repeated output from one team
   does not masquerade as broad independent activity.

Every retained record stores its inclusion reason, relevance, identifier-match
confidence, access time, OpenAlex ID, DOI, publication year, citation count,
annual citation counts, normalized citation percentile, FWCI when available,
author IDs, institution IDs, topic IDs, and referenced-work IDs.

## First-Phase Score

Each paper receives an evidence weight:

```text
paper_weight = relevance * match_confidence * independence_discount
```

Confirmed references receive a nonzero relevance floor. A DOI-resolved record
has the highest match confidence; an exact OpenAlex identifier is next. Title-
only matches are never silently treated as canonical.

Three bounded problem-level components are calculated:

### Field-normalized influence (weight 0.45)

Use the weighted median OpenAlex normalized citation percentile across relevant
canonical papers. The percentile already controls for publication year, work
type, and subfield. When FWCI is available it is retained for audit and future
calibration, but the first-phase bounded component uses the percentile to avoid
letting one extremely highly cited paper dominate the problem.

### Recent momentum (weight 0.30)

For every paper with two complete annual citation observations, calculate:

```text
paper_momentum = log((latest_complete_year_citations + 1)
                     / (prior_complete_year_citations + 1))
```

Take the evidence-weighted median and map it to `[0, 1]` with a logistic
transform. Flat annual citations map to 0.5; growth maps above 0.5 and decline
below 0.5.

### Research breadth (weight 0.15)

Combine the number of canonical relevant papers and independent institutions
with a logarithmic saturation function. Breadth grows with independent evidence
but has diminishing returns and cannot be inflated linearly by publishing many
near-duplicate papers.

The second-phase network component retains weight 0.10. Until it exists, the
available first-phase weights are renormalized:

```text
scientific_demand = 100 *
  (0.45 * influence + 0.30 * momentum + 0.15 * breadth)
  / (0.45 + 0.30 + 0.15)
```

The stored value is a point estimate rounded to one decimal place and carries
`formulaId = qec-scientific-demand-v1`. Component values, weights, coverage,
paper count, and evidence confidence remain available for audit.

## Missing, Zero, and Low-Coverage Evidence

- Missing citation counts are excluded and recorded; they never contribute
  numeric zero.
- An explicit OpenAlex zero remains part of the frozen evidence but is not
  rendered as `0 citations`. The paper table says `No matched citations`.
- A suspicious or noncanonical record says `Citation data unverified`.
- If no canonical paper has normalized citation evidence, the score is
  unavailable and the UI says `Citation evidence insufficient`.
- One or two comparable papers may produce a score with `Low evidence
  confidence`; three or four produce `Medium`; five or more with at least 80%
  normalized-metric coverage produce `High`.
- Missing momentum causes its coefficient to be omitted and the remaining
  available coefficients to be renormalized. Influence is mandatory.

This policy prevents a missing provider value from appearing as research
failure while avoiding a fabricated zero or fabricated precision.

## Presentation

- Rename `Scientific Attention` to `Scientific Demand Score`.
- Display one point value, for example `68.4 / 100`, plus evidence confidence.
- Add a concise method note naming the three first-phase components and their
  weights.
- Display `Selected Reference Papers` and `Problem Literature Set`, not
  `Anchor Papers`.
- Raw citation totals remain audit evidence only and are not a headline metric.
- No user-facing surface renders `0 citations` or a numeric range for this
  score.
- All application UI and generated reports remain English-only.

## Snapshot and Backfill Policy

Old valuation snapshots and assessment runs remain immutable. Add the citation
formula identifier to new snapshots. The portfolio batch runner must not reuse
a snapshot whose citation formula identifier differs from the current one.

Refreshing the 21 problems creates new valuation snapshots, binds new
assessment runs to those snapshots, and generates new detailed reports. It does
not alter problem lifecycle status or trusted knowledge.

## Testing

Follow red-green-refactor:

1. Unit tests for DOI/title deduplication, FWCI retention, author/institution
   capture, match confidence, and confirmed-reference relevance floors.
2. Unit tests for influence, logistic momentum, breadth saturation, missing
   component renormalization, confidence labels, and the exact weighted score.
3. Tests proving missing counts are not converted to zero and no formatter emits
   `0 citations`.
4. Snapshot tests proving formula-version provenance and immutable refresh.
5. Portfolio and report tests proving the new name, `/ 100` point display,
   method note, selected-reference terminology, and English-only output.
6. Full test suite, production build, portfolio verification, and local browser
   smoke checks for the portfolio and at least one detailed report.

## Acceptance Criteria

- All 21 QEC problems use `qec-scientific-demand-v1` in their latest valuation
  and assessment artifacts.
- Every score is reproducible from frozen component values and weights.
- Missing records never become zero-valued citations.
- No headline metric or paper table displays `0 citations`.
- Duplicate preprint/journal records do not contribute twice.
- The score remains explicitly separate from Research Value, Technical Success,
  and economic proxies.
- Previous immutable snapshots remain readable.
- Tests, build, and local portfolio verification pass.
