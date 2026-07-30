# Prob-000 expected attributable net social value example

## Status and decision

The user approved this design on 2026-07-30. The existing static
`Industry / social proxy` card for `Prob-000` will be replaced by one
problem-specific **Expected Attributable Net Social Value (EANSV)** example.
The headline display will be:

```text
+$180K USD 2026
```

The unrounded calculated value is USD 181,422.5451662417 in constant 2026
dollars. The UI value is a presentation rounding, not an independent input.

EANSV is the product's descriptive label for a deterministic synthesis of
standard social cost-benefit, counterfactual, and expected-value-of-information
ideas. It is not presented as a named formula copied from one publication.

## Problem and goal

The current static example displays the midpoint of a broad 2035
quantum-computing market range. That number describes an enabling industry, not
the value of solving Prob-000, and therefore cannot answer the problem-specific
question the card appears to answer.

This change will:

- calculate one auditable, problem-specific value for Prob-000 from explicit
  inputs;
- distinguish external evidence from economic and adoption assumptions;
- make the arithmetic reproducible in a reusable pure calculator;
- show only one rounded headline number while preserving the full derivation
  in the expanded card and documentation; and
- remove the broad industry value and its label from the rendered Prob-000
  page.

## Scope and non-goals

This is deliberately one worked example. It applies only to the preserved
static Prob-000 showcase.

It does not:

- assign EANSV values to production problems or the QEC portfolio;
- change valuation snapshots, assessment schemas, or trusted knowledge;
- claim that the example is calibrated, investment-grade, or empirically
  validated;
- infer the value of Prob-000 from a total-addressable-market percentage;
- promote external literature into `knowledge/`; or
- make the headline number editable in the UI.

## Metric definition

Let `R` mean performing the proposed research, `Y` a possible research result,
`a` a downstream action, `theta` uncertain states of the world, `W_R` social
welfare after the research result, `W_0` welfare without the research, and
`C_R` research cost. The conceptual definition is:

```text
EANSV = E_Y[max_a E_theta(W_R(a, theta, Y) | Y)]
        - max_a E_theta(W_0(a, theta))
        - PV(C_R)
```

For the finite Prob-000 example, each outcome branch already represents the
present value under the best modeled downstream action. The implemented form
is therefore:

```text
with_research_value = sum(outcome_probability * outcome_present_value)

EANSV = with_research_value
        - without_research_counterfactual_present_value
        - research_cost_present_value
```

This is a net incremental measure. A negative result is valid and must not be
clamped to zero.

## Evidence and assumption boundary

The fixture will identify every input as either external evidence or an
explicit modeling assumption.

External technical evidence supports only the following limited claims:

- the quantum-code distance problem has published algorithms and public
  software, including QDistRnd;
- improved distance-finding methods can affect a repeated computational task;
- QDistRnd is integrated into a public quantum-code software ecosystem; and
- public cloud CPU prices provide an observable unit-cost anchor.

The following are synthetic parameters, meaning transparent scenario inputs
rather than measurements of Prob-000's actual future impact:

- the number of adopting teams;
- runs per team per year;
- compute time avoided per run;
- researcher time released per run, its loaded hourly social value, and the
  fraction converted into productive work;
- outcome probabilities;
- duration of benefits;
- the value of avoiding futile follow-up work;
- the without-research counterfactual value; and
- research cost.

The external evidence makes the benefit mechanism plausible and supplies one
price anchor. It does not validate adoption, productivity, probabilities, the
counterfactual, or the final EANSV.

## Fixture contract

The example inputs will live in an independent fixture at:

```text
.research-loop/fixtures/showcase/problems/Prob-000/valuation.json
```

The fixture will contain:

- `schemaVersion`, `problemId`, metric ID, currency, and constant-dollar year;
- the social discount rate;
- three mutually exclusive outcome branches with probabilities;
- branch value models of either `annual-per-run` or `present-value`;
- the without-research counterfactual present value and research-cost present
  value;
- stable evidence records with titles, URLs, access/publication dates, and a
  concise statement of exactly what each source supports; and
