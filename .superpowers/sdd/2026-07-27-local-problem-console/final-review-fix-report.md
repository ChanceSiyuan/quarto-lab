# Final Review Fix Report: Local Problem Console

## Status

Complete. All Critical and Important review findings are addressed, and the Minor repository mutability finding is fixed. No dependencies or persistent `problems/` business records were added.

## Changes by Finding

### 1. Collision-safe next-ID allocation (Critical)

- The indexer now reserves every existing directory whose name matches `QMB-NNN` before attempting to read its manifest.
- It also reserves every parseable manifest ID matching `QMB-NNN` before schema validation, including invalid manifests and directory/manifest mismatches.
- `nextProblemId` is derived from the reserved set, while invalid records remain excluded from `problems` and continue to produce isolated diagnostics.
- A damaged `problems/QMB-001/problem.json` therefore produces `nextProblemId: QMB-002`, never `QMB-001`.

### 2. Safe and complete Codex creation contract (Important)

The generated prompt now explicitly requires:

- the issue #133 creation context for the next problem;
- the exact top-level manifest fields, lifecycle/readiness enums, conditional rejection fields, dates, and accepted-or-later Markdown contract;
- scanning both existing `QMB-NNN` directories and parseable manifest IDs before work;
- refusing any reserved candidate without writing or overwriting;
- rechecking the ID and destination immediately before writes;
- exclusive destination-directory creation that fails on collision;
- staging and validating all required problem files outside the final problem directory;
- copying non-manifest files first and atomically publishing `problem.json` last;
- final manifest validation and index build after publication.

### 3. Homepage behavior and navigation (Important)

- Empty desktop and mobile states now offer `+ Add first problem` through the existing Codex launch.
- No-results desktop and mobile states now offer `Clear all filters`.
- Clearing removes the query/status restrictions and reveals rejected and archived records, so the action always resolves a filter-created no-results state when records exist.
- Desktop table rows use one keyboard-focusable detail anchor with a row-spanning hit area; mobile items are whole-item anchors with explicit accessible labels.
- Search, lifecycle filtering, default rejected/archived hiding, clear behavior, and navigation targets live in a dependency-free pure view-state module used by the React component and Node tests.
- No lifecycle mutation, solver, validation, deletion, or status-advance controls were added.

### 4. Behavior-oriented and end-to-end coverage (Important)

- Added pure tests for search, selected statuses, default rejected/archived hiding, clear-all behavior, and stable detail hrefs.
- Reworked populated rendered tests to create temporary `problems/<id>/` files and generation audit files, invoke the real `scripts/build-problem-index.mjs` into `.generated/problem-index.json`, build the app, and render the result.
- The filesystem fixture includes one valid accepted problem plus a damaged reserved-ID directory, proving that valid data renders alongside diagnostics.
- Added rendered assertions for whole-row/mobile navigation, empty add-first action, no-results clear action, default-hidden rejected content, and diagnostic file/message visibility.
- Fixture cleanup restores the original generated index; no fake business records remain in the repository.

### 5. Repository immutability (Minor)

- The repository snapshots cloned problem records on construction.
- `listProblems()` and `getProblem()` return fresh deep clones, so nested caller mutations cannot affect repository state or the source index.

## TDD Evidence

### Cycle A: ID reservation and repository immutability

RED command:

```text
node --test tests/problem-indexer.test.mjs tests/problem-repository.test.mjs
```

RED result: exit 1; 6 passed, 3 failed. Expected failures were:

- damaged `QMB-001` directory returned `QMB-001` instead of `QMB-002`;
- invalid parseable manifest ID `QMB-007` returned `QMB-001` instead of `QMB-008`;
- mutating a listed record changed later repository results.

GREEN command: the same focused command.

GREEN result: exit 0; 9 passed, 0 failed.

### Cycle B: Codex creation safety contract

RED command:

```text
node --test tests/codex-launch.test.mjs
```

RED result: exit 1; 2 passed, 1 failed because the prompt omitted the five-problem target and downstream safety requirements.

GREEN command: the same focused command.

GREEN result: exit 0; 3 passed, 0 failed.

### Cycle C: Pure interactive view behavior

RED command:

```text
node --test tests/problem-view-state.test.mjs
```

RED result: exit 1 because `lib/problems/view-state.mjs` did not exist.

GREEN command:

