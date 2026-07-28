# Local Assessment Reports

Local assessment reports are generated only when the app is running through
`make dev` or `npm run dev`. The deployed static showcase cannot start Codex
and does not publish assessment artifacts.

## Running an assessment

1. Start the local app with `make dev`.
2. Open a problem page under `/problems/Prob-###`.
3. Press `Run assessment`.
4. Wait for the panel to show the advisory verdict, recommendation, confidence,
   and V/A/S scores.
5. Open the detailed report link for the full audit table and evidence
   appendix.

## Artifacts

Each accepted run is stored under
`problems/Prob-###/assessments/YYYYMMDDTHHMMSSZ-abcdef/`.

Completed runs include `run.json`, `input.json`, `assessment.json`,
`report.html`, `events.jsonl`, and `stderr.log`. Clarification runs include
`clarification.json`. Failed and interrupted runs include diagnostics but no
formal assessment and no report.

The service never stages or commits these files. Review them as ordinary local
repository changes.

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
