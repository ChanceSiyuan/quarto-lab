# Assessment Methodology

This document describes the current local research-problem assessment method.
It is implementation documentation for reviewers and future maintainers, not a
claim that the model is a calibrated scientific or investment-grade forecast.

The current quantitative workflow is intentionally narrow:

- it supports quantum-computing problems whose scope is explicitly identified;
- the QEC portfolio reader currently filters to `quantum-computing` plus
  `error-correction-and-fault-tolerance`;
- public evidence is frozen into immutable local snapshots before scoring; and
- assessment artifacts are local-only runtime outputs and are not part of the
  submitted repository history.

## High-level model

An assessment has two layers.

1. **Frozen valuation evidence** records public external evidence and any local
   operator assumptions in an immutable snapshot under
   `problems/<id>/valuation/snapshots/<snapshotId>/`.
2. **Research-problem assessment** scores the problem from the frozen evidence,
   the problem description, and the trusted knowledge resolver result. Completed
   runs are immutable and live under
   `problems/<id>/assessments/<runId>/`.

The local service treats these artifacts as advisory. It never mutates the
problem lifecycle, never starts an autoresearch campaign, and never promotes
external evidence into trusted `knowledge/`.

## Public score tracks

The visible assessment score tracks are:

| Track | Short label | Meaning | Range |
|---|---:|---|---:|
| Research Value | V | How valuable the problem appears as a research target. | 0-100 |
| Autoresearch Fit | A | How suitable the problem is for automated/bounded search. | 0-100 |
| Combined Priority | S | Harmonic combination of V and A. | 0-100 |

The public UI renders point values. Internally the assessment schema still
stores `min`, `estimate`, and `max` intervals for auditability, but public
cards and local reports display the point estimate rather than a range.

## Qualitative dimensions

Each dimension is scored on a 0-5 interval. Host-side validation recomputes the
aggregate scores and rejects arithmetic that does not match the fixed policy.

### Research Value dimensions

| Dimension ID | Label | Weight |
|---|---|---:|
| `importance` | Importance | 20 |
| `gap_and_novelty` | Gap and novelty | 20 |
| `plausibility` | Plausibility | 15 |
| `learning_from_failure` | Learning from failure | 15 |
| `generality_and_publication` | Generality and publication potential | 15 |
| `expected_value_relative_to_cost` | Expected value relative to cost | 15 |

Research Value is:

```text
V = 100 * weighted_average(research_value_dimension_scores) / 5
```

### Autoresearch Fit dimensions

| Dimension ID | Label | Weight |
|---|---|---:|
| `modifiable_search_object` | Modifiable search object | 20 |
| `executable_objective` | Executable objective | 20 |
| `correctness_and_anti_gaming` | Correctness and anti-gaming | 15 |
| `incremental_feedback` | Incremental feedback | 15 |
| `fresh_evaluation` | Fresh evaluation | 10 |
| `reproducibility_and_auditability` | Reproducibility and auditability | 10 |
| `attempt_runtime` | Attempt runtime | 10 |

Autoresearch Fit is:

```text
A = 100 * weighted_average(autoresearch_fit_dimension_scores) / 5
```

### Combined Priority

Combined Priority uses the harmonic mean of Research Value and Autoresearch Fit:

```text
S = 2 * V * A / (V + A)
```

If both inputs are zero, `S` is zero. The harmonic mean deliberately penalizes a
problem that is high-value but poorly suited to bounded automation, or easy to
automate but low-value.

## Verdict rule

The host derives the verdict from point estimates. Bands are:

| Band | Score range |
|---|---:|
| strong | `score >= 70` |
| mixed | `40 <= score < 70` |
| weak | `score < 40` |

The current verdict rule is:

| Condition | Verdict |
|---|---|
| V is strong and A is strong | `DO_NOW` |
| V is strong, A is not strong, and a bounded reframe exists | `REFRAME` |
| V is strong, A is weak, and no bounded reframe exists | `NOT_AUTORESEARCH` |
| otherwise | `DEFER` |

The model may mark a verdict provisional when the evidence interval crosses a
decision boundary, but the public summary still renders one headline verdict.

## Scientific Demand Score

Scientific Demand Score is the current citation-derived impact proxy for QEC
problems. It is not a raw citation count. Raw counts are recorded for audit, but
they are not directly summed into a problem score.

The implemented formula ID is:

```text
qec-scientific-demand-v1
```

### Paper evidence weight

Each included paper receives an evidence weight:

```text
paper_weight =
  relevance_weight * match_confidence * independence_discount
```

Rules:

