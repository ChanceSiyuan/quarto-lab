# Static Research Example Final Fix Report

## Findings addressed

1. Removed `.generated/problem-index.json` from Git tracking with `git rm --cached -- .generated/problem-index.json`. The generated file remains on disk, is ignored by `/.generated/`, and is still rebuilt by normal build, test, and lint commands.
2. Expanded `lib/problems/example-research.mjs` fixture validation before presentation. It now validates the static manifest, all consumed attempt fields, gate results, method and predecessor shape, metric ranges and count consistency, interpretations and learnings, provenance strings, ISO-valid timestamps, safe single-name artifacts, and exactly one accepted promoted attempt. Lookup functions retain deep-clone behavior.
3. Added negative fixture tests that prove malformed content is rejected before presentation, covering manifest disclaimer, title, promoted state, gate, method changes, metrics, interpretation, timestamp, and unsafe artifacts.
4. Changed the ledger description from `5 synthetic runs` to `5 synthetic attempts`; each attempt still displays its own 24-run metrics.

## Verification

- `PATH=/Users/nzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH node --test tests/example-research.test.mjs` — PASS (6 tests).
- `PATH=/Users/nzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run build && PATH=/Users/nzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH node --test tests/rendered-html.test.mjs` — PASS (build and 9 rendered HTML tests).
- `PATH=/Users/nzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm test` — PASS (36 focused/unit tests, build, and 9 rendered HTML tests).
- `PATH=/Users/nzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH npm run lint` — PASS.

## Files changed

- `.generated/problem-index.json` (removed from tracking; local ignored file retained)
- `app/problems/[id]/page.tsx`
- `lib/problems/example-research.mjs`
- `tests/example-research.test.mjs`
- `.superpowers/sdd/2026-07-27-static-research-example/final-fix-report.md`

## Concerns

- The build emits an existing proxy-environment warning from the tooling; it does not affect the successful build or tests.
- The pre-existing untracked `.superpowers/brainstorm/` directory was deliberately not staged or changed.
