# QEC valuation-only report refresh

## Context and decision

The QEC portfolio has 21 previously completed English version-2 assessments. A
new deterministic Scientific Demand Score is now available from versioned
OpenAlex evidence, but the local Codex CLI cannot produce more qualitative
assessments until its usage limit resets on 2026-08-05.

Three responses were considered:

1. Wait for the Codex limit to reset. This preserves the original online path
   but leaves the local portfolio incomplete for several days.
2. Rewrite the old assessment artifacts. This is rejected because completed
   snapshots and reports are immutable audit records.
3. Create new valuation-only assessment revisions. This is the selected
   approach: preserve each latest completed qualitative assessment, rebuild
   only its quantitative packet from a new verified valuation snapshot, and
   publish a new explicitly labelled immutable report.

The user approved option 3 on 2026-07-30.

## Scope

The refresh covers exactly `Prob-001` through `Prob-021`, all in the quantum
error-correction and fault-tolerance portfolio. It does not change problem
lifecycle state, trusted knowledge, old valuation snapshots, or old assessment
runs. It does not invent missing citations or convert missing evidence to zero.

## Architecture

A host-owned valuation-only refresher will compose existing boundaries rather
than bypass them:

- The valuation manager creates or reuses a complete snapshot whose citation
  formula is `qec-scientific-demand-v1`.
- The artifact store supplies the newest completed, public, English version-2
  assessment as the qualitative source.
- A pure rebasing function copies qualitative fields and replaces the complete
  quantitative packet with values derived from the verified new snapshot.
- The ordinary assessment contract validates the rebased envelope and
  recomputes aggregate scores.
- The ordinary input-snapshot and report renderers create a new immutable run.
- The portfolio verifier accepts the result only when all 21 reports are bound
  to verified current-formula snapshots.

No report is published partially. A problem with insufficient evidence remains
an explicit refresh error and cannot be presented as a completed portfolio row.

## Quantitative rebasing

The following qualitative fields remain byte-for-byte equivalent after normal
contract normalization: dimensions, rationales, evidence references, verdict,
recommendation, confidence, bottleneck, reframe, and information gaps.

The quantitative packet is rebuilt as follows:

- Snapshot identity, visibility, and freshness come from the verified snapshot.
- Scientific Demand Score, components, evidence confidence, paper count,
  coverage, momentum, sources, and formula ID come from the snapshot citation
  record. The displayed score is one exact `/ 100` point value.
- Technical feasibility remains evidence-dependent. The existing host formula
  derives one exact modeled technical-success point estimate from the retained
  qualitative dimensions; it is not reported as a measured gate result.
- Social-value and commercial-investment proxies come from the frozen public
  market evidence. They retain their proxy labels and must not be described as
  problem-specific revenue.
- Capturable value and information value remain evidence gaps when no valid
  problem-specific model exists. The UI uses actionable English evidence-gap
  copy, never a numeric zero or the literal label `Unknown`.
- Score anchors are empty for a valuation-only revision. The retained
  qualitative Importance score is not silently re-scored by a process that did
  not rerun the qualitative assessment.

## Provenance and presentation

Every derived report visibly states:

> Qualitative assessment retained from a prior completed run; quantitative
> valuation refreshed from the bound Scientific Demand snapshot.

The new run records the source run ID and source snapshot ID in a dedicated
local derivation artifact. The report and portfolio remain English-only. The
latest completed revision supersedes failed attempts in the local UI without
deleting them.

## Failure handling

- OpenAlex provider failure, incomplete normalized evidence, or an unverified
  snapshot prevents publication for that problem.
- A missing or invalid prior completed assessment prevents publication.
- Contract, snapshot binding, report rendering, or atomic publication failure
  leaves both old and newly staged artifacts unchanged.
- Codex usage-limit failures are retained for audit but are never selected as
  portfolio reports.
- Rerunning the refresher reuses an already completed report bound to the same
  snapshot and source run.

## Testing and acceptance

Tests are written before implementation and cover:

- qualitative fields are retained while quantitative fields are replaced;
- Scientific Demand Score and modeled technical success are exact point values;
- missing citation evidence is rejected instead of converted to zero;
- source-run and snapshot provenance is stored;
- old artifacts remain byte-identical;
- reruns are idempotent;
- reports contain the provenance notice and contain no visible Chinese,
  `Unknown`, `Pending`, or score ranges;
- the final verifier reports exactly 21 current-formula snapshots and 21 bound
  completed English reports.

Acceptance requires all targeted tests, the QEC verification command, the app
build, and a local HTTP smoke test of the portfolio and a representative report.