- stable assumption records with labels, values, units, and rationale.

An `annual-per-run` branch contains the adopting-team count, runs per team per
year, benefit years, and two per-run benefit components:

```text
compute saving per run
  = round_to_cents(public compute price per instance-hour
                   * assumed instance-hours avoided)

productive researcher-time value per run
  = round_to_cents(hours released
                   * loaded hourly social value
                   * productive recapture fraction)

per-run benefit = compute saving + productive researcher-time value
annual benefit  = teams * runs per team per year * per-run benefit
branch PV       = sum(annual benefit / (1 + social discount rate)^year)
```

Rounding the two benefit components to cents is an explicit model rule. It
prevents a current cloud quote with six decimal places from implying false
precision in a per-run scenario input. Present-value branches are already
expressed in base-year dollars and are not discounted again.

The fixture must not store the headline `+$180K` or the final EANSV as an input.
Those values must be derived.

## Approved Prob-000 inputs and arithmetic

All values are constant 2026 USD. The social discount rate is 3.5 percent.

### Full-success branch

The branch probability is 0.35. The assumed adoption is 30 teams making 1,000
runs per team per year for five years, with cash-flow years 1 through 5.

The per-run benefit is USD 10.20:

```text
compute saving       = round_to_cents(0.403216 * 0.5) = 0.20
productive-time value = round_to_cents(0.5 * 100 * 0.20) = 10.00
per-run benefit                                        = 10.20

annual benefit = 30 * 1,000 * 10.20 = 306,000

branch PV = sum(306,000 / 1.035^year, year = 1..5)
          = 1,381,606.026894049
```

The USD 0.403216 unit price is an external price anchor. The avoided instance
hours, researcher time, hourly value, and recapture fraction are assumptions.

### Partial-success branch

The branch probability is 0.25. The assumed adoption is 10 teams making 500
runs per team per year for three years, with cash-flow years 1 through 3.

The per-run benefit is USD 5.10:

```text
compute saving       = round_to_cents(0.403216 * 0.25) = 0.10
productive-time value = round_to_cents(0.25 * 100 * 0.20) = 5.00
per-run benefit                                          = 5.10

annual benefit = 10 * 500 * 5.10 = 25,500

branch PV = sum(25,500 / 1.035^year, year = 1..3)
          = 71,441.74301329814
```

### Decision-useful negative-result branch

The branch probability is 0.40. Its modeled value is a USD 75,000 base-year
present value from avoiding futile follow-up work. This is an explicit
assumption, not a measured saving.

### Expected value and net value

```text
with-research value
  = 0.35 * 1,381,606.026894049
    + 0.25 * 71,441.74301329814
    + 0.40 * 75,000
  = 531,422.5451662417

without-research counterfactual PV = 100,000
research cost PV                    = 250,000

EANSV = 531,422.5451662417 - 100,000 - 250,000
      = 181,422.5451662417
```

The outcome probabilities sum to one. Both deducted values are explicit
assumptions. The counterfactual deduction prevents crediting the proposed
research for benefits expected to occur without it.

## Display rules

The static assessment panel will keep its three-card layout. Only the middle
card changes:

```text
Expected Attributable Net Social Value
+$180K USD 2026
```

The display formatter rounds the calculated EANSV to the nearest USD 10,000
for this magnitude and adds an explicit sign. The currency and constant-dollar
year come from the fixture. The expanded detail shows the compact arithmetic,
states that the result is scenario-based, distinguishes evidence from
assumptions, and links to the methodology documentation. It must not render
`Industry / social proxy` or `$57.0B USD 2035`.

The card component receives a calculated view model. It does not contain the
monetary result or copy the fixture inputs into JSX constants.

## Architecture and data flow

The implementation will use four small boundaries:

1. The Prob-000 fixture owns example inputs, evidence provenance, and assumption
   provenance.
2. A loader validates the fixture and rejects malformed or mismatched example
   data before the static page can be generated.
3. Pure functions in `src/lib/valuations/formulas.mjs` calculate branch present
   values, the probability-weighted with-research value, and EANSV.
