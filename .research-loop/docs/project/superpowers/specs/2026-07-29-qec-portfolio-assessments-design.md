# QEC Problem Portfolio Assessments

## Status

Approved in conversation on 2026-07-29. The user selected scope B: keep the
existing `Prob-001`, register twenty new QEC problems as `Prob-002` through
`Prob-021`, and evaluate all twenty-one records with the same quantum valuation
and V/A/S assessment policy.

The trusted-knowledge resolver returned `ambiguous` results with no direct QEC
portfolio match. The portfolio therefore uses an explicitly labelled external
evidence route. External papers, citation metadata, market reports, and vendor
roadmaps remain external evidence and are never promoted into `knowledge/`.

## Outcome

The local Problem Console will contain twenty-one QEC problems. Every problem
will have:

- one valid problem record;
- a frozen public valuation snapshot with paper and market evidence;
- one completed assessment using Research Value, Autoresearch Fit, and Combined
  Priority;
- an English-only detailed HTML report; and
- a row on a local QEC portfolio comparison page.

No assessment starts an autoresearch campaign. New records remain `draft` and
all recommendations remain advisory.

## Portfolio

`Prob-001` remains `AutoQEC CSS Distance Campaign`. The twenty new records are:

1. `Prob-002` — Finite-Length qLDPC Code Search Under Hardware Constraints
2. `Prob-003` — Circuit-Level qLDPC Decoder Optimization
3. `Prob-004` — Real-Time Decoder Tail-Latency Minimization
4. `Prob-005` — Bounded-Memory Streaming QEC Decoder
5. `Prob-006` — Adaptive Decoding Under Correlated and Drifting Noise
6. `Prob-007` — Leakage-Aware Decoder and Reset-Policy Co-Design
7. `Prob-008` — Erasure-Biased Code–Decoder Co-Design
8. `Prob-009` — Generalizable Neural Decoder with Calibrated Uncertainty
9. `Prob-010` — Rare-Event Logical Failure Estimation
10. `Prob-011` — Reproducible Cross-Code QEC Benchmark Suite
11. `Prob-012` — Syndrome-Extraction Schedule Search
12. `Prob-013` — Flag-Sharing Ancilla Circuit Synthesis
13. `Prob-014` — Noise-Aware Stabilizer Measurement Scheduling
14. `Prob-015` — Lattice-Surgery Routing and Scheduling
15. `Prob-016` — Multi-Level Magic-State Factory Optimization
16. `Prob-017` — Fault-Tolerant Code-Switching Protocol Synthesis
17. `Prob-018` — Bias-Preserving Logical Operation Co-Optimization
18. `Prob-019` — Bosonic–Outer-Code Concatenation Co-Design
19. `Prob-020` — End-to-End Fault-Tolerant Resource Allocation Under Uncertainty
20. `Prob-021` — Automated Fault-Tolerance Verification for QEC Circuits

The exact titles, summaries, questions, gates, source counts, manifest fields,
timestamps, and file paths are the approved preview in the conversation. The
implementation must not silently revise them. Any collision returned by the
problem publisher stops the batch and requires a new preview and confirmation.

## Problem registration

Each new problem is published through the existing `make problem-publish`
boundary. Every staging directory contains exactly:

```text
problem.json
problem.md
generation/initial-prompt.md
generation/transcript.md
generation/decision.md
```

The records use `status: "draft"`, `domain: "quantum-computing"`,
`quantumArea: "error-correction-and-fault-tolerance"`, and the approved
problem-specific gate with readiness `specified`. The generated markdown and
all portfolio-visible problem text, labels, and reports are English only. The
generation transcript and initial prompt preserve the user-visible discussion
for auditability and may therefore contain the user's original Chinese text;
those audit files are not rendered by the portfolio or problem pages.

The publisher remains the only operation that makes a staged problem visible.
The batch invokes it once per candidate in ascending ID order and rebuilds the
generated index using existing repository commands.

## Evidence and valuation

Each problem receives a problem-specific technical anchor plus the common
economic evidence spine approved in the preview:

- McKinsey Quantum Technology Monitor 2026 for the projected internal quantum
  computing market range;
- IBM's 2026 quantum investment announcement as a vendor investment signal; and
- the problem-specific paper or official benchmark source shown in the preview.

