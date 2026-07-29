# Quantum Research-Problem Valuation

## Status

Approved section by section in the product-design conversation on 2026-07-29.
This document is the implementation boundary. It does not promote external
evidence into trusted knowledge and it does not authorize an assessment to
start an autoresearch campaign.

The trusted-knowledge resolver returned `no-match` for this design question.
The methods and papers cited below are therefore external evidence, not learned
Research Loop knowledge.

## Problem

The current assessment policy combines six research-value dimensions into `V`,
seven autoresearch-fit dimensions into `A`, and combines them harmonically into
`S`. Its qualitative evidence intervals are useful, but they do not make the
scientific attention, technical path, research cost, or potential economic
value of a problem independently auditable.

For quantum-computing problems only, Research Loop will add a quantitative
evidence layer that:

1. measures scientific attention with field- and publication-year-normalized
   paper influence rather than raw citation totals;
2. models technical feasibility against the best classical baseline and the
   full quantum resource/cost path;
3. estimates both industry/social value and value capturable by the team;
4. values information produced by a research step, including a useful negative
   result; and
5. anchors the existing `V` dimensions without replacing `V`, `A`, `S`, or the
   verdict policy.

The product must expose uncertainty rather than turn weak market claims or a
large citation count into a precise-looking score.

## Goals

- Give every quantitative value a source, date, unit, base year, evidence tier,
  derivation, and low/base/high range.
- Research public inputs automatically; ask the user only to confirm assumptions
  that materially change the decision or depend on private information.
- Freeze every evidence refresh into an immutable snapshot so an old assessment
  remains reproducible.
- Keep the existing assessment surface recognizable and preserve all version-1
  assessment artifacts.
- Make missing evidence explicit as `unknown`, never as zero.

## Non-goals

- Supporting domains other than quantum computing.
- Treating company financing valuations, headline TAM, patent counts, or raw
  citation totals as a problem valuation.
- Monte Carlo simulation, portfolio optimization, automated patent valuation,
  or automated licensing valuation in the first release.
- Writing external evidence into `knowledge/` or treating a valuation snapshot
  as trusted knowledge.
- Automatically starting autoresearch after an assessment.

## User experience

The problem page follows one explicit flow:

```text
check quantum scope
  -> refresh external evidence
  -> review material assumptions
  -> freeze snapshot
  -> run assessment
  -> inspect headline metrics and the detailed audit report
```

The page state is one of:

- `no_evidence`: no usable snapshot exists;
- `researching`: an explicit refresh is in progress;
- `needs_confirmation`: material assumptions require review;
- `ready`: a frozen snapshot can be assessed;
- `stale`: a snapshot is usable but at least one evidence class is old; or
- `research_failed`: refresh failed and may be retried without damaging prior
  snapshots.

Refresh is always explicit. It creates a new snapshot; it never updates an old
snapshot in place and never silently changes an old assessment.

The existing assessment panel remains the primary surface. It gains compact
cards for `V`, `A`, `S`, scientific attention, technical-success probability,
industry/social value, and capturable value, plus the largest sensitivity. The
existing detailed report gains the formulas, assumptions, paper set, sources,
score anchors, overrides, and snapshot identity. There is no separate valuation
workspace in the first release.

## System modules

### 1. Quantum Scope Gate

New problems eligible for quantitative valuation declare:

```json
{
  "domain": "quantum-computing",
  "quantumArea": "algorithms-and-applications"
}
```

Supported `quantumArea` values cover:

- algorithms and applications;
- quantum error correction and fault tolerance;
- compilation and architecture;
- computing hardware and control;
- resource estimation and benchmarks; and
- classical simulation or verification whose direct purpose is quantum
  computation.

Quantum sensing, quantum communication, general quantum materials, and general
many-body physics are excluded unless the problem directly serves quantum
computation. A legacy problem without the new fields may be classified for the
assessment snapshot, but the classifier must not mutate the problem. An
ambiguous classification returns `needs_input`.

Non-quantum problems continue through the version-1 assessment flow and display
that quantitative valuation is not yet supported for their domain.

### 2. Evidence Snapshot

Valuation inputs and immutable refresh results live under the problem tree:

```text
problems/<id>/valuation/
  inputs.json
  snapshots/<snapshot-id>/
    manifest.json
    papers.json
    market-evidence.json
```

`inputs.json` holds the current scope, confirmed anchor identifiers, user
confirmations, and optional private inputs. It is not an assessment artifact and
may change. The snapshot copies normalized, decision-relevant inputs into its
manifest; the assessment also embeds every numeric model input needed to
recalculate its outputs.

The snapshot identifier includes a sortable timestamp and a content-hash
prefix. The full content hash covers canonical JSON for all three files. An
assessment records `snapshotId` and `contentHash`, and validation fails if they
do not identify the exact frozen content.