```text
node --test tests/problem-view-state.test.mjs tests/problem-presentation.test.mjs
```

GREEN result: exit 0; 6 passed, 0 failed.

### Cycle D: Rendered actions, navigation, diagnostics, and real filesystem integration

RED command:

```text
npm run build && node --test tests/rendered-html.test.mjs
```

RED result: exit 1; 2 passed, 3 failed. The new assertions caught the missing empty-state action, whole-item links, and no-results clear action.

GREEN command: the same build-and-render command.

GREEN result: exit 0; 5 passed, 0 failed. The populated test built its index from temporary problem directories through the real indexer.

## Final Verification

All commands were run after the final implementation:

```text
npm run lint
```

Exit 0; ESLint reported no errors.

```text
npm test
```

Exit 0; 28 core Node tests passed, the production build completed, and 5 rendered/integration tests passed. Zero failures.

```text
npm run build
```

Exit 0; all Vinext build stages completed and routes `/` and `/problems/:id` were produced.

Focused GREEN evidence also includes:

- allocator/repository: 9 passed, 0 failed;
- Codex launch: 3 passed, 0 failed;
- view state/presentation: 6 passed, 0 failed;
- rendered filesystem integration: 5 passed, 0 failed.

## Files Changed

- `app/globals.css`
- `app/problem-console.tsx`
- `lib/problems/codex-launch.mjs`
- `lib/problems/indexer.mjs`
- `lib/problems/presentation.mjs`
- `lib/problems/repository.mjs`
- `lib/problems/view-state.mjs`
- `package.json`
- `tests/codex-launch.test.mjs`
- `tests/problem-indexer.test.mjs`
- `tests/problem-repository.test.mjs`
- `tests/problem-view-state.test.mjs`
- `tests/rendered-html.test.mjs`
- `.superpowers/sdd/2026-07-27-local-problem-console/final-review-fix-report.md`

## Self-Review

- Reservation happens before every validation `continue`, so malformed JSON is covered by its directory name and parseable invalid JSON records are covered by their manifest ID.
- Diagnostics are not used to derive allocation and are not suppressed or merged; damaged fixtures still produce one actionable diagnostic each.
- The prompt never authorizes overwrite and closes the check/write race with an exclusive directory-create instruction.
- The final manifest is explicitly staged, validated, and published last with atomic rename wording.
- Both desktop and mobile result structures have one primary keyboard-focusable link per problem and no nested anchors.
- Pure UI tests use literal expected problem IDs and real filter functions; the integration test uses real filesystem, indexer, build, and renderer boundaries.
- Repository clone tests mutate nested fields, not only outer properties.
- `git diff --check` passed before the report and will be rerun before commit.

### Fresh-context implementation review

- Critical findings: none.
- Git audit gate: PASS (`harm.secrets`, `harm.dangerous-files`, `harm.generated-artifacts`, `harm.cache`, and `harm.debug-leftovers` all OK; PR metadata not visible).
- The reviewer confirmed the reserved-ID, manifest-last, UI structure, navigation, and deep-clone implementations are correct.
- The reviewer requested a hydrated browser interaction test for handler and stretched-link CSS wiring. This repository has no DOM/browser test harness and the task forbids new dependencies; per the task's explicit fallback, the implementation instead uses pure filter/navigation helpers under Node tests plus real rendered markup assertions.

## Concerns and Principled Limitation

- No table skeleton was added. The homepage imports a build-time generated JSON index synchronously and has no asynchronous data fetch, Suspense transition, or reachable loading state. Adding a permanently hidden or unreachable skeleton would create untestable dead UI. A table-shaped loading boundary should be added when index loading becomes asynchronous, together with a test that can drive that boundary.
- There is no hydrated browser automation test. Realistic mutations confined to React event wiring or the desktop stretched-link CSS could evade the pure-helper and server-rendered checks. Adding Playwright/jsdom was outside scope and would violate the no-new-dependencies constraint; this should be revisited if the repository adopts a browser test harness.
- The pre-existing allocator has no explicit exhaustion behavior after `QMB-999` and would format `QMB-1000`, which the current three-digit schema rejects. This was not introduced by the malformed-ID fix and is outside the reviewed request.
- The build continues to print existing non-failing warnings about Node's deprecated `module.register()` API, detected proxy variables, and Vinext route classification. These warnings predate and are unrelated to this fix.