4. The static page adapter formats the calculated result and supplies the card
   detail to `StaticAssessmentPanel`.

The main methodology document will explain the metric, reproduce the line-by-
line Prob-000 calculation, and state that broad industry forecasts are context,
not problem value.

## Validation and failure handling

Fixture loading or calculation fails closed when:

- the fixture is not for Prob-000 or uses an unsupported schema/metric ID;
- currency or constant-dollar year is absent;
- an amount, probability, rate, count, or duration is non-finite;
- a required amount or count is negative;
- a probability is outside `[0, 1]` or probabilities do not sum to one within a
  small numeric tolerance;
- the discount rate is less than or equal to -1;
- benefit years are absent, duplicated, non-integer, or non-positive;
- a value model kind is unsupported;
- an evidence or assumption reference is missing or duplicated; or
- an input classified as external or assumed lacks the corresponding
  provenance record.

The calculator accepts zero and negative final EANSV values. It returns the
unrounded intermediate values so tests and expanded documentation can audit the
result. Invalid data must fail the static load/build rather than silently hide
the card or substitute a fallback number.

## Testing and acceptance

Tests will be written before implementation and cover:

- cent rounding for both per-run benefit components;
- annual benefit and discounted branch PV calculations;
- probability-weighted expected value, counterfactual deduction, research-cost
  deduction, and an unclamped negative EANSV case;
- strict probability, numeric, year, model-kind, and provenance validation;
- exact Prob-000 intermediate results and unrounded EANSV;
- derivation of the rounded `+$180K USD 2026` display from fixture inputs;
- static rendering of the new label, value, and explanation; and
- absence of `Industry / social proxy` and `$57.0B USD 2035` from the rendered
  Prob-000 page.

Acceptance requires the targeted unit and static-page tests, the application
build, and a local page smoke test. Existing unrelated baseline failures will
be reported separately rather than attributed to this change.

## External references

The fixture and methodology documentation will cite sources directly and state
their limited evidentiary role:

- Pablo Olivares and Mikel Sanz, “QDistRnd: A GAP package for computing the
  distance of quantum error-correcting codes,” *Journal of Open Source
  Software* 7(72), 2022, DOI
  [10.21105/joss.04120](https://doi.org/10.21105/joss.04120).
- “Distance-Finding Algorithms for Quantum Codes and Circuits,” arXiv:
  [2603.22532](https://arxiv.org/abs/2603.22532), used as current external
  technical context rather than trusted knowledge.
- [qLDPC](https://github.com/qLDPCOrg/qLDPC), used only to document public
  software integration.
- [Google Cloud general-purpose machine pricing](https://cloud.google.com/products/compute/pricing/general-purpose),
  accessed 2026-07-30, used only as the mutable public unit-price anchor.
- National Institute of Standards and Technology, *Guidelines and Discount
  Rates for Benefit-Cost Analysis of Federal Programs*, NIST IR 7319, DOI
  [10.6028/NIST.IR.7319](https://doi.org/10.6028/NIST.IR.7319), for general
  cost-benefit structure.
- UK HM Treasury,
  [The Green Book](https://www.gov.uk/government/publications/the-green-book-appraisal-and-evaluation-in-central-government),
  for counterfactual appraisal, discounting, and uncertainty conventions; the
  worked example adopts its 3.5 percent headline social time preference rate
  as an explicit modeling choice rather than a universal rate.
- National Research Council, *Valuing Health for Regulatory Cost-Effectiveness
  Analysis* (2007), DOI
  [10.17226/11806](https://doi.org/10.17226/11806), for counterfactual and
  social-value framing.
- ISPOR Value of Information Analysis Task Force reports:
  [Report 1](https://doi.org/10.1016/j.jval.2020.01.001) and
  [Report 2](https://doi.org/10.1016/j.jval.2020.01.004), for EVSI/ENBS
  concepts.
- UK Department for Science, Innovation and Technology,
  [The value of public R&D](https://www.gov.uk/government/publications/the-value-of-public-rd/the-value-of-public-rd),
  for the warning that portfolio-average returns should not be assigned to an
  individual program.