Snapshots are external evidence. They may be committed when appropriate, but
they are never resolvable trusted knowledge and never appear under
`public/knowledge/`.

### 3. Automated Evidence Research

The system starts with one to ten user-confirmed anchor papers or persistent
identifiers. It may suggest the initial anchors, but it must show them for
confirmation before the first refresh.

The paper collector uses OpenAlex metadata to expand one hop through cited,
citing, and topic-neighbor records. It filters candidates by title/abstract
relevance to the normalized problem, deduplicates by DOI and stable identifier,
and freezes the accepted set in `papers.json`. Each record retains the metadata
needed to reproduce its inclusion and metric calculation.

Commercial research searches public primary sources first: government data,
regulatory disclosures, public contracts, public prices, and original technical
or economic studies. Authoritative industry studies are secondary evidence;
vendor case studies and news reports are weak evidence. A value without a
reliable public source remains an explicit assumption.

Every extracted atomic value records:

- value or interval, unit, currency, and price base year;
- source URL or DOI, publication/access date, and locator;
- geographic, technical, and beneficiary scope;
- evidence tier;
- `reported` versus `inferred` status;
- transformation or formula when inferred; and
- the snapshot item IDs it depends on.

The agent performs search, relevance matching, extraction proposals, scenario
construction, and explanation. Deterministic host code validates schemas,
normalizes units, checks currencies and interval ordering, evaluates formulas,
canonicalizes JSON, hashes content, and freezes snapshots. Agent output cannot
become a final quantitative value until it passes this boundary.

When sources disagree, the snapshot retains the disagreement and widens the
scenario interval. Weak evidence lowers confidence. Missing evidence produces
`unknown`; it is never silently imputed. Failure in one evidence class may
produce an incomplete snapshot, but all affected outputs and score anchors must
show the degradation.

### 4. Citation Engine

Raw citation count is audit-only. The headline metric is:

```text
ScientificAttention
  = 100 * weightedMedian(values = normalizedPercentile_i,
                         weights = relevance_i)
```

`normalizedPercentile_i` is the paper's citation percentile within its field and
publication-year cohort. Relevance weights come from the frozen inclusion
decision and are bounded and normalized by deterministic host code. The engine
also reports:

- `momentum`: a robust comparison of citation velocity across the latest two
  complete calendar years, shown separately and never used as novelty evidence;
- `coverage`: the share of relevant included papers with usable normalized
  data, which changes confidence but not the headline value; and
- `concentration`: whether the result is dominated by one or a few papers.

The weighted median prevents one blockbuster paper from defining the entire
problem. If too few relevant papers have comparable data, scientific attention
is an unknown interval rather than a fabricated point estimate.

This design follows the caution in the Leiden Manifesto against replacing
expert judgment with a single bibliometric number and uses the same broad
field-normalization motivation as the Relative Citation Ratio. OpenAlex exposes
the normalized-percentile and yearly-count fields required by the first
implementation.

### 5. Feasibility and Total Cost of Ownership

Technical feasibility is a conditional stage tree:

```text
theory
  -> small validation
  -> resource-affordable implementation
  -> advantage over the best classical baseline
  -> workflow adoption
```

Each stage stores a low/base/high conditional success probability, elapsed time,
incremental cost, evidence references, the current bottleneck, and explicit
continue/stop/pivot criteria. The first release multiplies the conditional stage
intervals to obtain the technical-success interval and sums discounted
stage-dependent cost-to-go. It does not run Monte Carlo simulation.

The resource model must state the best classical baseline, quality/accuracy
target, logical and physical quantum resources when applicable, runtime,
throughput, error-correction assumptions, infrastructure cost, and integration
cost. A claim of quantum value without a comparable classical workflow remains
incomplete.

Outputs are technical-success probability, time to useful deployment,
cost-to-go, total cost of ownership, and the largest technical bottleneck. Both
positive feasibility studies and negative resource estimates are valid
evidence; a negative result can still have information value.

### 6. Dual-track Valuation and Information Value

The first release uses low/base/high scenario calculation, expected net present
value, a staged decision tree, and value of information.

Industry/social value is built bottom-up:

```text
gross social benefit_t
  = beneficiaries_t
  * benefit per use_t
  * uses per beneficiary_t
  * adoption_t
  * problem attribution_t

expected social benefit_t
  = P(technical success by t) * gross social benefit_t

social ENPV
  = sum_t (expected social benefit_t - expected social cost_t)
          / (1 + social discount rate)^t
```

Capturable value is a separate track:

```text
expected capturable benefit_t
  = P(technical success by t)
    * gross attributable benefit_t
    * capture share_t

capturable ENPV
  = sum_t (expected capturable benefit_t - expected team cost_t)
          / (1 + private discount rate)^t
```