- `relevance_weight` is the paper relevance supplied by the evidence candidate.
- Confirmed anchor papers have a minimum relevance floor of `0.25`.
- `match_confidence` defaults to `1` when missing and is clamped to `[0, 1]`.
- `independence_discount` may be provided directly. Otherwise it is derived
  from institution overlap: repeated institutions receive `1 / sqrt(frequency)`
  credit, averaged over the paper's distinct institution IDs. Papers without
  institution IDs receive no institution penalty.
- Papers with non-positive final evidence weight are excluded from component
  calculations.

This weighting is meant to reduce the effect of duplicate, weakly matched, or
highly concentrated evidence without pretending that bibliometrics can prove
novelty.

### Components

Scientific Demand Score currently has four component slots:

| Component | Weight | Current status | Meaning |
|---|---:|---|---|
| influence | 0.45 | active | Weighted median of normalized citation percentile. |
| momentum | 0.30 | active when year data exists | Recent citation growth from complete-year counts. |
| breadth | 0.15 | active when positive-weight papers exist | Diversity of papers and institutions. |
| network | 0.10 | reserved | Reserved for a future collaboration/network signal. |

Influence:

```text
influence = weighted_median(citation_normalized_percentile)
```

The coverage value records what fraction of positive evidence weight had a
normalized citation percentile. Missing normalized percentiles reduce evidence
confidence but are not converted into zero.

Momentum:

```text
raw_growth = log((citations_latest_complete_year + 1)
                 / (citations_prior_complete_year + 1))
momentum = logistic(raw_growth)
```

The latest complete year is `currentYear - 1`; the prior complete year is
`currentYear - 2`. Papers without both year counts are excluded from the
momentum component. If no paper has both counts, momentum is an evidence gap.

Breadth:

```text
paper_breadth = min(1, log1p(paper_count) / log1p(20))
institution_breadth = min(1, log1p(institution_count) / log1p(20))
breadth = 0.6 * paper_breadth + 0.4 * institution_breadth
```

The saturation count of 20 keeps breadth from growing without bound as more
similar papers are added.

Network:

The `network` component is recorded as `reserved`. It is not included in the
current score until a validated network metric is added.

### Score aggregation

Only known active components are included. Available weights are renormalized:

```text
Scientific Demand Score =
  round_to_1_decimal(
    100 * sum(component_weight * component_value)
        / sum(available_component_weights)
  )
```

If all active components are missing, the result is an evidence gap. The model
does not fabricate a zero.

### Evidence confidence

The current citation evidence confidence rule is:

| Condition | Confidence |
|---|---|
| at least 5 comparable papers and coverage at least 0.8 | high |
| at least 3 comparable papers | medium |
| otherwise | low |

Warnings are retained when coverage is partial, momentum is unavailable, raw
counts are missing, or no paper has positive evidence weight.

## Technical Success estimate

Technical Success is the probability-like public estimate used by the QEC
portfolio when no sealed benchmark has yet produced a measured value.

If `technicalFeasibility` is already a known measured value, the assessment
preserves that measured value.

Otherwise the host derives a model estimate from selected 0-5 assessment
dimensions:

```text
qec-technical-success-v1
```

| Input dimension | Weight |
|---|---:|
| `plausibility` | 0.35 |
| `executable_objective` | 0.20 |
| `correctness_and_anti_gaming` | 0.20 |
| `incremental_feedback` | 0.15 |
| `attempt_runtime` | 0.10 |

Formula:

```text
Technical Success =
  round_to_1_decimal(
    100 * weighted_average(selected_dimension_estimates) / 5
  )
```

The result is stored as a point interval with unit `percent` and
`estimateKind: "model"`. It is not presented as a completed sealed evaluation.

## Economic value evidence

Economic evidence is represented as atomic known or unknown values. A known
value has:

- `state: "known"`;
- an ordered `low/base/high` interval;
- a unit such as `USD_2035`, `USD_2026`, `percent`, or `score-100`;
- public/private visibility;
- evidence state and evidence tier; and
- explicit source IDs and source locators.

An unknown value stays unknown with a reason. Missing values are never converted
to zero.

The current QEC portfolio uses broad public proxies to make the comparison
complete when no problem-specific market model exists:

| Track | Current proxy | Interpretation |
|---|---|---|
| Social Value | `mckinsey-qc-internal-market-2035` | Broad enabling quantum-computing market proxy, not problem-specific welfare. |
| Capturable Value | `ibm-quantum-investment-floor-2026` | Public investment-floor proxy, not a problem-specific capture estimate. |