OpenAlex is the frozen citation provider used by the existing valuation service.
When available, Crossref or Semantic Scholar metadata may be retained as a
cross-check but never substituted silently for the configured provider.
Scientific attention is normalized by publication year and field. Raw citation
totals do not score novelty and do not get added directly to V, A, or S.

The common market range is an enabling-value proxy, not capturable revenue.
`capturableValue` remains unknown unless a problem-specific pricing, licensing,
contract, or willingness-to-pay source exists. Unknown values are not encoded as
zero. Each snapshot freezes source URLs, retrieval dates, units, base year,
evidence tier, derivation, and low/base/high intervals.

## Assessment policy

Every completed assessment uses the repository's existing six Research Value
dimensions and seven Autoresearch Fit dimensions. V and A remain 0–100 weighted
scores and S remains their harmonic mean. Evidence states remain `supported`,
`inferred`, or `unknown`, with unknowns expressed as intervals.

The quantitative layer may anchor Importance, Plausibility, Learning from
failure, Generality, and Expected value relative to cost within the policy's
declared limits. It must not alter A weights, use citation counts as novelty, or
turn market TAM into problem value. Every report includes the verdict,
recommendation, confidence, dimension table, largest bottleneck, one bounded
reframe when applicable, assumptions, evidence gaps, sensitivity, and immutable
snapshot identity.

## Batch orchestration

A repository-local batch command accepts the approved catalog and performs
these phases in order:

1. validate that only `Prob-001` exists and `Prob-002` is the next ID;
2. stage and publish `Prob-002` through `Prob-021` with the existing publisher;
3. refresh the generated problem index and verify twenty-one QEC records;
4. prepare one valuation candidate per problem;
5. confirm only the exact approved anchors and public assumptions;
6. freeze one immutable snapshot per problem;
7. run one assessment per problem, selecting the external-valuation resolver
   alternative when the trusted resolver is ambiguous and no QEC page applies;
8. verify all completed artifacts and render the portfolio comparison data.

The batch is restartable. It skips an already completed phase only after
verifying its artifact hashes and contracts. It does not overwrite an existing
problem, valuation snapshot, assessment run, or generated report. Concurrency is
bounded so local Codex and evidence providers are not flooded; failures are
recorded per problem and do not make incomplete runs look successful.

## Local comparison page

The local-only page presents one row per problem with:

- problem ID and title;
- verdict and confidence;
- Research Value, Autoresearch Fit, and Combined Priority with intervals;
- normalized scientific attention;
- technical-success estimate;
- industry/social enabling-value proxy;
- capturable-value state;
- largest bottleneck; and
- links to the problem page and detailed assessment report.

Rows default to descending Combined Priority and can be sorted by V, A, S,
verdict, or scientific attention. The page clearly labels the comparison as
external-evidence-backed and advisory. It is available only through the local
development server; deployed static output does not expose assessment artifacts
or executable routes.

## Error handling

- A problem ID collision stops publication before the colliding target is
  overwritten.
- Missing or invalid anchor metadata leaves the affected metric unknown and
  records a warning.
- Provider rate limits use bounded retries and preserve prior snapshots.
- A valuation candidate requiring material private information remains at
  confirmation instead of inventing a value.
- An invalid structured assessment is retained as a failed run with diagnostics
  and is absent from the completed comparison rows.
- A report containing CJK text fails the English-only portfolio verification.

## Verification

Completion requires evidence for every explicit outcome:

1. `find problems -maxdepth 2 -name problem.json` returns `Prob-001` through
   `Prob-021` with no gaps or extras.
2. All twenty new draft records pass the existing problem schema, draft
   contract, publisher, and index tests.
3. Every problem has at least one verified frozen valuation snapshot with the
   exact three-file snapshot shape and valid content hash.
4. Every problem has one completed assessment whose input binds that snapshot
   and whose report passes the assessment contract.
5. All twenty-one reports and portfolio-visible strings contain no CJK code
   points.
6. The full local test suite passes.
7. Browser verification confirms twenty-one comparison rows, working problem
   links, working report links, readable V/A/S labels, and no visible Chinese.

## Non-goals

- Promoting external evidence into trusted knowledge.
- Automatically accepting, rejecting, or launching any problem.
- Estimating team-capturable revenue without direct evidence.
- Supporting non-QEC domains in this portfolio batch.
- Replacing the existing problem publisher, valuation contracts, assessment
  policy, or preserved dashboard appearance.