Capture share requires evidence from a plausible mechanism such as licensing,
contract research, usage pricing, a product margin, or a documented business
model. Company valuations, patent counts, and headline market size may bound a
scenario but are not primary valuation inputs.

Value of information remains separate from deployment value:

```text
EVSI = E_y[max_a E(NB_a | y)] - max_a E(NB_a)
ENBS = EVSI - study cost
```

The report identifies whether the proposed research step is valuable because it
may deploy a solution, because it cheaply resolves a costly uncertainty, or
both. It also reports the inputs with the greatest effect on the decision.

Research and pre-deployment costs are charged in the states where they are
incurred, including failed paths; multiplying every cost by final success
probability would understate the cost of failure.

Public information can usually support scientific attention, market bounds,
classical baselines, resource estimates, and public price/cost ranges. Private
team cost, capture mechanism, customer constraints, and contractual economics
may require user confirmation. If the user supplies none, social value still
runs and capturable value is labeled `public-evidence scenario` with a wide or
unknown interval.

### 7. Assessment Policy Version 2

Version 2 preserves the current research-value and autoresearch dimensions,
their weights, the harmonic combination, and the verdict thresholds. It adds
quantitative anchors to the research-value dimensions:

| Research-value dimension | Quantitative evidence anchor |
|---|---|
| Importance | Social/industry ENPV, beneficiary scale, scientific attention |
| Gap and novelty | Unresolved evidence, method gaps, literature concentration; citations are not novelty |
| Plausibility | Stage success, quantum resources, classical baseline, TCO |
| Learning from failure | EVSI/ENBS and reusable outputs from a negative result |
| Generality and publication | Transfer across instances and relevant research audience |
| Expected value relative to cost | Dual-track ENPV, ENBS, cost, and time intervals |

Quantitative metrics constrain a recommended score interval; they are not bonus
points added to `V`. The evaluator selects a dimension score within the
recommended interval and explains the choice. A score outside it requires a
structured override reason. Raw dollars, citation metrics, or success
probabilities are displayed beside the scores and are never added again to the
weighted total.

The first release deliberately does not claim a globally calibrated conversion
from dollars or citations to a 0-5 point score. The agent proposes the interval
from the complete evidence packet; the host enforces deterministic consistency
rules, including interval ordering, evidence/ confidence compatibility,
required override reasons, and no use of an unknown input as a zero. This keeps
the recommendation auditable without inventing a universal exchange rate
between scientific and economic value.

`A` is unchanged. As today, a valuable problem may still be unsuitable for the
autonomous loop.

### 8. Report and Panel

The compact problem-page cards show:

- existing `V`, `A`, `S`, confidence, verdict, and recommendation;
- scientific attention and its coverage warning;
- technical-success probability and time to utility;
- industry/social value;
- capturable value; and
- the largest sensitivity or bottleneck.

The detailed audit report adds the evidence hierarchy, paper set, formulas,
atomic inputs, scenario table, stage tree, classical comparator, score anchors,
overrides, missing information, source freshness, snapshot ID, and content hash.
All external claims are visibly labeled as external evidence. No report content
is published into trusted knowledge.

## Assessment contract and compatibility

Version-1 assessment artifacts remain valid and render unchanged. A new
assessment uses `assessment.schemaVersion = 2` and retains every existing field.
It adds one `quantitativeEvidence` object beneath the assessment:

```json
{
  "domain": "quantum-computing",
  "quantumArea": "algorithms-and-applications",
  "snapshot": {
    "snapshotId": "...",
    "contentHash": "...",
    "createdAt": "...",
    "freshness": "fresh"
  },
  "scientificAttention": {},
  "technicalFeasibility": {},
  "socialValue": {},
  "capturableValue": {},
  "informationValue": {},
  "scoreAnchors": {},
  "sensitivity": {},
  "assumptions": [],
  "warnings": []
}
```

Money fields retain original currency, price base year, conversion source, and
display currency. Optional numeric evidence uses explicit known/unknown unions;
JSON null or numeric zero must not ambiguously mean missing. Every inferred
output records its formula identifier and input IDs.

Historical artifacts are never batch-migrated or recomputed. The report and
view-model layers dispatch on schema version. A new valuation refresh does not
make an old assessment invalid; it only allows the page to show that newer
evidence is available.

## Freshness policy

Freshness is advisory and evidence-class-specific:

- normalized citation/topic data: stale after 90 days;
- hardware capability, quantum resource cost, and classical baseline: stale
  after 90 days;
- market, price, contract, and adoption evidence: stale after 180 days;
- government statistics: stale at the source's announced next publication; and
- user-provided private inputs: no fixed expiry, only explicit user replacement.

Staleness displays a refresh prompt but does not invalidate the frozen snapshot
or alter an assessment.

## Trust, privacy, and failure boundaries

- The trusted-knowledge resolver still runs before the assessment makes any
  learned-knowledge claim. Valuation snapshots are external evidence and are
  never a resolver fallback.