These proxies are intentionally labeled as broad evidence. They help the UI
avoid empty economic columns, but they do not prove problem-specific revenue,
pricing power, adoption, novelty, or technical feasibility.

### Prob-000 Expected Attributable Net Social Value example

The preserved Prob-000 showcase uses a separate problem-specific worked
example instead of allocating a percentage of the broad USD 43-71 billion
quantum-computing forecast to one research problem. The example is deliberately
limited to Prob-000 and does not alter production QEC portfolio assessments.

**Expected Attributable Net Social Value (EANSV)** is the product's descriptive
label for a synthesis of standard social cost-benefit, counterfactual, and
expected-value-of-information ideas. It is not a named formula taken from one
publication. Conceptually:

```text
EANSV = E_Y[max_a E_theta(W_R(a, theta, Y) | Y)]
        - max_a E_theta(W_0(a, theta))
        - PV(C_R)
```

The finite Prob-000 fixture treats every outcome branch as the present value
under the best modeled downstream response, so the implemented form is:

```text
with_research_value = sum_y(probability_y * branch_present_value_y)

EANSV = with_research_value
        - without_research_counterfactual_PV
        - research_cost_PV
```

The counterfactual prevents the research from receiving credit for value that
is expected to arise without it. Research cost is then deducted to produce a
net value. The result may be negative and is not clamped to zero.

#### External evidence versus scenario assumptions

External evidence supports the existence of the repeated technical task,
public software, and one observable compute-price anchor. It does not establish
future adoption, productivity, success probability, the counterfactual, or the
final value.

| Input | Value used | Classification |
|---|---:|---|
| c3-standard-8 public price | USD 0.403216 per instance-hour | External price evidence, accessed 2026-07-30. |
| Social discount rate | 3.5% | Scenario assumption; adopts the UK Green Book headline rate for this worked example. |
| Full-success probability | 0.35 | Scenario assumption. |
| Full-success adoption and workload | 30 teams; 1,000 runs/team/year; years 1-5 | Scenario assumptions. |
| Full-success time effects | 0.5 compute hour and 0.5 researcher hour released per run | Scenario assumptions. |
| Partial-success probability | 0.25 | Scenario assumption. |
| Partial-success adoption and workload | 10 teams; 500 runs/team/year; years 1-3 | Scenario assumptions. |
| Partial-success time effects | 0.25 compute hour and 0.25 researcher hour released per run | Scenario assumptions. |
| Loaded researcher-hour social value | USD 100/hour | Scenario assumption. |
| Productive recapture fraction | 0.20 | Scenario assumption. |
| Decision-useful negative-result branch | probability 0.40; USD 75,000 PV | Scenario assumptions. |
| Without-research counterfactual | USD 100,000 PV | Scenario assumption. |
| Research cost | USD 250,000 PV | Scenario assumption. |

The compute component is rounded to cents before aggregation. Productive time
is also rounded to cents:

```text
compute saving per run
  = round_to_cents(price per instance-hour * instance-hours avoided)

productive-time value per run
  = round_to_cents(researcher-hours released
                   * loaded hourly social value
                   * productive recapture fraction)
```

All amounts below are constant 2026 USD. With a 3.5% social discount rate, the
full-success branch is:

```text
per-run benefit = round_to_cents(0.403216 * 0.5)
                  + round_to_cents(0.5 * 100 * 0.20)
                = 0.20 + 10.00
                = 10.20

annual benefit = 30 * 1,000 * 10.20 = 306,000
branch PV = sum(306,000 / 1.035^year, year = 1..5)
          = 1,381,606.026894049
```

The partial-success branch is:

```text
per-run benefit = round_to_cents(0.403216 * 0.25)
                  + round_to_cents(0.25 * 100 * 0.20)
                = 0.10 + 5.00
                = 5.10

annual benefit = 10 * 500 * 5.10 = 25,500
branch PV = sum(25,500 / 1.035^year, year = 1..3)
          = 71,441.74301329814
```

The decision-useful negative-result branch has an assumed base-year present
value of USD 75,000. Combining the mutually exclusive branches gives:

```text
with-research expected PV
  = 0.35 * 1,381,606.026894049
    + 0.25 * 71,441.74301329814
    + 0.40 * 75,000
  = 531,422.5451662417

EANSV = 531,422.5451662417 - 100,000 - 250,000
      = 181,422.5451662417
```

The static card rounds that calculated result to the nearest USD 10,000 and
displays one number: `+$180K USD 2026`. The rounded card value is not stored in
the fixture.

The external technical and method references for this worked example are:

- [QDistRnd, JOSS 7(72), DOI 10.21105/joss.04120](https://doi.org/10.21105/joss.04120),
  supporting the existence of a published public distance-calculation tool;
- [Distance-Finding Algorithms for Quantum Codes and Circuits](https://arxiv.org/abs/2603.22532),
  used as external current technical context;
- [qLDPC](https://github.com/qLDPCOrg/qLDPC), documenting public software
  integration;
- [Google Cloud general-purpose machine pricing](https://cloud.google.com/products/compute/pricing/general-purpose),
  supplying the mutable unit-price anchor;
- [NIST IR 7319](https://doi.org/10.6028/NIST.IR.7319) and the
  [UK Green Book](https://www.gov.uk/government/publications/the-green-book-appraisal-and-evaluation-in-central-government),
  for general cost-benefit, counterfactual, and discounting conventions;
- the ISPOR Value of Information Analysis Task Force
  [Report 1](https://doi.org/10.1016/j.jval.2020.01.001) and
  [Report 2](https://doi.org/10.1016/j.jval.2020.01.004), for EVSI/ENBS
  concepts; and
- UK DSIT's [The value of public R&D](https://www.gov.uk/government/publications/the-value-of-public-rd/the-value-of-public-rd),
  which cautions against assigning portfolio-average returns to an individual
  program.

## Score anchors and quantitative evidence

Assessment v2 can include `scoreAnchors` that recommend bounded dimension
scores from frozen quantitative evidence. The host validates that:

- quantitative evidence IDs are explicit and referenced;
- inferred values include derivation metadata;
- private evidence is not leaked into public summaries;
- citation momentum cannot be used as a novelty shortcut; and
- dimension scores outside a quantitative anchor require an override reason.

For valuation-only QEC refreshes, qualitative dimensions are retained from a
prior completed public English assessment, while quantitative evidence is
refreshed from the bound Scientific Demand snapshot. In that mode,
`scoreAnchors` are cleared so the refresh does not silently re-score qualitative
judgments without a new assessment pass.

## Snapshot, provenance, and refresh rules

Each frozen valuation snapshot records:

- the exact confirmed candidate;
- anchor papers and OpenAlex expansion results;
- market/economic evidence;
- citation components and formula ID;
- provider warnings or errors;
- visibility;
- `snapshotId`; and
- `contentHash`.

Assessment input binds the exact `snapshotId`, `contentHash`, full snapshot
hash, freshness advisory, visibility, and deterministic recalculation inputs.

A newer valuation snapshot does not mutate older assessments. Instead, a new
valuation-only run can be derived. The derived run writes `derivation.json` with
the source assessment run and refreshed snapshot ID, and the HTML report
includes a visible valuation-only refresh notice.

## Freshness and privacy

Freshness is advisory:

| Evidence class | Stale window |
|---|---:|
| citation | 90 days |
| hardware | 90 days |
| classical baseline | 90 days |
| market | 180 days |
| contract | 180 days |
| adoption | 180 days |

Private evidence has no automatic public expiry. Visibility propagates upward:
any output depending on private input is private. Public rendering redacts
sensitive numeric fields, including value, interval, currency, and derivation.
Public-build validation fails closed if private valuation fields are not
redacted.

## What the method deliberately does not claim

The current method does not claim that:

- citation evidence proves novelty;
- raw citation count alone measures problem importance;
- broad market estimates are problem-specific value estimates;
- public vendor investment is capturable value for a single research problem;
- modeled Technical Success is a sealed-benchmark result; or
- local external evidence is trusted knowledge.

Those limits are part of the design. The model is meant to produce a
repeatable, inspectable advisory ranking while keeping uncertainty and
provenance visible.

## Main implementation references

- Assessment policy and verdict arithmetic:
  `lib/assessments/policy.mjs`
- Scientific Demand Score:
  `lib/valuations/citations.mjs`
- Technical Success point estimates:
  `lib/assessments/point-estimates.mjs`
- Valuation formulas and interval utilities:
  `lib/valuations/formulas.mjs`
- Valuation snapshot storage:
  `lib/valuations/snapshot-store.mjs`
- Privacy and public redaction:
  `lib/valuations/privacy.mjs`
- QEC valuation-only refresh:
  `lib/qec-portfolio/valuation-only-refresh.mjs`
- QEC portfolio public reader:
  `lib/qec-portfolio/reader.mjs`
- Assessment output schema:
  `schemas/research-problem-assessment.schema.json`
- Quantum valuation snapshot schema:
  `schemas/quantum-valuation-snapshot.schema.json`
