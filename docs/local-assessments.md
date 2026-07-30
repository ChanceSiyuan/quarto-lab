# Local Assessment Reports

Local assessment reports are generated only when the app is running through
`make dev` or `npm run dev`. The deployed static showcase cannot start Codex
and does not publish assessment artifacts.

For the scoring formulas, evidence rules, and QEC valuation workflow semantics,
see [Assessment Methodology](assessment-methodology.md).

## Running an assessment

1. Start the local app with `make dev`.
2. Open a problem page under `/problems/Prob-###`.
3. For ordinary or legacy problems, press `Run assessment`.
4. Wait for the panel to show the advisory verdict, recommendation, confidence,
   and V/A/S scores.
5. Open the detailed report link for the full audit table and evidence
   appendix.

## Quantum valuation workflow

For problems whose manifest contains `domain: quantum-computing` and a
supported `quantumArea`, assessment v2 requires a frozen valuation snapshot
before scoring.

1. Set `OPENALEX_API_KEY` before starting `make dev`. The live OpenAlex client
   returns `OPENALEX_KEY_REQUIRED` if no key is configured, and the valuation
   job records an incomplete/degraded state instead of silently using uncited
   citation evidence.
2. Open the quantum problem page and press `Research evidence`.
3. Review the public evidence candidate. Confirm exact anchor papers and any
   material assumptions requested by the panel.
4. Press `Confirm and freeze snapshot`. This writes an immutable valuation
   snapshot under the problem directory.
5. Once the panel shows `Evidence ready`, press `Run assessment`. Codex receives
   only the host-frozen valuation packet for score anchors/rationales; it must
   not browse, refresh, relabel the evidence as trusted knowledge, mutate the
   problem lifecycle, or start autoresearch.

If OpenAlex or another evidence provider fails, the valuation manager may still
freeze an incomplete snapshot. Missing values remain explicit `{ state:
"unknown" }` values and never become fake zeroes; the later assessment can widen
or omit quantitative anchors accordingly.

## Artifacts

Each accepted run is stored under
`problems/Prob-###/assessments/YYYYMMDDTHHMMSSZ-abcdef/`.

Completed runs include `run.json`, `input.json`, `assessment.json`,
`report.html`, `events.jsonl`, and `stderr.log`. Clarification runs include
`clarification.json`. Failed and interrupted runs include diagnostics but no
formal assessment and no report.

The service never stages or commits these files, and `/problems/Prob-*` is
gitignored. Inspect a run directly under the path above (for example with
`find problems/Prob-###/assessments -maxdepth 2 -type f`) rather than expecting
it to appear in `git status`.

Quantum valuation input and snapshots live under
`problems/Prob-###/valuation/`:

- `inputs.json` contains public operator-provided valuation inputs.
- `inputs.private.json` is a local-only private overlay and is never sent to
  the public-source research process.
- `snapshots/<snapshotId>/manifest.json` records the confirmed candidate,
  current inputs, assumptions, computed citation/valuation outputs, snapshot
  identity, and provider errors when present.
- `snapshots/<snapshotId>/papers.json` stores bounded OpenAlex/citation
  expansion results.
- `snapshots/<snapshotId>/market-evidence.json` stores confirmed market or
  economic evidence.

Assessment v2 `input.json` binds the exact valuation `snapshotId`,
`contentHash`, full `snapshotHash`, advisory freshness result, visibility, and
deterministic recalculation inputs. A newer valuation snapshot is advisory: old
assessment reports remain readable and are not recomputed or mutated.

When `knowledge.ts resolve --query <text>` returns `ambiguous`, the local
service may apply one of that exact result's alternatives with
`--select-page <knowledge/...qmd>`. The flag is rejected when the query is no
longer ambiguous or the page was not one of its alternatives.

## Freshness and privacy

Freshness is advisory by evidence class. Citation, hardware, and classical
baseline evidence use 90-day windows; market, contract, and adoption evidence
use 180-day windows. Private evidence has no automatic public expiry and is
reported as private-local.

Visibility propagates upward: any output depending on `visibility: private`
must be treated as private. Public rendering redacts sensitive numeric fields
such as `value`, `interval`, `currency`, and `derivation`; public-build
validation rejects unredacted private valuation artifacts. Keep private values
in `inputs.private.json` or local assessment artifacts, not in trusted
`knowledge/`, `drafts/`, deployed pages, or public problem summaries.

## Manual smoke test with real Codex

Run this only when you are willing to consume local Codex quota:

```bash
codex login status
make dev
```

Then run one assessment from the browser and verify that:

- the Codex command is read-only;
- the panel shows an advisory recommendation;
- `problem.json` is unchanged;
- `report.html` opens locally; and
- `events.jsonl` and `stderr.log` stay under the problem's assessment run.

For a quantum problem, additionally verify that:

- `Research evidence` creates only valuation artifacts under
  `problems/<id>/valuation/`;
- confirmation freezes a snapshot before `Run assessment` is enabled;
- the detailed report shows the external-evidence banner and snapshot ID;
- private numeric sentinels are redacted from public-facing output;
- the problem lifecycle/status is not changed; and
- no autoresearch campaign is started by valuation or assessment actions.