- Research and refresh remain loopback-only local operations. No deployed route
  triggers external research or execution.
- Agent-written candidates cannot write trusted knowledge, publish private
  inputs, or start a campaign.
- Private team inputs remain problem-local, carry `visibility: private`, and are
  redacted from public report output. Any snapshot or assessment that depends on
  them is marked private, and public build validation must reject an unredacted
  private value. Making a value public is a separate explicit user action.
- Stored web evidence contains metadata, short factual extracts or paraphrases,
  and locators—not mirrored copyrighted reports.
- Partial provider failure preserves old snapshots. A new incomplete snapshot
  identifies failed providers, retryability, and every output degraded to
  `unknown`.
- Timeouts, malformed responses, unit mismatches, unsupported currencies,
  missing locators, hash mismatches, and invalid formulas fail closed before
  snapshot freezing.

## Quality requirements and verification

Implementation follows test-driven changes and must cover:

1. domain and quantum-area scope classification, including ambiguous legacy
   problems and non-quantum fallbacks;
2. deterministic paper deduplication, relevance inclusion, field/year
   normalization, coverage, concentration, and insufficient-data behavior;
3. strict atomic-evidence schemas, unit/currency/base-year normalization, and
   reported-versus-inferred provenance;
4. immutable snapshot creation, canonical hashing, tamper detection, and
   assessment-to-snapshot resolution;
5. stage-tree probability, time, cost-to-go, TCO, ENPV, EVSI, and ENBS formulas
   against hand-calculated fixtures;
6. low/base/high interval propagation and explicit `unknown` behavior;
7. score-anchor consistency, no double counting, and mandatory override reasons;
8. version-1 rendering compatibility and version-2 schema validation;
9. freshness transitions without snapshot mutation;
10. provider timeout, partial failure, retry, and stale-snapshot fallback;
11. HTML escaping and safe external-link rendering;
12. private-input propagation, report redaction, and rejection of private data
    by public build paths; and
13. end-to-end local flow from explicit refresh through confirmation, frozen
    snapshot, assessment, cards, and detailed report.

The full repository test suite and build remain required. The preserved
dashboard files are not redesigned to make the feature pass.

## Delivery sequence

1. Add strict valuation/evidence contracts and deterministic formula tests.
2. Add quantum scope fields and backward-compatible assessment schema v2.
3. Add snapshot storage, canonical hashing, freshness, and fixtures.
4. Add paper metadata collection and citation metrics.
5. Add commercial evidence candidates, confirmation, and dual-track formulas.
6. Add policy anchors, Codex contract changes, and host validation.
7. Extend the report and progressively enhance the existing assessment panel.
8. Run focused, full-suite, build, and end-to-end verification.

## Deferred and rejected alternatives

- **Deferred:** Monte Carlo uncertainty, patent/licensing automation, and
  cross-problem portfolio optimization. The scenario model must stabilize first.
- **Rejected:** allocating a public or private company's valuation down to a
  research problem. Company value reflects a portfolio and financing context,
  not the marginal value of one research question.
- **Rejected:** direct additive bonuses for citations or market size. This would
  double count evidence and reward fashionable or exaggerated markets.
- **Rejected:** mandatory user completion of a blank valuation form. Public
  inputs are the system's research responsibility; user attention is reserved
  for material judgment and private information.
- **Rejected:** background refresh that mutates current results. Reproducibility
  requires explicit, immutable snapshots.

## External method references

- [OpenAlex developer documentation](https://developers.openalex.org/).
- Hicks et al., [The Leiden Manifesto for research metrics](https://doi.org/10.1038/520429a).
- Hutchins et al., [Relative Citation Ratio](https://doi.org/10.1371/journal.pbio.1002541).
- Bova, Goldfarb, and Melko, [Quantum Economic Advantage](https://doi.org/10.1287/mnsc.2022.4578).
- Schneider et al., [A generic real-options model for R&D projects](https://doi.org/10.1111/j.1467-9310.2007.00500.x).
- Fenwick et al., [Value of Information Analysis for Research Decisions](https://doi.org/10.1016/j.jval.2020.01.001).
- Lubinski et al., [Application-Oriented Performance Benchmarks for Quantum Computing](https://doi.org/10.1109/TQE.2023.3253761).
- Beverland et al., [Assessing requirements to scale to practical quantum advantage](https://arxiv.org/abs/2211.07629).
- Mozgunov, Marshall, and Anand, [Applications and resource estimates for open system simulation](https://arxiv.org/abs/2406.06281).
- Bellonzi et al., [Feasibility of accelerating homogeneous catalyst discovery](https://arxiv.org/abs/2406.06335).
- Penuel et al., [Detailed assessment of calculating drag force with quantum computers](https://arxiv.org/abs/2406.06323).
