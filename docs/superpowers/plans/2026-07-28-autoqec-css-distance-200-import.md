# AutoQEC CSS Distance 200 Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import `/Users/nzy/AutoQEC` CSS-distance autoresearch trials as the self-contained real `Prob-001` record with all 200 attempts, copied artifacts, six frozen infrastructure snapshots, offline verification, and navigable problem and attempt pages.

**Architecture:** Add a generic imported-research record contract beside the existing problem manifest contract, then index research records into `.generated/research-index.json` without embedding raw Markdown or source code. Add an explicit AutoQEC importer that reads Git objects from a source repo, copies only approved regular files into `problems/Prob-001`, freezes the six infrastructure snapshots, verifies the imported tree offline, and leaves the existing `Prob-000` Pages showcase isolated.

**Tech Stack:** Node.js 22+ ESM, Node test runner, React 19, vinext/Next.js 16 app routes, Git CLI read-only source inspection, SHA-256 file hashing through `node:crypto`.

## Global Constraints

- Implement only in the current `/Users/nzy/mcode/research-loop` checkout.
- Treat `/Users/nzy/AutoQEC` as read-only migration input.
- The real record is `Prob-001`.
- `problems/Prob-001` must contain actual copied files, not symlinks, hardlinks, submodules, or runtime links to AutoQEC.
- Preserve each existing trial `LOG.md`, `REPORT.md`, `candidate.py`, and `METHOD.txt` when the source trial contains that file.
- A failed proposal that never produced `candidate.py` remains a visible attempt and is labeled `Candidate code was not generated`.
- Use exactly two logical cohorts: `cohort-001-100` for `ATT-001` through `ATT-100`, and `cohort-101-200` for `ATT-101` through `ATT-200`.
- Freeze exactly six physical infrastructure snapshots with this mapping: `ATT-001` -> `c4533f982ece376c5f299a13edfabff0f489182c`; `ATT-002`-`ATT-100` -> `3e61f5ac8143e4848e5e814188c83683c74dfe4c`; `ATT-101`-`ATT-104` -> `12a8f794f68d63f07303df0cc38fa244c1ab1248`; `ATT-105`-`ATT-107` -> `87f0972ca2551074546c723cf48053d569b9bf59`; `ATT-108` -> `3f30f39a2f9be8ceead3821706aae77acdd980aa`; `ATT-109`-`ATT-200` -> `b6a0e03c05a653b4e85160a703c0be4eef06b619`.
- Private blind-evaluation material, selection secrets, salts, answer keys, case-level results, credentials, and Git metadata are not imported.
- `problems/Prob-001` is an experimental audit record, not trusted `knowledge/`; `make knowledge-resolve` remains unchanged.
- No Research Loop build, route, index, verification, preview, or test executes imported candidate code or frozen AutoQEC Python.
- The preserved dashboard files `app/page.tsx`, `app/globals.css`, and `app/layout.tsx` are not edited.
- The GitHub Pages showcase continues to publish only synthetic `Prob-000`; `Prob-001`, candidates, and infrastructure snapshots must not appear in `out/`.
- Import is all-or-nothing and refuses to overwrite an existing `problems/Prob-001`.
- `.generated/` remains ignored build output; commands regenerate `.generated/problem-index.json` and `.generated/research-index.json`, but commits do not include them.
- Use test-first commits; each task ends with focused verification and a task-specific commit.

---

## File Map

- `lib/problems/research-schema.mjs`: validate `research.json`, `attempt.json`, `infrastructure/cohorts/*.json`, `source-manifest.json`, and `import-manifest.json`.
- `lib/problems/research-indexer.mjs`: discover committed research records, validate integrity, and build `.generated/research-index.json`.
- `lib/problems/research-repository.mjs`: immutable lookup helpers for indexed research records and attempts.
- `lib/problems/research-presentation.mjs`: generic ledger and dossier display helpers shared by imported records and `Prob-000`.
- `lib/problems/research-route-data.mjs`: route-state helpers that make real research route branching testable without rendering server components against generated files.
- `lib/problems/example-presentation.mjs`: thin compatibility wrapper over `research-presentation.mjs` for the synthetic fixture.
- `scripts/build-problem-index.mjs`: write both `.generated/problem-index.json` and `.generated/research-index.json` for the selected problem root.
- `scripts/dev-problem-index.mjs`: watch top-level problem files plus `research.json`, `import-manifest.json`, cohort manifests, and attempt manifests.
- `lib/problems/autoqec-css-distance/reports.mjs`: parse the two AutoQEC CSS-distance report contracts.
- `lib/problems/autoqec-css-distance/git-source.mjs`: read trial refs, commits, first parents, tree entries, blobs, and executable modes without modifying AutoQEC.
- `lib/problems/autoqec-css-distance/infrastructure.mjs`: resolve the fixed six-snapshot mapping and compute the local Python import closure from frozen trees.
- `lib/problems/autoqec-css-distance/importer.mjs`: copy trial artifacts, generate normalized JSON, freeze infrastructure snapshots, and install `Prob-001` atomically.
- `scripts/import-autoqec-css-distance.mjs`: CLI for `import` and `verify` modes.
- `Makefile` and `package.json`: add import and offline verification surfaces.
- `app/problems/[id]/page.tsx`: render real research ledgers when a generated research record exists, preserving the synthetic example behavior.
- `app/problems/[id]/attempts/[attemptId]/page.tsx`: render real attempt dossiers when a generated research record exists.
- `tests/imported-research-schema.test.mjs`: contract tests for imported research records and manifests.
- `tests/research-indexer.test.mjs`: indexing and integrity-diagnostic tests.
- `tests/research-presentation.test.mjs`: ledger and dossier formatting tests for real imported records.
- `tests/autoqec-css-distance-report.test.mjs`: parser coverage for representative report formats.
- `tests/autoqec-css-distance-importer.test.mjs`: synthetic Git-source import coverage, safe-copy checks, infrastructure mapping, and atomic install behavior.
- `tests/autoqec-css-distance-verify.test.mjs`: offline verification coverage.
- `tests/dev-problem-index.test.mjs`: watcher coverage for research files.
- `tests/pages-showcase.test.mjs`: prove Pages output stays synthetic and excludes `Prob-001`.
- `problems/Prob-001/**`: generated by the importer in the final data task.

---

## PR #5 Hardening Follow-up

This follow-up fixes the review findings discovered after the initial import:
partial ledgers from missing attempts, offline verification that ignores
unmanifested files, broad infrastructure snapshots that mirror unrelated
source trees, and superpowers planning/spec documents that should not ship in
the PR diff.

### Task H1: Require Exact Attempt Directories Before Indexing

**Files:**
- Modify: `tests/research-indexer.test.mjs`
- Modify: `lib/problems/research-indexer.mjs`

**Interfaces:**
- Produces: `expectedAttemptIds(manifest)` returning `string[]`, for example `["ATT-001", ..., "ATT-200"]`.
- Produces: problem-level diagnostics with `relativePath` set to `problems/Prob-001/attempts` for missing, unexpected, or malformed attempt directories.
- Preserves: `buildResearchIndex({ rootDir, problemsDir })` return shape.

- [ ] **Step H1.1: Update fixtures to create the complete declared attempt set**

Replace the current one-attempt happy-path fixture with a helper that writes
all declared attempts:

```js
async function writeValidResearch(root, sequences = Array.from({ length: 200 }, (_, index) => index + 1)) {
  await writeFile(join(root, "problems", "Prob-001", "research.json"), JSON.stringify({
    schemaVersion: 1,
    kind: "imported-research-record",
    problemId: "Prob-001",
    attemptCount: 200,
    attemptIdRange: ["ATT-001", "ATT-200"],
    disclaimer: RESEARCH_DISCLAIMER,
    cohorts: [
      { id: "cohort-001-100", first: 1, last: 100 },
      { id: "cohort-101-200", first: 101, last: 200 },
    ],
  }, null, 2));
  for (const sequence of sequences) {
    const id = `ATT-${String(sequence).padStart(3, "0")}`;
    await mkdir(join(root, "problems", "Prob-001", "attempts", id), { recursive: true });
    await writeFile(join(root, "problems", "Prob-001", "attempts", id, "attempt.json"), JSON.stringify(attempt(sequence), null, 2));
  }
}
```

- [ ] **Step H1.2: Write the missing-attempt failing test**

Add this test:

```js
test("does not emit a partial ledger when declared attempts are missing", async () => {
  const root = await makeRoot();
  await writeValidResearch(root, [1]);

  const index = await buildResearchIndex({ rootDir: root });

  assert.deepEqual(index.records, []);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Missing declared attempt directory: ATT-002/);
});
```

- [ ] **Step H1.3: Write the unexpected-attempt failing test**

Add this test:

```js
test("rejects unexpected attempt directories before indexing", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);
  await mkdir(join(root, "problems", "Prob-001", "attempts", "ATT-201"), { recursive: true });
  await writeFile(join(root, "problems", "Prob-001", "attempts", "ATT-201", "attempt.json"), "{}\n");

  const index = await buildResearchIndex({ rootDir: root });

  assert.deepEqual(index.records, []);
  assert.match(index.diagnostics.map((item) => item.message).join("\n"), /Unexpected attempt directory: ATT-201/);
});
```

- [ ] **Step H1.4: Run the focused test and confirm RED**

Run: `node --test tests/research-indexer.test.mjs`

Expected: the two new tests fail because `buildResearchIndex()` currently
filters to discovered `ATT-\d{3}` directories and emits a one-attempt ledger.

- [ ] **Step H1.5: Implement exact attempt-set comparison**

Add helpers to `lib/problems/research-indexer.mjs`:

```js
function expectedAttemptIds(manifest) {
  const first = Number(manifest.attemptIdRange[0].slice("ATT-".length));
  return Array.from({ length: manifest.attemptCount }, (_, index) => `ATT-${String(first + index).padStart(3, "0")}`);
}

function compareAttemptDirectorySet(entries, expectedIds, attemptsRelativePath) {
  const expected = new Set(expectedIds);
  const actual = new Set();
  const errors = [];
  for (const entry of entries) {
    if (!entry.isDirectory()) continue;
    if (!ATTEMPT_ID_PATTERN.test(entry.name)) {
      errors.push(diagnostic(attemptsRelativePath, "attempts", `Malformed attempt directory: ${entry.name}`));
      continue;
    }
    actual.add(entry.name);
    if (!expected.has(entry.name)) {
      errors.push(diagnostic(attemptsRelativePath, "attempts", `Unexpected attempt directory: ${entry.name}`));
    }
  }
  for (const id of expectedIds) {
    if (!actual.has(id)) errors.push(diagnostic(attemptsRelativePath, "attempts", `Missing declared attempt directory: ${id}`));
  }
  return errors;
}
```

Use `expectedAttemptIds(manifestValidation.value)` to drive the read loop, and
push problem diagnostics before creating the record whenever the directory set
is not exact.

- [ ] **Step H1.6: Run focused and problem tests**

Run: `node --test tests/research-indexer.test.mjs`

Run: `npm run test:unit:problems`

Expected: both commands pass; corrupt attempts still suppress records rather
than returning a partial ledger.

- [ ] **Step H1.7: Commit exact attempt indexing**

```bash
git add tests/research-indexer.test.mjs lib/problems/research-indexer.mjs
git commit -m "fix: require complete imported attempt ledgers"
```

### Task H2: Make Offline Import Verification Exact

**Files:**
- Modify: `tests/autoqec-css-distance-verify.test.mjs`
- Modify: `lib/problems/autoqec-css-distance/importer.mjs`

**Interfaces:**
- Produces: `listVerifiedProblemFiles(problemPath, id)` returning sorted manifest-relative regular file paths excluding only `import-manifest.json`.
- Preserves: `verifyImportedProblemTree({ rootDir, id })`.

- [ ] **Step H2.1: Write the extra-file failing test**

Add this test:

```js
test("offline verification rejects files missing from import-manifest", async () => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-import-verify-"));
  const problem = join(root, "problems", "Prob-001");
  const log = "log\n";
  await mkdir(join(problem, "attempts", "ATT-001"), { recursive: true });
  await writeFile(join(problem, "attempts", "ATT-001", "LOG.md"), log);
  await writeFile(join(problem, "attempts", "ATT-001", "EXTRA.md"), "extra\n");
  await writeFile(join(problem, "import-manifest.json"), JSON.stringify({
    schemaVersion: 1,
    kind: "autoqec-css-distance-import",
    problemId: "Prob-001",
    sourceRepository: "AutoQEC",
    importedAt: "2026-07-28T00:00:00.000Z",
    attempts: 1,
    files: [{
      path: "attempts/ATT-001/LOG.md",
      sourcePath: "LOG.md",
      sha256: "9b75290f6a6359a2a3471022cbba4b724e45105b313ae8f6c103a2f79e82a857",
      size: 4,
      generated: false,
    }],
  }, null, 2));

  const result = await verifyImportedProblemTree({ rootDir: root });

  assert.equal(result.ok, false);
  assert.match(result.errors.map((item) => item.message).join("\n"), /Unexpected file not listed in import-manifest: attempts\/ATT-001\/EXTRA.md/);
});
```

- [ ] **Step H2.2: Write the symlink failing test**

Add `symlink` to the `node:fs/promises` import and add this test:

```js
test("offline verification rejects symlinks inside the imported problem tree", async () => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-import-verify-"));
  const problem = join(root, "problems", "Prob-001");
  await mkdir(join(problem, "attempts", "ATT-001"), { recursive: true });
  await writeFile(join(problem, "attempts", "ATT-001", "LOG.md"), "log\n");
  await symlink("LOG.md", join(problem, "attempts", "ATT-001", "alias.md"));
  await writeFile(join(problem, "import-manifest.json"), JSON.stringify({
    schemaVersion: 1,
    kind: "autoqec-css-distance-import",
    problemId: "Prob-001",
    sourceRepository: "AutoQEC",
    importedAt: "2026-07-28T00:00:00.000Z",
    attempts: 1,
    files: [],
  }, null, 2));

  const result = await verifyImportedProblemTree({ rootDir: root });

  assert.equal(result.ok, false);
  assert.match(result.errors.map((item) => item.message).join("\n"), /Non-regular file in imported problem tree: attempts\/ATT-001\/alias.md/);
});
```

- [ ] **Step H2.3: Run the focused test and confirm RED**

Run: `node --test tests/autoqec-css-distance-verify.test.mjs`

Expected: the extra-file test fails because verification only checks manifest
entries; the symlink test fails because the directory tree is not enumerated.

- [ ] **Step H2.4: Implement exact tree comparison**

In `lib/problems/autoqec-css-distance/importer.mjs`, import `lstat` and add:

```js
async function listVerifiedProblemFiles(problemPath, id, directory = problemPath) {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const absolutePath = join(directory, entry.name);
    const relativePath = absolutePath.slice(problemPath.length + 1);
    if (relativePath === "import-manifest.json") continue;
    const metadata = await lstat(absolutePath);
    if (metadata.isDirectory()) {
      files.push(...await listVerifiedProblemFiles(problemPath, id, absolutePath));
    } else if (metadata.isFile()) {
      assertSafeImportPath(relativePath);
      files.push(relativePath);
    } else {
      throw new Error(`Non-regular file in imported problem tree: ${relativePath}`);
    }
  }
  return files.sort((left, right) => left.localeCompare(right));
}
```

After validating `manifest.files`, compare `new Set(manifest.files.map((entry) => entry.path))`
with the `listVerifiedProblemFiles()` result. Add diagnostics for duplicate
manifest paths, missing listed files, and unexpected on-disk files before hash
checks complete.

- [ ] **Step H2.5: Run focused and importer tests**

Run: `node --test tests/autoqec-css-distance-verify.test.mjs`

Run: `node --test tests/autoqec-css-distance-importer.test.mjs`

Expected: both commands pass; existing hash mismatch behavior is unchanged.

- [ ] **Step H2.6: Commit exact offline verification**

```bash
git add tests/autoqec-css-distance-verify.test.mjs lib/problems/autoqec-css-distance/importer.mjs
git commit -m "fix: verify exact imported problem file sets"
```

### Task H3: Freeze CSS-Distance Infrastructure as a Closed File Set

**Files:**
- Modify: `tests/autoqec-css-distance-importer.test.mjs`
- Modify: `lib/problems/autoqec-css-distance/infrastructure.mjs`
- Modify: `lib/problems/autoqec-css-distance/importer.mjs`

**Interfaces:**
- Produces: `selectCssDistanceInfrastructurePaths({ paths, readText })` returning `{ paths: string[], entryPoints: string[] }`.
- Consumes: `readText(path)` async function that reads a UTF-8 Git blob for one selected Python source path.
- Preserves: `buildInfrastructurePlan(trials, options)` and `buildCohortManifests(ranges)`.

- [ ] **Step H3.1: Update synthetic source fixtures to include CSS-distance entry points**

In `createSyntheticSource()`, replace `src/infrastructure.py` with these files
for every synthetic infrastructure commit:

```js
await mkdir(join(sourceDir, "src", "autoqec_search"), { recursive: true });
await writeFile(join(sourceDir, "src", "autoqec_search", "__init__.py"), "");
await writeFile(join(sourceDir, "src", "autoqec_search", "css_distance_autoresearch.py"), [
  "from autoqec_search.css_distance_container import DockerImage",
  "from autoqec_search.css_distance_eval import DEFAULT_TIMEOUT_SECONDS",
  "",
  `EPOCH = ${sequence}`,
  "",
].join("\n"));
await writeFile(join(sourceDir, "src", "autoqec_search", "css_distance_container.py"), "class DockerImage:\n    pass\n");
await writeFile(join(sourceDir, "src", "autoqec_search", "css_distance_eval.py"), "DEFAULT_TIMEOUT_SECONDS = 300\n");
await writeFile(join(sourceDir, "src", "autoqec_search", "quantum_tanner_catalog.py"), "UNRELATED = True\n");
await mkdir(join(sourceDir, "containers", "css-distance-autoresearch"), { recursive: true });
await writeFile(join(sourceDir, "containers", "css-distance-autoresearch", "candidate-entrypoint.py"), "print('entry')\n");
await writeFile(join(sourceDir, "containers", "css-distance-autoresearch", "evaluator.Dockerfile"), "FROM python:3.11\n");
await writeFile(join(sourceDir, "containers", "css-distance-autoresearch", "proposal.Dockerfile"), "FROM python:3.11\n");
await writeFile(join(sourceDir, "containers", "css-distance-autoresearch", "requirements.txt"), "numpy\n");
await writeFile(join(sourceDir, "pyproject.toml"), "[project]\nname = \"synthetic-autoqec\"\n");
```

Update the corresponding `git add` call to stage `src`, `containers`, and
`pyproject.toml`.

- [ ] **Step H3.2: Write the focused snapshot-closure failing assertion**

Extend `imports synthetic trials atomically with copied artifacts and snapshots`:

```js
const firstSnapshotSource = join(root, "problems", "Prob-001", "infrastructure", "snapshots", firstParents[0], "source");
assert.equal(await fileExists(join(firstSnapshotSource, "src", "autoqec_search", "css_distance_autoresearch.py")), true);
assert.equal(await fileExists(join(firstSnapshotSource, "src", "autoqec_search", "css_distance_container.py")), true);
assert.equal(await fileExists(join(firstSnapshotSource, "src", "autoqec_search", "quantum_tanner_catalog.py")), false);
assert.equal(await fileExists(join(firstSnapshotSource, "zoo", "external", "eczoo", "views", "site", "index.html")), false);
const snapshotManifest = JSON.parse(await readFile(join(root, "problems", "Prob-001", "infrastructure", "snapshots", firstParents[0], "source-manifest.json"), "utf8"));
assert.deepEqual(snapshotManifest.entryPoints, [
  "containers/css-distance-autoresearch/candidate-entrypoint.py",
  "src/autoqec_search/css_distance_autoresearch.py",
]);
```

- [ ] **Step H3.3: Run the focused test and confirm RED**

Run: `node --test tests/autoqec-css-distance-importer.test.mjs`

Expected: it fails because `freezeSnapshots()` currently copies every
non-dot/non-private tree entry and reports all Python files as entry points.

- [ ] **Step H3.4: Implement recursive local Python import closure**

In `lib/problems/autoqec-css-distance/infrastructure.mjs`, add approved roots:

```js
export const CSS_DISTANCE_INFRASTRUCTURE_ENTRY_POINTS = [
  "containers/css-distance-autoresearch/candidate-entrypoint.py",
  "src/autoqec_search/css_distance_autoresearch.py",
  "src/autoqec_search/css_distance_autoresearch_batch.py",
];

export const CSS_DISTANCE_INFRASTRUCTURE_ALLOWLIST = [
  "campaigns/examples/css-distance-autoresearch/README.md",
  "campaigns/examples/css-distance-autoresearch/proposal-prompt.txt",
  "campaigns/examples/css-distance-autoresearch/research-brief.md",
  "campaigns/examples/css-distance-autoresearch/results.md",
  "campaigns/examples/css-distance-autoresearch/source.json",
  "containers/css-distance-autoresearch/evaluator.Dockerfile",
  "containers/css-distance-autoresearch/proposal.Dockerfile",
  "containers/css-distance-autoresearch/requirements.txt",
  "pyproject.toml",
  "results/css-distance-autoresearch-100/development-baseline-aggregate.json",
  "zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/hx.json",
  "zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/hz.json",
  "zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/instance.json",
];
```

Implement `selectCssDistanceInfrastructurePaths({ paths, readText })` so it:
starts from existing approved Python entry points, adds existing allowlisted
files, reads each selected local Python file, resolves `autoqec_search.*` and
same-package relative imports to `src/autoqec_search/*.py` or
`src/autoqec_search/*/__init__.py`, adds package `__init__.py` files when
present, recurses until stable, and throws `Unresolved local Python import`
when a local import cannot be mapped to an existing path.

- [ ] **Step H3.5: Wire the selector into snapshot freezing**

In `freezeSnapshots()`, read the complete Git tree into entries, call
`selectCssDistanceInfrastructurePaths({ paths: [...entries.keys()], readText })`,
copy only selected paths, and set `source-manifest.json.entryPoints` to the
selector's returned `entryPoints` instead of every `.py` file.

- [ ] **Step H3.6: Run focused and problem tests**

Run: `node --test tests/autoqec-css-distance-importer.test.mjs`

Run: `npm run test:unit:problems`

Expected: both commands pass and synthetic unrelated files stay out of
snapshots.

- [ ] **Step H3.7: Commit closed snapshot selection**

```bash
git add tests/autoqec-css-distance-importer.test.mjs lib/problems/autoqec-css-distance/infrastructure.mjs lib/problems/autoqec-css-distance/importer.mjs
git commit -m "fix: freeze focused AutoQEC infrastructure snapshots"
```

### Task H4: Regenerate Prob-001 From the Corrected Importer

**Files:**
- Modify: `problems/Prob-001/**`

**Interfaces:**
- Consumes: `make problem-import-autoqec-css-distance SOURCE=/Users/nzy/AutoQEC`.
- Consumes: `make problem-import-verify ID=Prob-001`.
- Produces: a committed `problems/Prob-001` tree whose snapshots contain no
  `articles/`, `zoo/external/`, generated `views/site/`, or unrelated
  `docs/superpowers/` content.

- [ ] **Step H4.1: Confirm the tracked destination has no uncommitted user edits**

Run: `git status --short -- problems/Prob-001`

Expected: no uncommitted changes under `problems/Prob-001` before replacing the
generated data tree.

- [ ] **Step H4.2: Generate a corrected tree in temporary space**

Run: `make problem-import-autoqec-css-distance SOURCE=/Users/nzy/AutoQEC ROOT=/private/tmp/research-loop-autoqec-corrected`

If the Make target does not expose `ROOT`, run the importer CLI against a
temporary root with the existing script interface and the same `SOURCE`
argument.

- [ ] **Step H4.3: Verify the temporary tree**

Run: `make problem-import-verify ID=Prob-001 ROOT=/private/tmp/research-loop-autoqec-corrected`

If the Make target does not expose `ROOT`, run `node scripts/import-autoqec-css-distance.mjs verify --id Prob-001 --root /private/tmp/research-loop-autoqec-corrected`.

Expected: verification passes with the exact manifest/file-set check from Task
H2.

- [ ] **Step H4.4: Replace only the generated Prob-001 tree**

Move the current generated tree to `/private/tmp/research-loop-Prob-001-backup-<timestamp>`
and move the verified temporary `Prob-001` into `/Users/nzy/mcode/research-loop/problems/Prob-001`.
Do not remove or stage `.gitignore`.

- [ ] **Step H4.5: Check the broad snapshot paths are gone**

Run: `rg --files problems/Prob-001/infrastructure/snapshots | rg 'articles|zoo/external|views/site|docs/superpowers'`

Expected: no matching output.

- [ ] **Step H4.6: Verify regenerated data and tests**

Run: `make problem-import-verify ID=Prob-001`

Run: `npm run test:unit:problems`

Expected: both commands pass.

- [ ] **Step H4.7: Commit regenerated data**

```bash
git add problems/Prob-001
git commit -m "data: regenerate focused AutoQEC import"
```

### Task H5: Remove Planning Artifacts From the PR Diff

**Files:**
- Delete: `docs/superpowers/plans/2026-07-28-add-problem-skill.md`
- Delete: `docs/superpowers/plans/2026-07-28-autoqec-css-distance-200-import.md`
- Delete: `docs/superpowers/plans/2026-07-28-autoresearch-campaigns.md`
- Delete: `docs/superpowers/plans/2026-07-28-autoresearch-preparation.md`
- Delete: `docs/superpowers/plans/2026-07-28-local-assessment-reports.md`
- Delete: `docs/superpowers/specs/2026-07-28-add-problem-skill-design.md`
- Delete: `docs/superpowers/specs/2026-07-28-autoqec-css-distance-200-import-design.md`
- Delete: `docs/superpowers/specs/2026-07-28-autoresearch-button-design.md`
- Delete: `docs/superpowers/specs/2026-07-28-local-assessment-reports-design.md`

**Interfaces:**
- Consumes: the exact newly added superpowers docs from `git diff --name-only d428044 -- docs/superpowers/specs docs/superpowers/plans`.
- Produces: no `A docs/superpowers/...` entries in the PR diff against `d428044`.

- [ ] **Step H5.1: Confirm the exact planning/spec files added by this PR**

Run: `git diff --name-only d428044 -- docs/superpowers/specs docs/superpowers/plans`

Expected: the nine files listed above.

- [ ] **Step H5.2: Delete only those added files**

Run: `git rm` with exactly the nine paths listed in this task.

- [ ] **Step H5.3: Verify no superpowers docs remain in the PR diff**

Run: `git diff --name-only d428044 -- docs/superpowers/specs docs/superpowers/plans`

Expected: no output.

- [ ] **Step H5.4: Run final local verification**

Run: `git diff --check`

Run: `make problem-import-verify ID=Prob-001`

Run: `npm run test:unit:problems`

Run: `make test`

Expected: `git diff --check`, `make problem-import-verify`, and
`npm run test:unit:problems` pass. If `make test` fails because Quarto or another
documented external binary is missing, capture the exact command output and
report it as an environment gap, not a code pass.

- [ ] **Step H5.5: Commit PR hygiene cleanup**

```bash
git add docs/superpowers/plans docs/superpowers/specs
git commit -m "chore: keep planning artifacts out of PR"
```

---

### Task 1: Add Imported Research Schemas

**Files:**
- Create: `tests/imported-research-schema.test.mjs`
- Create: `lib/problems/research-schema.mjs`

**Interfaces:**
- Produces: `validateResearchManifest(manifest, context = {})`, `validateResearchAttempt(attempt, context = {})`, `validateCohortManifest(manifest, context = {})`, `validateSourceManifest(manifest, context = {})`, `validateImportManifest(manifest, context = {})`.
- Produces constants: `ATTEMPT_ID_PATTERN`, `RESEARCH_DISCLAIMER`, `AUTOQEC_INFRASTRUCTURE_RANGES`, `TIMING_STATUSES`, `GATE_VALUES`, `CANDIDATE_STATUSES`.

- [ ] **Step 1: Write the failing schema tests**

Create `tests/imported-research-schema.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";

import {
  AUTOQEC_INFRASTRUCTURE_RANGES,
  RESEARCH_DISCLAIMER,
  validateCohortManifest,
  validateImportManifest,
  validateResearchAttempt,
  validateResearchManifest,
  validateSourceManifest,
} from "../lib/problems/research-schema.mjs";

const baseAttempt = {
  schemaVersion: 1,
  problemId: "Prob-001",
  id: "ATT-200",
  sequence: 200,
  cohort: "cohort-101-200",
  title: "CSS Distance Proposal 200",
  summary: "Imported AutoQEC trial record.",
  stage: "development",
  decision: "rejected",
  gate: {
    containment: "passed",
    publicContract: "passed",
    development: "failed",
  },
  method: {
    description: "Randomized CSS kernel-combination search.",
    learnedFrom: null,
  },
  metrics: {
    runs: 24,
    verifiedWitnesses: 13,
    targetHits: 13,
    timeouts: 0,
    crashes: 0,
    invalidClaims: 11,
    weightedTargetHits: 13,
    normalizedQuality: 0.541666666666667,
    runtimeSeconds: 85.7838381199399,
    averageSeconds: 3.574326588330829,
    medianSeconds: 2.232983041496482,
    p95Seconds: 9.437287125037983,
    timingStatus: "recorded",
    speedup: null,
  },
  provenance: {
    sourceRepository: "AutoQEC",
    sourceBranch: "autoresearch/css-distance/run200-proposal-200",
    sourceCommit: "705563faed99c094534394e5ca8774f3d74863aa",
    sourceInfrastructureCommit: "b6a0e03c05a653b4e85160a703c0be4eef06b619",
    sourceCohort: "cohort-101-200",
    model: null,
  },
  candidate: {
    status: "present",
    path: "candidate.py",
  },
  artifacts: [
    {
      path: "LOG.md",
      sha256: "e28b7dffb8945e10907df9c136e95a5c57ee6a75fb9cb2237316bc6fcbb41a91",
      sourcePath: "LOG.md",
    },
    {
      path: "REPORT.md",
      sha256: "48fc9413bfa907579039c51a1a6c8f3b24e92b570f6ddb724b961ecde6104dfe",
      sourcePath: "REPORT.md",
    },
    {
      path: "candidate.py",
      sha256: "2fb483016f9e8894da309d3079e35c598d412c0c377a84454efae5bfe5322bac",
      sourcePath: "proposal-workspace/candidate.py",
    },
  ],
};

test("validates the imported research manifest contract", () => {
  const result = validateResearchManifest({
    schemaVersion: 1,
    kind: "imported-research-record",
    problemId: "Prob-001",
    attemptCount: 200,
    attemptIdRange: ["ATT-001", "ATT-200"],
    disclaimer: RESEARCH_DISCLAIMER,
    cohorts: [
      { id: "cohort-001-100", first: 1, last: 100 },
      { id: "cohort-101-200", first: 101, last: 200 },
    ],
  }, { relativePath: "problems/Prob-001/research.json" });

  assert.equal(result.ok, true);
});

test("rejects malformed research manifests before indexing", () => {
  const result = validateResearchManifest({
    schemaVersion: 1,
    kind: "imported-research-record",
    problemId: "Prob-001",
    attemptCount: 199,
    attemptIdRange: ["ATT-001", "ATT-200"],
    disclaimer: "reviewed knowledge",
    cohorts: [],
  });

  assert.equal(result.ok, false);
  assert.match(result.errors.map((error) => error.field).join("\n"), /attemptCount/);
  assert.match(result.errors.map((error) => error.field).join("\n"), /disclaimer/);
  assert.match(result.errors.map((error) => error.field).join("\n"), /cohorts/);
});

test("validates real attempt metadata including present and missing candidates", () => {
  assert.equal(validateResearchAttempt(baseAttempt).ok, true);

  const missingCandidate = structuredClone(baseAttempt);
  missingCandidate.id = "ATT-101";
  missingCandidate.sequence = 101;
  missingCandidate.gate.publicContract = "failed";
  missingCandidate.gate.development = "failed";
  missingCandidate.metrics = {
    runs: 0,
    verifiedWitnesses: 0,
    targetHits: 0,
    timeouts: 0,
    crashes: 0,
    invalidClaims: 1,
    weightedTargetHits: 0,
    normalizedQuality: 0,
    runtimeSeconds: null,
    averageSeconds: null,
    medianSeconds: null,
    p95Seconds: null,
    timingStatus: "not-run",
    speedup: null,
  };
  missingCandidate.candidate = { status: "not-generated" };
  missingCandidate.artifacts = missingCandidate.artifacts.filter((artifact) => artifact.path !== "candidate.py");

  assert.equal(validateResearchAttempt(missingCandidate).ok, true);
});

test("rejects unsafe attempt artifacts and unexplained missing candidates", () => {
  const unsafe = structuredClone(baseAttempt);
  unsafe.artifacts[0].path = "../LOG.md";
  assert.equal(validateResearchAttempt(unsafe).ok, false);

  const unexplained = structuredClone(baseAttempt);
  unexplained.candidate = { status: "not-generated" };
  unexplained.artifacts = unexplained.artifacts.filter((artifact) => artifact.path !== "candidate.py");
  assert.equal(validateResearchAttempt(unexplained).ok, false);
});

test("locks the exact AutoQEC infrastructure range map", () => {
  assert.deepEqual(AUTOQEC_INFRASTRUCTURE_RANGES, [
    { first: 1, last: 1, cohort: "cohort-001-100", commit: "c4533f982ece376c5f299a13edfabff0f489182c" },
    { first: 2, last: 100, cohort: "cohort-001-100", commit: "3e61f5ac8143e4848e5e814188c83683c74dfe4c" },
    { first: 101, last: 104, cohort: "cohort-101-200", commit: "12a8f794f68d63f07303df0cc38fa244c1ab1248" },
    { first: 105, last: 107, cohort: "cohort-101-200", commit: "87f0972ca2551074546c723cf48053d569b9bf59" },
    { first: 108, last: 108, cohort: "cohort-101-200", commit: "3f30f39a2f9be8ceead3821706aae77acdd980aa" },
    { first: 109, last: 200, cohort: "cohort-101-200", commit: "b6a0e03c05a653b4e85160a703c0be4eef06b619" },
  ]);
});

test("validates cohort, snapshot, and import manifests", () => {
  const cohort = validateCohortManifest({
    schemaVersion: 1,
    kind: "autoqec-css-distance-cohort",
    id: "cohort-101-200",
    problemId: "Prob-001",
    attempts: [
      { first: 101, last: 104, sourceInfrastructureCommit: "12a8f794f68d63f07303df0cc38fa244c1ab1248" },
      { first: 105, last: 107, sourceInfrastructureCommit: "87f0972ca2551074546c723cf48053d569b9bf59" },
      { first: 108, last: 108, sourceInfrastructureCommit: "3f30f39a2f9be8ceead3821706aae77acdd980aa" },
      { first: 109, last: 200, sourceInfrastructureCommit: "b6a0e03c05a653b4e85160a703c0be4eef06b619" },
    ],
  });
  assert.equal(cohort.ok, true);

  const snapshot = validateSourceManifest({
    schemaVersion: 1,
    kind: "autoqec-css-distance-source-snapshot",
    problemId: "Prob-001",
    sourceRepository: "AutoQEC",
    sourceCommit: "b6a0e03c05a653b4e85160a703c0be4eef06b619",
    attemptRanges: [{ first: 109, last: 200 }],
    entryPoints: [
      "src/autoqec_search/css_distance_autoresearch_batch.py",
      "containers/css-distance-autoresearch/candidate-entrypoint.py",
    ],
    excludedPathClasses: ["blind-evaluation-private", "credentials", "git-metadata"],
    files: [
      {
        path: "src/autoqec_search/css_distance_autoresearch_batch.py",
        sha256: "f".repeat(64),
        size: 1234,
        executable: false,
      },
    ],
    blindDatasetReproducible: false,
  });
  assert.equal(snapshot.ok, true);

  const importManifest = validateImportManifest({
    schemaVersion: 1,
    kind: "autoqec-css-distance-import",
    problemId: "Prob-001",
    sourceRepository: "AutoQEC",
    importedAt: "2026-07-28T00:00:00.000Z",
    attempts: 200,
    files: [
      {
        path: "attempts/ATT-200/REPORT.md",
        sourcePath: "REPORT.md",
        sha256: "a".repeat(64),
        size: 222,
        generated: false,
      },
      {
        path: "attempts/ATT-200/attempt.json",
        sourcePath: null,
        sha256: "b".repeat(64),
        size: 333,
        generated: true,
      },
    ],
  });
  assert.equal(importManifest.ok, true);
});
```

- [ ] **Step 2: Run the schema tests and verify RED**

Run:

```bash
node --test tests/imported-research-schema.test.mjs
```

Expected: FAIL with `Cannot find module '../lib/problems/research-schema.mjs'`.

- [ ] **Step 3: Implement the validators**

Create `lib/problems/research-schema.mjs` with these exported names and constraints:

```js
export const RESEARCH_DISCLAIMER = "Imported experimental record - not reviewed knowledge.";
export const ATTEMPT_ID_PATTERN = /^ATT-(\d{3})$/;
export const TIMING_STATUSES = ["recorded", "legacy-not-recorded", "not-run"];
export const GATE_VALUES = ["passed", "failed", "not-recorded"];
export const CANDIDATE_STATUSES = ["present", "not-generated"];
export const AUTOQEC_INFRASTRUCTURE_RANGES = [
  { first: 1, last: 1, cohort: "cohort-001-100", commit: "c4533f982ece376c5f299a13edfabff0f489182c" },
  { first: 2, last: 100, cohort: "cohort-001-100", commit: "3e61f5ac8143e4848e5e814188c83683c74dfe4c" },
  { first: 101, last: 104, cohort: "cohort-101-200", commit: "12a8f794f68d63f07303df0cc38fa244c1ab1248" },
  { first: 105, last: 107, cohort: "cohort-101-200", commit: "87f0972ca2551074546c723cf48053d569b9bf59" },
  { first: 108, last: 108, cohort: "cohort-101-200", commit: "3f30f39a2f9be8ceead3821706aae77acdd980aa" },
  { first: 109, last: 200, cohort: "cohort-101-200", commit: "b6a0e03c05a653b4e85160a703c0be4eef06b619" },
];
```

Use shared helpers inside the file:

```js
const SHA256_PATTERN = /^[a-f0-9]{64}$/;
const COMMIT_PATTERN = /^[a-f0-9]{40}$/;
const SAFE_RELATIVE_PATH_PATTERN = /^(?!\/)(?!\.)(?!.*(?:^|\/)\.\.(?:\/|$))(?!.*\/\/)[A-Za-z0-9][A-Za-z0-9._/@+-]*(?:\/[A-Za-z0-9][A-Za-z0-9._@+-]*)*$/;

function diagnostic(relativePath, field, message) {
  return { relativePath, field, message };
}

function finish(value, errors) {
  return errors.length === 0 ? { ok: true, value } : { ok: false, errors };
}
```

Each validator must reject unknown top-level fields, bad IDs, unsafe relative paths, bad hashes, bad timestamps, non-contiguous cohort ranges, and mismatches with `AUTOQEC_INFRASTRUCTURE_RANGES`. `validateResearchAttempt()` must enforce:

```js
attempt.id === `ATT-${String(attempt.sequence).padStart(3, "0")}`
attempt.problemId === "Prob-001"
attempt.cohort === expectedRange.cohort
attempt.provenance.sourceInfrastructureCommit === expectedRange.commit
attempt.metrics.timingStatus === "recorded" ? all timing fields are finite positive numbers except speedup may be null : true
attempt.metrics.timingStatus === "legacy-not-recorded" ? averageSeconds, medianSeconds, p95Seconds, and speedup are null : true
attempt.metrics.timingStatus === "not-run" ? runs is 0 and timing fields are null : true
attempt.candidate.status === "present" ? attempt.candidate.path === "candidate.py" and artifacts contains candidate.py : true
attempt.candidate.status === "not-generated" ? publicContract is "failed" or runs is 0 : true
```

- [ ] **Step 4: Run schema tests and verify GREEN**

Run:

```bash
node --test tests/imported-research-schema.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit schema contracts**

```bash
git add tests/imported-research-schema.test.mjs lib/problems/research-schema.mjs
git commit -m "feat: validate imported research records"
```

---

### Task 2: Build Research Index and Repository Lookups

**Files:**
- Create: `tests/research-indexer.test.mjs`
- Create: `lib/problems/research-indexer.mjs`
- Create: `lib/problems/research-repository.mjs`
- Modify: `scripts/build-problem-index.mjs`
- Modify: `package.json`

**Interfaces:**
- Consumes: Task 1 validators.
- Produces: `buildResearchIndex({ rootDir?: string, problemsDir?: string } = {})`.
- Produces: `createResearchRepository(index)` with `getResearchRecord(problemId)`, `getAttempt(problemId, attemptId)`, and `getDiagnostics(problemId?)`.
- Produces: `.generated/research-index.json` next to `.generated/problem-index.json`.

- [ ] **Step 1: Write failing research index tests**

Create `tests/research-indexer.test.mjs` with temporary fixture writers for one valid imported problem:

```js
import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { buildResearchIndex } from "../lib/problems/research-indexer.mjs";
import { createResearchRepository } from "../lib/problems/research-repository.mjs";
import { RESEARCH_DISCLAIMER } from "../lib/problems/research-schema.mjs";

async function makeRoot() {
  const root = await mkdtemp(join(tmpdir(), "research-loop-research-index-"));
  await mkdir(join(root, "problems", "Prob-001", "attempts", "ATT-001"), { recursive: true });
  await mkdir(join(root, "problems", "Prob-001", "infrastructure", "cohorts"), { recursive: true });
  await mkdir(join(root, "problems", "Prob-001", "infrastructure", "snapshots", "c4533f982ece376c5f299a13edfabff0f489182c"), { recursive: true });
  return root;
}

function attempt(sequence = 1) {
  return {
    schemaVersion: 1,
    problemId: "Prob-001",
    id: `ATT-${String(sequence).padStart(3, "0")}`,
    sequence,
    cohort: "cohort-001-100",
    title: `CSS Distance Proposal ${String(sequence).padStart(3, "0")}`,
    summary: "Imported AutoQEC trial record.",
    stage: "development",
    decision: "rejected",
    gate: { containment: "passed", publicContract: "passed", development: "failed" },
    method: { description: "randomized kernel sampling", learnedFrom: null },
    metrics: {
      runs: 24,
      verifiedWitnesses: 12,
      targetHits: 12,
      timeouts: 0,
      crashes: 0,
      invalidClaims: 12,
      weightedTargetHits: 12,
      normalizedQuality: 0.5,
      runtimeSeconds: 4.705462539917789,
      averageSeconds: null,
      medianSeconds: null,
      p95Seconds: null,
      timingStatus: "legacy-not-recorded",
      speedup: null,
    },
    provenance: {
      sourceRepository: "AutoQEC",
      sourceBranch: "autoresearch/css-distance/run100-proposal-001",
      sourceCommit: "f".repeat(40),
      sourceInfrastructureCommit: "c4533f982ece376c5f299a13edfabff0f489182c",
      sourceCohort: "cohort-001-100",
      model: null,
    },
    candidate: { status: "present", path: "candidate.py" },
    artifacts: [
      { path: "LOG.md", sha256: "a".repeat(64), sourcePath: "LOG.md" },
      { path: "REPORT.md", sha256: "b".repeat(64), sourcePath: "REPORT.md" },
      { path: "candidate.py", sha256: "c".repeat(64), sourcePath: "proposal-workspace/candidate.py" },
    ],
  };
}

async function writeValidResearch(root) {
  await writeFile(join(root, "problems", "Prob-001", "research.json"), JSON.stringify({
    schemaVersion: 1,
    kind: "imported-research-record",
    problemId: "Prob-001",
    attemptCount: 1,
    attemptIdRange: ["ATT-001", "ATT-001"],
    disclaimer: RESEARCH_DISCLAIMER,
    cohorts: [{ id: "cohort-001-100", first: 1, last: 1 }],
  }, null, 2));
  await writeFile(join(root, "problems", "Prob-001", "attempts", "ATT-001", "attempt.json"), JSON.stringify(attempt(), null, 2));
}

test("builds a deterministic research index from committed attempts", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);

  const index = await buildResearchIndex({ rootDir: root });

  assert.equal(index.schemaVersion, 1);
  assert.deepEqual(index.records.map((record) => record.problemId), ["Prob-001"]);
  assert.deepEqual(index.records[0].attempts.map((item) => item.id), ["ATT-001"]);
  assert.deepEqual(index.diagnostics, []);
});

test("surfaces corrupt attempts as diagnostics without returning a partial ledger", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);
  const broken = attempt();
  broken.sequence = 2;
  await writeFile(join(root, "problems", "Prob-001", "attempts", "ATT-001", "attempt.json"), JSON.stringify(broken, null, 2));

  const index = await buildResearchIndex({ rootDir: root });

  assert.deepEqual(index.records, []);
  assert.equal(index.diagnostics.length, 1);
  assert.match(index.diagnostics[0].relativePath, /attempts\/ATT-001\/attempt\.json/);
});

test("repository returns immutable research records and attempts", async () => {
  const root = await makeRoot();
  await writeValidResearch(root);
  const repository = createResearchRepository(await buildResearchIndex({ rootDir: root }));

  const record = repository.getResearchRecord("Prob-001");
  const attemptRecord = repository.getAttempt("Prob-001", "ATT-001");
  record.attempts[0].title = "mutated";
  attemptRecord.title = "mutated";

  assert.equal(repository.getResearchRecord("Prob-001").attempts[0].title, "CSS Distance Proposal 001");
  assert.equal(repository.getAttempt("Prob-001", "ATT-001").title, "CSS Distance Proposal 001");
  assert.equal(repository.getAttempt("Prob-001", "ATT-999"), null);
});
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
node --test tests/research-indexer.test.mjs
```

Expected: FAIL because the research indexer and repository do not exist.

- [ ] **Step 3: Implement `buildResearchIndex()`**

Create `lib/problems/research-indexer.mjs`. It must:

```js
import { readFile, readdir } from "node:fs/promises";
import { join, relative, resolve } from "node:path";
import {
  ATTEMPT_ID_PATTERN,
  validateResearchAttempt,
  validateResearchManifest,
} from "./research-schema.mjs";
```

Return:

```js
{
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  workspacePath,
  records,
  diagnostics,
}
```

For each `Prob-###` directory containing `research.json`, read `research.json`, then read every `attempts/ATT-###/attempt.json` directory in lexical order. Validate every item. If any item for a problem fails, push diagnostics and do not include that problem in `records`. A valid record shape is:

```js
{
  problemId: manifest.problemId,
  manifest,
  attempts,
  attemptCount: attempts.length,
}
```

- [ ] **Step 4: Implement immutable repository helpers**

Create `lib/problems/research-repository.mjs`:

```js
function clone(value) {
  return structuredClone(value);
}

export function createResearchRepository(index) {
  const records = Array.isArray(index.records) ? index.records.map(clone) : [];
  const diagnostics = Array.isArray(index.diagnostics) ? index.diagnostics.map(clone) : [];
  return {
    getResearchRecord(problemId) {
      const record = records.find((item) => item.problemId === problemId);
      return record ? clone(record) : null;
    },
    getAttempt(problemId, attemptId) {
      const record = records.find((item) => item.problemId === problemId);
      const attempt = record?.attempts.find((item) => item.id === attemptId);
      return attempt ? clone(attempt) : null;
    },
    getDiagnostics(problemId = null) {
      return diagnostics
        .filter((item) => !problemId || item.relativePath.includes(`/${problemId}/`) || item.relativePath.startsWith(`problems/${problemId}/`))
        .map(clone);
    },
  };
}
```

- [ ] **Step 5: Make the build script write the research index**

Modify `scripts/build-problem-index.mjs`:

```js
import { buildResearchIndex } from "../lib/problems/research-indexer.mjs";
```

After writing `outputPath`, write:

```js
const researchOutputPath = resolve(readArg("--research-out", join(rootDir, ".generated/research-index.json")));
const researchIndex = await buildResearchIndex({ rootDir, problemsDir });
await mkdir(dirname(researchOutputPath), { recursive: true });
await writeFile(researchOutputPath, `${JSON.stringify(researchIndex, null, 2)}\n`);
console.log(`research index: wrote ${relative(rootDir, researchOutputPath)}`);
```

- [ ] **Step 6: Add the focused test script**

Modify `package.json` `scripts.test:unit:problems` to include:

```json
"node --test tests/static-example-content.test.mjs tests/example-research.test.mjs tests/problem-schema.test.mjs tests/problem-indexer.test.mjs tests/dev-problem-index.test.mjs tests/problem-repository.test.mjs tests/codex-launch.test.mjs tests/problem-presentation.test.mjs tests/problem-view-state.test.mjs tests/imported-research-schema.test.mjs tests/research-indexer.test.mjs"
```

- [ ] **Step 7: Run tests and verify GREEN**

Run:

```bash
node --test tests/imported-research-schema.test.mjs tests/research-indexer.test.mjs
npm run test:unit:problems
```

Expected: both commands PASS.

- [ ] **Step 8: Commit research indexing**

```bash
git add tests/research-indexer.test.mjs lib/problems/research-indexer.mjs lib/problems/research-repository.mjs scripts/build-problem-index.mjs package.json
git commit -m "feat: index imported research records"
```

---

### Task 3: Generalize Research Presentation Helpers

**Files:**
- Create: `tests/research-presentation.test.mjs`
- Create: `lib/problems/research-presentation.mjs`
- Modify: `lib/problems/example-presentation.mjs`
- Modify: `tests/example-research.test.mjs`

**Interfaces:**
- Consumes: normalized attempts from Task 1 and indexed records from Task 2.
- Produces: `buildResearchLedger(record)`, `buildResearchAttemptDossier(attempt, recordManifest)`, `formatMetricValue(value, timingStatus)`, `formatCandidate(candidate)`, `formatGateLabel(value)`.
- Keeps existing exports from `lib/problems/example-presentation.mjs` working for `Prob-000`.

- [ ] **Step 1: Write failing generic presentation tests**

Create `tests/research-presentation.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";

import {
  buildResearchAttemptDossier,
  buildResearchLedger,
  formatCandidate,
  formatMetricValue,
} from "../lib/problems/research-presentation.mjs";
import { RESEARCH_DISCLAIMER } from "../lib/problems/research-schema.mjs";

const manifest = {
  problemId: "Prob-001",
  disclaimer: RESEARCH_DISCLAIMER,
};

function attempt(id, overrides = {}) {
  const sequence = Number(id.slice(4));
  return {
    problemId: "Prob-001",
    id,
    sequence,
    cohort: sequence <= 100 ? "cohort-001-100" : "cohort-101-200",
    title: `CSS Distance Proposal ${String(sequence).padStart(3, "0")}`,
    summary: "Imported AutoQEC trial record.",
    stage: "development",
    decision: "rejected",
    gate: { containment: "passed", publicContract: "passed", development: "failed" },
    method: { description: "kernel sampling", learnedFrom: null },
    metrics: {
      runs: 24,
      verifiedWitnesses: 12,
      targetHits: 12,
      timeouts: 0,
      crashes: 0,
      invalidClaims: 12,
      weightedTargetHits: 12,
      normalizedQuality: 0.5,
      runtimeSeconds: 4.705462539917789,
      averageSeconds: null,
      medianSeconds: null,
      p95Seconds: null,
      timingStatus: "legacy-not-recorded",
      speedup: null,
    },
    provenance: {
      sourceRepository: "AutoQEC",
      sourceBranch: `autoresearch/css-distance/run200-proposal-${sequence}`,
      sourceCommit: "d".repeat(40),
      sourceInfrastructureCommit: "b6a0e03c05a653b4e85160a703c0be4eef06b619",
      sourceCohort: "cohort-101-200",
      model: null,
    },
    candidate: { status: "present", path: "candidate.py" },
    artifacts: [
      { path: "LOG.md", sha256: "a".repeat(64), sourcePath: "LOG.md" },
      { path: "REPORT.md", sha256: "b".repeat(64), sourcePath: "REPORT.md" },
    ],
    ...overrides,
  };
}

test("builds aggregate cards and ordered rows without synthetic speedups", () => {
  const record = {
    problemId: "Prob-001",
    manifest,
    attempts: [
      attempt("ATT-002", { decision: "accepted", metrics: { ...attempt("ATT-002").metrics, targetHits: 23, normalizedQuality: 0.9722222222222222 } }),
      attempt("ATT-001"),
    ],
  };

  const ledger = buildResearchLedger(record);

  assert.deepEqual(ledger.cards, [
    { label: "Attempts", value: "2" },
    { label: "Accepted", value: "1" },
    { label: "Best hits", value: "23/24" },
    { label: "Candidates", value: "2 present" },
  ]);
  assert.deepEqual(ledger.rows.map((row) => row.id), ["ATT-001", "ATT-002"]);
  assert.equal(ledger.rows[0].p95, "legacy not recorded");
  assert.equal(ledger.rows[0].candidate, "present");
  assert.equal(ledger.rows[0].href, "/problems/Prob-001/attempts/ATT-001");
});

test("formats recorded, legacy, not-run, and missing candidate states distinctly", () => {
  assert.equal(formatMetricValue(9.437287125037983, "recorded"), "9.44 s");
  assert.equal(formatMetricValue(null, "legacy-not-recorded"), "legacy not recorded");
  assert.equal(formatMetricValue(null, "not-run"), "not run");
  assert.equal(formatCandidate({ status: "not-generated" }), "not generated");
});

test("builds an attempt dossier with provenance, artifacts, and missing-candidate message", () => {
  const dossier = buildResearchAttemptDossier(attempt("ATT-101", {
    candidate: { status: "not-generated" },
    gate: { containment: "passed", publicContract: "failed", development: "failed" },
    metrics: {
      runs: 0,
      verifiedWitnesses: 0,
      targetHits: 0,
      timeouts: 0,
      crashes: 0,
      invalidClaims: 1,
      weightedTargetHits: 0,
      normalizedQuality: 0,
      runtimeSeconds: null,
      averageSeconds: null,
      medianSeconds: null,
      p95Seconds: null,
      timingStatus: "not-run",
      speedup: null,
    },
  }), manifest);

  assert.equal(dossier.candidate.message, "Candidate code was not generated.");
  assert.deepEqual(dossier.metrics.map((metric) => metric.value), ["0/0", "0", "0.000", "not run", "not run", "not run"]);
  assert.equal(dossier.provenance.sourceRepository, "AutoQEC");
  assert.deepEqual(dossier.artifacts.map((artifact) => artifact.path), [
    "problems/Prob-001/attempts/ATT-101/LOG.md",
    "problems/Prob-001/attempts/ATT-101/REPORT.md",
  ]);
});
```

- [ ] **Step 2: Run presentation tests and verify RED**

Run:

```bash
node --test tests/research-presentation.test.mjs
```

Expected: FAIL because `research-presentation.mjs` does not exist.

- [ ] **Step 3: Implement generic presentation helpers**

Create `lib/problems/research-presentation.mjs`. Required behavior:

```js
export function formatMetricValue(value, timingStatus) {
  if (timingStatus === "not-run") return "not run";
  if (value === null || value === undefined) return "legacy not recorded";
  return `${Number(value).toFixed(2)} s`;
}

export function formatCandidate(candidate) {
  return candidate.status === "present" ? "present" : "not generated";
}

export function buildResearchArtifactPath(problemId, attemptId, artifactPath) {
  return `problems/${problemId}/attempts/${attemptId}/${artifactPath}`;
}
```

`buildResearchLedger(record)` must sort attempts by `sequence`, compute cards from actual values only, and row fields:

```js
{
  id,
  title,
  method,
  summary,
  cohort,
  stage,
  decision,
  publicContract,
  runs,
  verified,
  hits,
  quality,
  runtime,
  p95,
  candidate,
  href,
}
```

`buildResearchAttemptDossier(attempt, manifest)` must include `disclaimer`, metric strip, method description, evaluation path, provenance, candidate state, and artifact objects with repository-relative paths and hashes.

- [ ] **Step 4: Keep the synthetic example wrapper stable**

Modify `lib/problems/example-presentation.mjs` so existing functions call generic formatters where the shapes match but keep `buildExampleResearchLedger()` and `buildAttemptDossier()` export names. The synthetic fixture can retain its `speedup` card and artifact root through `getStaticResearchArtifactPath()`.

- [ ] **Step 5: Run presentation suites and verify GREEN**

Run:

```bash
node --test tests/research-presentation.test.mjs tests/example-research.test.mjs tests/problem-presentation.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit presentation helpers**

```bash
git add tests/research-presentation.test.mjs lib/problems/research-presentation.mjs lib/problems/example-presentation.mjs tests/example-research.test.mjs
git commit -m "feat: present imported research ledgers"
```

---

### Task 4: Render Real Research Routes

**Files:**
- Create: `lib/problems/research-route-data.mjs`
- Modify: `app/problems/[id]/page.tsx`
- Modify: `app/problems/[id]/attempts/[attemptId]/page.tsx`
- Create: `tests/problem-routes-research.test.mjs`
- Modify: `package.json`

**Interfaces:**
- Consumes: `.generated/problem-index.json`, `.generated/research-index.json`, `createResearchRepository()`, `buildResearchLedger()`, `buildResearchAttemptDossier()`.
- Produces: `buildProblemDetailResearchState({ problem, researchRecord, diagnostics })`, `buildAttemptDetailResearchState({ problem, researchRecord, attemptId })`, real `Prob-001` ledger and attempt dossier pages; unknown attempts still call `notFound()`.

- [ ] **Step 1: Write route-state tests that prove the real research branches**

Create `tests/problem-routes-research.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";

import {
  buildAttemptDetailResearchState,
  buildProblemDetailResearchState,
} from "../lib/problems/research-route-data.mjs";

const problem = {
  id: "Prob-001",
  title: "AutoQEC CSS-distance autoresearch record",
  summary: "Imported 200-trial CSS-distance experiment history.",
  status: "solved",
};

const attempt101 = {
  problemId: "Prob-001",
  id: "ATT-101",
  sequence: 101,
  cohort: "cohort-101-200",
  title: "CSS Distance Proposal 101",
  summary: "Imported AutoQEC trial record.",
  stage: "development",
  decision: "rejected",
  gate: { containment: "passed", publicContract: "failed", development: "failed" },
  method: { description: "Proposal contract failure", learnedFrom: null },
  metrics: { runs: 0, verifiedWitnesses: 0, targetHits: 0, timeouts: 0, crashes: 0, invalidClaims: 1, weightedTargetHits: 0, normalizedQuality: 0, runtimeSeconds: null, averageSeconds: null, medianSeconds: null, p95Seconds: null, timingStatus: "not-run", speedup: null },
  provenance: { sourceRepository: "AutoQEC", sourceBranch: "autoresearch/css-distance/run200-proposal-101", sourceCommit: "a".repeat(40), sourceInfrastructureCommit: "12a8f794f68d63f07303df0cc38fa244c1ab1248", sourceCohort: "cohort-101-200", model: null },
  candidate: { status: "not-generated" },
  artifacts: [{ path: "LOG.md", sha256: "b".repeat(64), sourcePath: "LOG.md" }],
};

const record = {
  problemId: "Prob-001",
  manifest: {
    problemId: "Prob-001",
    disclaimer: "Imported experimental record - not reviewed knowledge.",
  },
  attempts: [attempt101],
};

test("problem detail state chooses the real research ledger when a record exists", () => {
  const state = buildProblemDetailResearchState({ problem, researchRecord: record, diagnostics: [] });

  assert.equal(state.kind, "research");
  assert.equal(state.problem.id, "Prob-001");
  assert.equal(state.ledger.rows.length, 1);
  assert.equal(state.ledger.rows[0].id, "ATT-101");
  assert.equal(state.disclaimer, "Imported experimental record - not reviewed knowledge.");
});

test("problem detail state exposes integrity diagnostics instead of a partial ledger", () => {
  const state = buildProblemDetailResearchState({
    problem,
    researchRecord: null,
    diagnostics: [{ relativePath: "problems/Prob-001/attempts/ATT-101/attempt.json", field: "metrics", message: "bad metrics" }],
  });

  assert.equal(state.kind, "research-diagnostics");
  assert.match(state.diagnostics[0].message, /bad metrics/);
});

test("attempt detail state returns dossiers for known attempts and not-found for unknown attempts", () => {
  const found = buildAttemptDetailResearchState({ problem, researchRecord: record, attemptId: "ATT-101" });
  assert.equal(found.kind, "research-attempt");
  assert.equal(found.dossier.id, "ATT-101");
  assert.equal(found.dossier.candidate.message, "Candidate code was not generated.");

  const missing = buildAttemptDetailResearchState({ problem, researchRecord: record, attemptId: "ATT-999" });
  assert.equal(missing.kind, "not-found");
});
```

- [ ] **Step 2: Run route smoke test and verify RED**

Run:

```bash
node --test tests/problem-routes-research.test.mjs
```

Expected: FAIL because `research-route-data.mjs` does not exist.

- [ ] **Step 3: Implement the route-state helpers**

Create `lib/problems/research-route-data.mjs`:

```js
import {
  buildResearchAttemptDossier,
  buildResearchLedger,
} from "./research-presentation.mjs";

export function buildProblemDetailResearchState({ problem, researchRecord, diagnostics = [] }) {
  if (researchRecord) {
    return {
      kind: "research",
      problem,
      disclaimer: researchRecord.manifest.disclaimer,
      ledger: buildResearchLedger(researchRecord),
    };
  }
  if (diagnostics.length > 0) {
    return {
      kind: "research-diagnostics",
      problem,
      diagnostics: diagnostics.map((item) => ({ ...item })),
    };
  }
  return { kind: "generic", problem };
}

export function buildAttemptDetailResearchState({ problem, researchRecord, attemptId }) {
  const attempt = researchRecord?.attempts.find((item) => item.id === attemptId);
  if (!attempt) return { kind: "not-found", problem };
  return {
    kind: "research-attempt",
    problem,
    dossier: buildResearchAttemptDossier(attempt, researchRecord.manifest),
  };
}
```

- [ ] **Step 4: Import and use generated research data in the problem detail route**

Modify `app/problems/[id]/page.tsx`:

```tsx
import generatedResearchIndex from "../../../.generated/research-index.json";
import { createResearchRepository } from "@/lib/problems/research-repository.mjs";
import { buildProblemDetailResearchState } from "@/lib/problems/research-route-data.mjs";
```

After loading `problem`, create:

```tsx
const researchRepository = createResearchRepository(generatedResearchIndex);
const researchRecord = researchRepository.getResearchRecord(problem.id);
const researchDiagnostics = researchRepository.getDiagnostics(problem.id);
const researchState = buildProblemDetailResearchState({ problem, researchRecord, diagnostics: researchDiagnostics });
```

Before the generic placeholder return, add a branch:

```tsx
if (researchState.kind === "research") {
  const ledger = researchState.ledger;
  return (
    <main className="detail-shell research-shell">
      <Link className="back-link" href="/">← Back to problems</Link>
      <header className="research-header">
        <div>
          <p className="eyebrow">{problem.id}</p>
          <h1>{problem.title}</h1>
          <p className="detail-summary">{problem.summary}</p>
        </div>
        <div className="research-badges" aria-label="Research metadata">
          <span>{problem.status}</span>
          <span>Imported record</span>
          <span>{ledger.rows.length} attempts</span>
        </div>
      </header>
      <p className="example-disclaimer">{researchState.disclaimer}</p>
      <dl className="research-metric-strip" aria-label="Research metrics">
        {ledger.cards.map((card) => (
          <div key={card.label}><dt>{card.label}</dt><dd>{card.value}</dd></div>
        ))}
      </dl>
      <section className="attempt-ledger" aria-labelledby="attempt-ledger-heading">
        <div className="section-heading-row">
          <h2 id="attempt-ledger-heading">Attempts</h2>
          <p>{ledger.rows.length} imported attempts</p>
        </div>
        <div className="attempt-table-wrap">
          <table className="attempt-table">
            <thead>
              <tr>
                <th scope="col">Attempt</th><th scope="col">Method</th><th scope="col">Decision</th><th scope="col">Public contract</th><th scope="col">Runs</th><th scope="col">Verified</th><th scope="col">Hits</th><th scope="col">Quality</th><th scope="col">Runtime</th><th scope="col">P95</th><th scope="col">Candidate</th><th scope="col">Open</th>
              </tr>
            </thead>
            <tbody>
              {ledger.rows.map((row) => (
                <tr key={row.id}>
                  <th scope="row"><Link href={row.href}>{row.id}</Link></th>
                  <td><strong>{row.method}</strong><span>{row.summary}</span></td>
                  <td>{row.decision}</td>
                  <td>{row.publicContract}</td>
                  <td>{row.runs}</td>
                  <td>{row.verified}</td>
                  <td>{row.hits}</td>
                  <td>{row.quality}</td>
                  <td>{row.runtime}</td>
                  <td>{row.p95}</td>
                  <td>{row.candidate}</td>
                  <td><Link href={row.href}>Open</Link></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="attempt-card-list" aria-label="Attempt cards">
          {ledger.rows.map((row) => (
            <Link className="attempt-card" href={row.href} key={row.id}>
              <span>{row.id}</span>
              <strong>{row.method}</strong>
              <small>{row.decision} · {row.verified} verified · {row.candidate}</small>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
```

If `researchState.kind === "research-diagnostics"`, render a diagnostic panel instead of the generic placeholder.

- [ ] **Step 5: Import and use generated research data in the attempt route**

Modify `app/problems/[id]/attempts/[attemptId]/page.tsx`:

```tsx
import generatedResearchIndex from "../../../../../.generated/research-index.json";
import { createResearchRepository } from "@/lib/problems/research-repository.mjs";
import { buildAttemptDetailResearchState } from "@/lib/problems/research-route-data.mjs";
```

After the synthetic example branch remains available, allow real attempts:

```tsx
const researchRepository = createResearchRepository(generatedResearchIndex);
const researchRecord = researchRepository.getResearchRecord(problem.id);
const researchState = buildAttemptDetailResearchState({ problem, researchRecord, attemptId });

if (researchState.kind === "research-attempt") {
  const dossier = researchState.dossier;
  return (
    <main className="detail-shell attempt-shell">
      <div className="breadcrumb-row">
        <Link className="back-link" href={`/problems/${problem.id}`}>← Back to research ledger</Link>
        <Link className="back-link muted-back-link" href="/">Problem library</Link>
      </div>
      <header className="attempt-header">
        <div>
          <p className="eyebrow">{`${problem.id} / ${dossier.id}`}</p>
          <h1>{dossier.title}</h1>
          <p className="detail-summary">{dossier.summary}</p>
        </div>
        <div className="research-badges" aria-label="Attempt metadata">
          <span>{dossier.stage}</span>
          <span>{dossier.decision}</span>
          <span>{dossier.candidate.label}</span>
        </div>
      </header>
      <p className="example-disclaimer">{dossier.disclaimer}</p>
      {dossier.candidate.message ? <p className="example-disclaimer">{dossier.candidate.message}</p> : null}
      <dl className="attempt-metric-strip" aria-label="Attempt metrics">
        {dossier.metrics.map((metric) => (
          <div key={metric.label}><dt>{metric.label}</dt><dd>{metric.value}</dd></div>
        ))}
      </dl>
      <div className="attempt-layout">
        <section className="attempt-main" aria-label="Attempt research record">
          <article><h2>Method</h2><p>{dossier.method.description}</p></article>
          <article>
            <h2>Evaluation path</h2>
            <ol className="evaluation-path">
              {dossier.evaluationPath.map((item) => (
                <li key={item.label}><span>{item.label}</span><strong>{item.value}</strong></li>
              ))}
            </ol>
          </article>
        </section>
        <aside className="attempt-audit" aria-label="Attempt audit metadata">
          <section>
            <h2>Provenance</h2>
            <dl>
              <div><dt>Branch</dt><dd>{dossier.provenance.sourceBranch}</dd></div>
              <div><dt>Commit</dt><dd>{dossier.provenance.sourceCommit}</dd></div>
              <div><dt>Infrastructure</dt><dd>{dossier.provenance.sourceInfrastructureCommit}</dd></div>
              <div><dt>Cohort</dt><dd>{dossier.provenance.sourceCohort}</dd></div>
              <div><dt>Model</dt><dd>{dossier.provenance.model ?? "not recorded"}</dd></div>
            </dl>
          </section>
          <section>
            <h2>Artifacts</h2>
            <ul>{dossier.artifacts.map((artifact) => <li key={artifact.path}><code>{artifact.path}</code><span>{artifact.sha256}</span></li>)}</ul>
          </section>
        </aside>
      </div>
    </main>
  );
}
```

Unknown real attempts must fall through to `notFound()`.

- [ ] **Step 6: Add the route test to focused problem tests**

Modify `package.json` `test:unit:problems` to include `tests/problem-routes-research.test.mjs`.

- [ ] **Step 7: Run route and problem suites**

Run:

```bash
node --test tests/problem-routes-research.test.mjs tests/research-presentation.test.mjs
npm run test:unit:problems
```

Expected: PASS.

- [ ] **Step 8: Commit routes**

```bash
git add lib/problems/research-route-data.mjs 'app/problems/[id]/page.tsx' 'app/problems/[id]/attempts/[attemptId]/page.tsx' tests/problem-routes-research.test.mjs package.json
git commit -m "feat: render imported research routes"
```

---

### Task 5: Parse AutoQEC Reports and Read Source Git Objects

**Files:**
- Create: `tests/autoqec-css-distance-report.test.mjs`
- Create: `lib/problems/autoqec-css-distance/reports.mjs`
- Create: `lib/problems/autoqec-css-distance/git-source.mjs`

**Interfaces:**
- Produces: `parseAutoqecReport(text, { proposalNumber })`.
- Produces: `buildTrialRef(proposalNumber)`, `discoverTrialRefs(sourceDir)`, `readGitText(sourceDir, ref, path)`, `readGitBlob(sourceDir, ref, path)`, `getCommitAndFirstParent(sourceDir, ref)`, `listGitTree(sourceDir, ref)`.

- [ ] **Step 1: Write parser tests from observed report contracts**

Create `tests/autoqec-css-distance-report.test.mjs`:

```js
import assert from "node:assert/strict";
import test from "node:test";

import { buildTrialRef, parseAutoqecReport } from "../lib/problems/autoqec-css-distance/reports.mjs";

const report001 = `# CSS Distance Proposal 001 Report

## Overview

- Proposal: \`001\` of \`100\`
- Branch: \`autoresearch/css-distance/run100-proposal-001\`
- Candidate: \`proposal-workspace/candidate.py\`
- Objective: randomized CSS logical-operator witness search for an upper-bound certificate.
- Per-process hard timeout: \`300s\`

## Method

The assigned exploration direction was **randomized kernel sampling with stabilizer-coset descent**.

## Public Contract Check

Status: **passed**.

## Blinded Development Screening

| Metric | Value |
| --- | ---: |
| Decision | rejected |
| Runs | 24 |
| Verified witnesses | 12 |
| Target hits | 12 |
| Timeouts | 0 |
| Crashes | 0 |
| Invalid claims | 12 |
| Weighted target hits | 12 |
| Normalized quality | 0.5 |
| Runtime seconds | 4.705462539917789 |
`;

const report101 = `# CSS Distance Proposal 101 Report

## Method

The assigned exploration direction was **Proposal contract failure**.

## Public Contract

| Field | Value |
| --- | ---: |
| Proposal total | 200 |
| Branch | autoresearch/css-distance/run200-proposal-101 |
| Public contract status | failed |
| Timeout seconds | 300 |
| Proposal image ID | sha256:3892c207c48f8e5a7c1953b127e59b4d9fd7203a4ccd412f3b59290362c73d53 |
| Evaluator image ID | sha256:bf017fcb8296dedb434117714c4f43ee01f74ab5c349dd6488d6ea0ceaa1f62c |

## Blinded Development Screening

| Metric | Value |
| --- | ---: |
| Decision | rejected |
| Runs | 0 |
| Verified witnesses | 0 |
| Target hits | 0 |
| Timeouts | 0 |
| Crashes | 0 |
| Invalid claims | 1 |
| Weighted target hits | 0 |
| Normalized quality | 0.000000000000000 |
| Runtime seconds | 0.000000000000000 |
| Average seconds | not run |
| Median seconds | not run |
| P95 seconds | not run |
`;

const report200 = report101
  .replaceAll("101", "200")
  .replace("Proposal contract failure", "Randomized CSS kernel-combination search")
  .replace("failed", "passed")
  .replace("| Runs | 0 |", "| Runs | 24 |")
  .replace("| Verified witnesses | 0 |", "| Verified witnesses | 13 |")
  .replace("| Target hits | 0 |", "| Target hits | 13 |")
  .replace("| Invalid claims | 1 |", "| Invalid claims | 11 |")
  .replace("| Weighted target hits | 0 |", "| Weighted target hits | 13 |")
  .replace("| Normalized quality | 0.000000000000000 |", "| Normalized quality | 0.541666666666667 |")
  .replace("| Runtime seconds | 0.000000000000000 |", "| Runtime seconds | 85.783838119939901 |")
  .replace("| Average seconds | not run |", "| Average seconds | 3.574326588330829 |")
  .replace("| Median seconds | not run |", "| Median seconds | 2.232983041496482 |")
  .replace("| P95 seconds | not run |", "| P95 seconds | 9.437287125037983 |");

test("maps proposal numbers to the exact AutoQEC trial refs", () => {
  assert.equal(buildTrialRef(1), "autoresearch/css-distance/run100-proposal-001");
  assert.equal(buildTrialRef(100), "autoresearch/css-distance/run100-proposal-100");
  assert.equal(buildTrialRef(101), "autoresearch/css-distance/run200-proposal-101");
  assert.equal(buildTrialRef(200), "autoresearch/css-distance/run200-proposal-200");
});

test("parses legacy 001-100 reports with legacy timing", () => {
  const parsed = parseAutoqecReport(report001, { proposalNumber: 1 });

  assert.equal(parsed.branch, "autoresearch/css-distance/run100-proposal-001");
  assert.equal(parsed.candidateSourcePath, "proposal-workspace/candidate.py");
  assert.equal(parsed.publicContract, "passed");
  assert.equal(parsed.methodDescription, "randomized kernel sampling with stabilizer-coset descent");
  assert.equal(parsed.metrics.runs, 24);
  assert.equal(parsed.metrics.runtimeSeconds, 4.705462539917789);
  assert.equal(parsed.metrics.averageSeconds, null);
  assert.equal(parsed.metrics.timingStatus, "legacy-not-recorded");
});

test("parses failed public-contract reports as not-run missing-candidate attempts", () => {
  const parsed = parseAutoqecReport(report101, { proposalNumber: 101 });

  assert.equal(parsed.branch, "autoresearch/css-distance/run200-proposal-101");
  assert.equal(parsed.publicContract, "failed");
  assert.equal(parsed.candidateSourcePath, null);
  assert.equal(parsed.metrics.runs, 0);
  assert.equal(parsed.metrics.runtimeSeconds, null);
  assert.equal(parsed.metrics.timingStatus, "not-run");
});

test("parses recorded timing in 101-200 reports", () => {
  const parsed = parseAutoqecReport(report200, { proposalNumber: 200 });

  assert.equal(parsed.publicContract, "passed");
  assert.equal(parsed.metrics.runs, 24);
  assert.equal(parsed.metrics.verifiedWitnesses, 13);
  assert.equal(parsed.metrics.averageSeconds, 3.574326588330829);
  assert.equal(parsed.metrics.medianSeconds, 2.232983041496482);
  assert.equal(parsed.metrics.p95Seconds, 9.437287125037983);
  assert.equal(parsed.metrics.timingStatus, "recorded");
});
```

- [ ] **Step 2: Run parser tests and verify RED**

Run:

```bash
node --test tests/autoqec-css-distance-report.test.mjs
```

Expected: FAIL because the parser module does not exist.

- [ ] **Step 3: Implement report parsing**

Create `lib/problems/autoqec-css-distance/reports.mjs`. Required exports:

```js
export function buildTrialRef(proposalNumber) {
  const padded = String(proposalNumber).padStart(3, "0");
  const runTotal = proposalNumber <= 100 ? "run100" : "run200";
  return `autoresearch/css-distance/${runTotal}-proposal-${padded}`;
}
```

`parseAutoqecReport()` must parse Markdown tables structurally by line, not by hard-coded offsets. Implement a table helper:

```js
function parseMarkdownTable(sectionText) {
  const rows = new Map();
  for (const line of sectionText.split(/\r?\n/)) {
    const match = line.match(/^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$/);
    if (!match || /^-+$/.test(match[1].trim())) continue;
    rows.set(match[1].trim().toLowerCase(), match[2].trim().replace(/^`|`$/g, ""));
  }
  return rows;
}
```

Normalize `Average seconds`, `Median seconds`, and `P95 seconds` values of `not run` to `null` and `timingStatus: "not-run"`. For reports without those fields, use `timingStatus: "legacy-not-recorded"` and set average, median, and p95 to `null`. Do not convert missing values to zero.

- [ ] **Step 4: Implement read-only Git helpers**

Create `lib/problems/autoqec-css-distance/git-source.mjs`. Use `execFile` only with `git -C sourceDir ...`:

```js
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export async function git(sourceDir, args, options = {}) {
  const result = await execFileAsync("git", ["-C", sourceDir, ...args], {
    maxBuffer: options.maxBuffer ?? 50 * 1024 * 1024,
    encoding: options.encoding ?? "utf8",
  });
  return result.stdout;
}
```

Required helpers:

```js
export async function assertReadableGitRepository(sourceDir) {
  const inside = (await git(sourceDir, ["rev-parse", "--is-inside-work-tree"])).trim();
  if (inside !== "true") throw new Error(`AutoQEC source is not a Git work tree: ${sourceDir}`);
}

export async function getCommitAndFirstParent(sourceDir, ref) {
  const line = (await git(sourceDir, ["rev-list", "--parents", "-n", "1", ref])).trim();
  const [commit, firstParent] = line.split(/\s+/);
  if (!commit || !firstParent) throw new Error(`Trial ref has no first parent: ${ref}`);
  return { commit, firstParent };
}

export async function readGitText(sourceDir, ref, path) {
  return git(sourceDir, ["show", `${ref}:${path}`]);
}
```

For binary blob reads, use `execFileAsync` with `encoding: "buffer"` and return a `Buffer`.

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
node --test tests/autoqec-css-distance-report.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit report and Git-source helpers**

```bash
git add tests/autoqec-css-distance-report.test.mjs lib/problems/autoqec-css-distance/reports.mjs lib/problems/autoqec-css-distance/git-source.mjs
git commit -m "feat: parse AutoQEC CSS distance reports"
```

---

### Task 6: Implement Safe Import and Infrastructure Freezing

**Files:**
- Create: `tests/autoqec-css-distance-importer.test.mjs`
- Create: `lib/problems/autoqec-css-distance/infrastructure.mjs`
- Create: `lib/problems/autoqec-css-distance/importer.mjs`

**Interfaces:**
- Consumes: Tasks 1 and 5.
- Produces: `expectedInfrastructureForAttempt(sequence, ranges = AUTOQEC_INFRASTRUCTURE_RANGES)`, `buildCohortManifests(ranges = AUTOQEC_INFRASTRUCTURE_RANGES)`, `buildInfrastructurePlan(trials, { ranges } = {})`, `importAutoqecCssDistance({ rootDir, sourceDir, now, expectedAttempts, infrastructureRanges })`.

- [ ] **Step 1: Write importer tests with a synthetic Git source**

Create `tests/autoqec-css-distance-importer.test.mjs`. The test source must be a tiny Git repo created under `tmpdir()` with three trial branches and three parent infrastructure commits. Use `git init`, `git add`, `git commit`, and branches named like real AutoQEC refs. The full real import uses `AUTOQEC_INFRASTRUCTURE_RANGES`; the synthetic import test passes an explicit `infrastructureRanges` array built from the synthetic first-parent commit IDs so the test does not depend on impossible real AutoQEC commit hashes. The focused tests:

```js
test("maps attempts to the exact six infrastructure ranges", () => {
  assert.equal(expectedInfrastructureForAttempt(1).commit, "c4533f982ece376c5f299a13edfabff0f489182c");
  assert.equal(expectedInfrastructureForAttempt(100).commit, "3e61f5ac8143e4848e5e814188c83683c74dfe4c");
  assert.equal(expectedInfrastructureForAttempt(101).commit, "12a8f794f68d63f07303df0cc38fa244c1ab1248");
  assert.equal(expectedInfrastructureForAttempt(108).commit, "3f30f39a2f9be8ceead3821706aae77acdd980aa");
  assert.equal(expectedInfrastructureForAttempt(200).commit, "b6a0e03c05a653b4e85160a703c0be4eef06b619");
});

test("builds cohort manifests from the exact range table", () => {
  assert.deepEqual(buildCohortManifests().map((manifest) => manifest.id), ["cohort-001-100", "cohort-101-200"]);
  assert.deepEqual(buildCohortManifests()[0].attempts, [
    { first: 1, last: 1, sourceInfrastructureCommit: "c4533f982ece376c5f299a13edfabff0f489182c" },
    { first: 2, last: 100, sourceInfrastructureCommit: "3e61f5ac8143e4848e5e814188c83683c74dfe4c" },
  ]);
});

test("refuses an infrastructure first-parent mismatch", async () => {
  await assert.rejects(
    buildInfrastructurePlan([{ sequence: 1, firstParent: "0".repeat(40) }]),
    /infrastructure commit mismatch/,
  );
});

test("accepts a synthetic range map for temporary Git-source imports", async () => {
  const ranges = [
    { first: 1, last: 1, cohort: "cohort-001-100", commit: "1".repeat(40) },
    { first: 101, last: 101, cohort: "cohort-101-200", commit: "2".repeat(40) },
    { first: 200, last: 200, cohort: "cohort-101-200", commit: "3".repeat(40) },
  ];
  const plan = await buildInfrastructurePlan([
    { sequence: 1, firstParent: "1".repeat(40) },
    { sequence: 101, firstParent: "2".repeat(40) },
    { sequence: 200, firstParent: "3".repeat(40) },
  ], { ranges });

  assert.deepEqual(plan.map((item) => item.commit), ["1".repeat(40), "2".repeat(40), "3".repeat(40)]);
});

test("safe artifact policy rejects path escapes and symlinks", async () => {
  assert.throws(() => assertSafeImportPath("../candidate.py"), /unsafe/);
  assert.throws(() => assertSafeImportPath("/candidate.py"), /unsafe/);
});
```

Also add a synthetic end-to-end import test that imports three trials through test-only `expectedAttempts: [1, 101, 200]` and `infrastructureRanges` options and asserts the generated structure:

```js
assert.equal(await fileExists(join(root, "problems", "Prob-001", "attempts", "ATT-101", "candidate.py")), false);
assert.equal(JSON.parse(await readFile(join(root, "problems", "Prob-001", "attempts", "ATT-101", "attempt.json"), "utf8")).candidate.status, "not-generated");
assert.equal((await readdir(join(root, "problems", "Prob-001", "infrastructure", "snapshots"))).length, 3);
```

- [ ] **Step 2: Run importer tests and verify RED**

Run:

```bash
node --test tests/autoqec-css-distance-importer.test.mjs
```

Expected: FAIL because infrastructure and importer modules do not exist.

- [ ] **Step 3: Implement infrastructure range helpers**

Create `lib/problems/autoqec-css-distance/infrastructure.mjs`:

```js
import { AUTOQEC_INFRASTRUCTURE_RANGES } from "../research-schema.mjs";

export function expectedInfrastructureForAttempt(sequence, ranges = AUTOQEC_INFRASTRUCTURE_RANGES) {
  const range = ranges.find((item) => sequence >= item.first && sequence <= item.last);
  if (!range) throw new Error(`No infrastructure range for ATT-${String(sequence).padStart(3, "0")}`);
  return range;
}

export function buildCohortManifests(ranges = AUTOQEC_INFRASTRUCTURE_RANGES) {
  return ["cohort-001-100", "cohort-101-200"].map((cohort) => ({
    schemaVersion: 1,
    kind: "autoqec-css-distance-cohort",
    id: cohort,
    problemId: "Prob-001",
    attempts: ranges
      .filter((range) => range.cohort === cohort)
      .map((range) => ({
        first: range.first,
        last: range.last,
        sourceInfrastructureCommit: range.commit,
      })),
  }));
}
```

`buildInfrastructurePlan(trials, { ranges = AUTOQEC_INFRASTRUCTURE_RANGES } = {})` must reject any trial whose `firstParent` does not equal `expectedInfrastructureForAttempt(trial.sequence, ranges).commit`.

- [ ] **Step 4: Implement safe import path and file metadata helpers**

Create `lib/problems/autoqec-css-distance/importer.mjs` with:

```js
import { createHash } from "node:crypto";
import { cp, mkdir, mkdtemp, rename, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

export function sha256(buffer) {
  return createHash("sha256").update(buffer).digest("hex");
}

export function assertSafeImportPath(path) {
  if (!/^(?!\/)(?!\.)(?!.*(?:^|\/)\.\.(?:\/|$))(?!.*\/\/)[A-Za-z0-9][A-Za-z0-9._@+-]*(?:\/[A-Za-z0-9][A-Za-z0-9._@+-]*)*$/.test(path)) {
    throw new Error(`unsafe import path: ${path}`);
  }
  if (path.includes(".git/") || path === ".git") throw new Error(`unsafe Git metadata path: ${path}`);
  return path;
}
```

Allowed trial source artifact mapping:

```js
const TRIAL_ARTIFACT_SOURCES = [
  { sourcePath: "LOG.md", targetPath: "LOG.md", required: true },
  { sourcePath: "REPORT.md", targetPath: "REPORT.md", required: true },
  { sourcePath: "proposal-workspace/candidate.py", targetPath: "candidate.py", required: false },
  { sourcePath: "proposal-workspace/METHOD.txt", targetPath: "METHOD.txt", required: false },
  { sourcePath: "METHOD.txt", targetPath: "METHOD.txt", required: false },
];
```

- [ ] **Step 5: Implement normalized attempt generation**

Add:

```js
export function normalizeAttempt({ sequence, parsedReport, sourceBranch, sourceCommit, sourceInfrastructureCommit, artifacts, infrastructureRanges = AUTOQEC_INFRASTRUCTURE_RANGES }) {
  const id = `ATT-${String(sequence).padStart(3, "0")}`;
  const expected = expectedInfrastructureForAttempt(sequence, infrastructureRanges);
  const hasCandidate = artifacts.some((artifact) => artifact.path === "candidate.py");
  return {
    schemaVersion: 1,
    problemId: "Prob-001",
    id,
    sequence,
    cohort: expected.cohort,
    title: `CSS Distance Proposal ${String(sequence).padStart(3, "0")}`,
    summary: "Imported AutoQEC trial record.",
    stage: "development",
    decision: parsedReport.metrics.decision,
    gate: {
      containment: "passed",
      publicContract: parsedReport.publicContract,
      development: parsedReport.metrics.decision === "accepted" ? "passed" : "failed",
    },
    method: {
      description: parsedReport.methodDescription,
      learnedFrom: null,
    },
    metrics: parsedReport.metrics,
    provenance: {
      sourceRepository: "AutoQEC",
      sourceBranch,
      sourceCommit,
      sourceInfrastructureCommit,
      sourceCohort: expected.cohort,
      model: null,
    },
    candidate: hasCandidate ? { status: "present", path: "candidate.py" } : { status: "not-generated" },
    artifacts,
  };
}
```

Validate every generated attempt through `validateResearchAttempt()`.

- [ ] **Step 6: Implement atomic import installation**

`importAutoqecCssDistance({ rootDir, sourceDir, now = () => new Date(), expectedAttempts = [1..200], infrastructureRanges = AUTOQEC_INFRASTRUCTURE_RANGES })` must:

1. Refuse if `join(rootDir, "problems", "Prob-001")` exists.
2. Create a temp directory under `tmpdir()`.
3. Read each trial `REPORT.md` and `LOG.md` through Git blobs.
4. Copy optional candidate and method only when Git tree contains them.
5. Write `problem.json`, `problem.md`, `research.json`, and generation files.
6. Write `infrastructure/cohorts/*.json`.
7. Freeze one `infrastructure/snapshots/<commit>/source/` tree per distinct expected infrastructure commit.
8. Write each `source-manifest.json`.
9. Write `import-manifest.json` last with hashes for all other imported and generated files.
10. Run offline verification from Task 8 before final `rename()`.

For Task 6, implement steps 1 through 8 and leave step 10 to call a local `verifyImportedProblemTree()` once Task 8 creates it.

- [ ] **Step 7: Run importer tests and verify GREEN**

Run:

```bash
node --test tests/autoqec-css-distance-report.test.mjs tests/autoqec-css-distance-importer.test.mjs
```

Expected: PASS.

- [ ] **Step 8: Commit importer core**

```bash
git add tests/autoqec-css-distance-importer.test.mjs lib/problems/autoqec-css-distance/infrastructure.mjs lib/problems/autoqec-css-distance/importer.mjs
git commit -m "feat: import AutoQEC trial artifacts"
```

---

### Task 7: Add Import and Verify CLI Surfaces

**Files:**
- Create: `tests/autoqec-css-distance-verify.test.mjs`
- Create: `scripts/import-autoqec-css-distance.mjs`
- Modify: `lib/problems/autoqec-css-distance/importer.mjs`
- Modify: `package.json`
- Modify: `Makefile`

**Interfaces:**
- Produces CLI:
  - `node scripts/import-autoqec-css-distance.mjs import --source /Users/nzy/AutoQEC --root /Users/nzy/mcode/research-loop`
  - `node scripts/import-autoqec-css-distance.mjs verify --id Prob-001 --root /Users/nzy/mcode/research-loop`
- Produces Make targets:
  - `make problem-import-autoqec-css-distance SOURCE=/Users/nzy/AutoQEC`
  - `make problem-import-verify ID=Prob-001`

- [ ] **Step 1: Write offline verification tests**

Create `tests/autoqec-css-distance-verify.test.mjs`:

```js
import assert from "node:assert/strict";
import { mkdir, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { verifyImportedProblemTree } from "../lib/problems/autoqec-css-distance/importer.mjs";

test("offline verification recomputes import-manifest hashes", async () => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-import-verify-"));
  const problem = join(root, "problems", "Prob-001");
  await mkdir(join(problem, "attempts", "ATT-001"), { recursive: true });
  await writeFile(join(problem, "attempts", "ATT-001", "LOG.md"), "log\n");
  await writeFile(join(problem, "import-manifest.json"), JSON.stringify({
    schemaVersion: 1,
    kind: "autoqec-css-distance-import",
    problemId: "Prob-001",
    sourceRepository: "AutoQEC",
    importedAt: "2026-07-28T00:00:00.000Z",
    attempts: 1,
    files: [{
      path: "attempts/ATT-001/LOG.md",
      sourcePath: "LOG.md",
      sha256: "fb1c4b1af10a35ed036f32f59c94fb7b6927e3d5f3a23f1c98a7b294b3b54c5d",
      size: 4,
      generated: false,
    }],
  }, null, 2));

  assert.equal((await verifyImportedProblemTree({ rootDir: root, id: "Prob-001" })).ok, true);

  await writeFile(join(problem, "attempts", "ATT-001", "LOG.md"), "changed\n");
  const result = await verifyImportedProblemTree({ rootDir: root, id: "Prob-001" });
  assert.equal(result.ok, false);
  assert.match(result.errors[0].message, /hash mismatch/);
});
```

- [ ] **Step 2: Run verification tests and verify RED**

Run:

```bash
node --test tests/autoqec-css-distance-verify.test.mjs
```

Expected: FAIL because `verifyImportedProblemTree()` does not exist.

- [ ] **Step 3: Implement offline verification**

Add `verifyImportedProblemTree({ rootDir, id = "Prob-001" })` to `lib/problems/autoqec-css-distance/importer.mjs`. It must read only the imported tree and:

```js
const manifestPath = join(rootDir, "problems", id, "import-manifest.json");
const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
const manifestValidation = validateImportManifest(manifest, { relativePath: `problems/${id}/import-manifest.json` });
```

For each `manifest.files` entry:

```js
const filePath = join(rootDir, "problems", id, entry.path);
const bytes = await readFile(filePath);
if (bytes.byteLength !== entry.size) addError(entry.path, "size", "size mismatch");
if (sha256(bytes) !== entry.sha256) addError(entry.path, "sha256", "hash mismatch");
```

Also read and validate `research.json`, all `attempt.json`, both cohort manifests, and all six `source-manifest.json` files when `id === "Prob-001"` and `manifest.attempts === 200`.

- [ ] **Step 4: Add CLI mode parsing**

Create `scripts/import-autoqec-css-distance.mjs`:

```js
import { resolve } from "node:path";
import { importAutoqecCssDistance, verifyImportedProblemTree } from "../lib/problems/autoqec-css-distance/importer.mjs";

function readArg(name, fallback = null) {
  const index = process.argv.indexOf(name);
  return index === -1 ? fallback : process.argv[index + 1];
}

const mode = process.argv[2];
const rootDir = resolve(readArg("--root", process.cwd()));

if (mode === "import") {
  const sourceDir = readArg("--source");
  if (!sourceDir) {
    console.error("usage: node scripts/import-autoqec-css-distance.mjs import --source /Users/nzy/AutoQEC");
    process.exit(2);
  }
  await importAutoqecCssDistance({ rootDir, sourceDir: resolve(sourceDir) });
  console.log("AutoQEC CSS-distance import complete: problems/Prob-001");
} else if (mode === "verify") {
  const id = readArg("--id", "Prob-001");
  const result = await verifyImportedProblemTree({ rootDir, id });
  if (!result.ok) {
    for (const error of result.errors) {
      console.error(`${error.relativePath}: ${error.field}: ${error.message}`);
    }
    process.exit(1);
  }
  console.log(`AutoQEC CSS-distance import verified: ${id}`);
} else {
  console.error("usage: node scripts/import-autoqec-css-distance.mjs <import|verify>");
  process.exit(2);
}
```

- [ ] **Step 5: Add package and Make targets**

Modify `package.json` scripts:

```json
"problem:import:autoqec-css-distance": "node scripts/import-autoqec-css-distance.mjs import",
"problem:import:verify": "node scripts/import-autoqec-css-distance.mjs verify"
```

Modify `Makefile` `.PHONY` list to include:

```make
problem-import-autoqec-css-distance problem-import-verify
```

Add help text:

```make
	@echo '  make problem-import-autoqec-css-distance SOURCE=/Users/nzy/AutoQEC  import the 200-trial AutoQEC CSS-distance record as Prob-001'
	@echo '  make problem-import-verify ID=Prob-001                         verify a committed imported problem without reading AutoQEC'
```

Add targets:

```make
problem-import-autoqec-css-distance: node_modules/.package-lock.json
	@if [ -z "$(SOURCE)" ]; then \
		echo 'usage: make problem-import-autoqec-css-distance SOURCE=/Users/nzy/AutoQEC' >&2; \
		exit 2; \
	fi
	npm run problem:import:autoqec-css-distance -- --source "$(SOURCE)"

problem-import-verify: node_modules/.package-lock.json
	npm run problem:import:verify -- --id "$(or $(ID),Prob-001)"
```

- [ ] **Step 6: Run verification and CLI tests**

Run:

```bash
node --test tests/autoqec-css-distance-verify.test.mjs tests/autoqec-css-distance-importer.test.mjs
make problem-import-verify ID=Prob-404
```

Expected: Node tests PASS. `make problem-import-verify ID=Prob-404` exits non-zero with a clear missing-manifest diagnostic.

- [ ] **Step 7: Commit CLI surfaces**

```bash
git add tests/autoqec-css-distance-verify.test.mjs scripts/import-autoqec-css-distance.mjs lib/problems/autoqec-css-distance/importer.mjs package.json Makefile
git commit -m "feat: verify AutoQEC imports offline"
```

---

### Task 8: Update Dev Watchers for Research Files

**Files:**
- Modify: `tests/dev-problem-index.test.mjs`
- Modify: `scripts/dev-problem-index.mjs`

**Interfaces:**
- Consumes: build script from Task 2.
- Produces: dev index rebuilds when research manifests or attempt manifests change.

- [ ] **Step 1: Extend watcher tests**

Add to `tests/dev-problem-index.test.mjs`:

```js
test("watches research manifests and attempt manifests", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-dev-watch-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(join(root, "problems", "Prob-001", "attempts", "ATT-001"), { recursive: true });
  await mkdir(join(root, "problems", "Prob-001", "infrastructure", "cohorts"), { recursive: true });

  const watches = [];
  let changes = 0;
  const watcher = await watchProblemFiles({
    rootDir: root,
    onChange: () => { changes += 1; },
    watchFn(path, options, callback) {
      watches.push({ path, options, callback });
      return { close() {} };
    },
  });
  t.after(() => watcher.close());

  assert.ok(watches.some((item) => item.path === join(root, "problems", "Prob-001")));
  assert.ok(watches.some((item) => item.path === join(root, "problems", "Prob-001", "attempts")));
  assert.ok(watches.some((item) => item.path === join(root, "problems", "Prob-001", "attempts", "ATT-001")));
  assert.ok(watches.some((item) => item.path === join(root, "problems", "Prob-001", "infrastructure", "cohorts")));

  const attemptWatch = watches.find((item) => item.path === join(root, "problems", "Prob-001", "attempts", "ATT-001"));
  attemptWatch.callback("change", "candidate.py");
  attemptWatch.callback("change", "attempt.json");
  assert.equal(changes, 1);
});
```

- [ ] **Step 2: Run watcher tests and verify RED**

Run:

```bash
node --test tests/dev-problem-index.test.mjs
```

Expected: FAIL because only the problem directory is watched and nested attempt changes are ignored.

- [ ] **Step 3: Implement nested research watchers**

In `scripts/dev-problem-index.mjs`, keep `recursive: false` watchers but add helper registration for:

```js
const RESEARCH_INDEX_FILENAMES = new Set([
  "problem.json",
  "problem.md",
  "research.json",
  "import-manifest.json",
]);
const ATTEMPT_INDEX_FILENAMES = new Set(["attempt.json"]);
const COHORT_INDEX_FILENAMES = new Set(["cohort-001-100.json", "cohort-101-200.json"]);
```

For each problem directory, watch:

```text
problems/<id>/
problems/<id>/attempts/
problems/<id>/attempts/<ATT-NNN>/
problems/<id>/infrastructure/cohorts/
```

Trigger `onChange()` for top-level research filenames, attempt `attempt.json`, and cohort manifest changes. Do not trigger for `candidate.py`, `LOG.md`, `REPORT.md`, or `source/` files because the generated index does not read raw artifact content.

- [ ] **Step 4: Run watcher tests and verify GREEN**

Run:

```bash
node --test tests/dev-problem-index.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit watcher support**

```bash
git add tests/dev-problem-index.test.mjs scripts/dev-problem-index.mjs
git commit -m "feat: watch imported research manifests"
```

---

### Task 9: Import the Real AutoQEC Record

**Files:**
- Create: `problems/Prob-001/**`
- Regenerate but do not commit: `.generated/problem-index.json`
- Regenerate but do not commit: `.generated/research-index.json`

**Interfaces:**
- Consumes: Tasks 1 through 8.
- Produces: the self-contained imported problem tree and generated indexes.

- [ ] **Step 1: Verify destination is absent**

Run:

```bash
test ! -e problems/Prob-001
```

Expected: exits 0. If it exits non-zero, stop and inspect the existing tree with:

```bash
find problems/Prob-001 -maxdepth 3 -type f | sort | head -100
```

- [ ] **Step 2: Run the real import**

Run:

```bash
make problem-import-autoqec-css-distance SOURCE=/Users/nzy/AutoQEC
```

Expected: creates `problems/Prob-001` only after all validation succeeds.

- [ ] **Step 3: Verify the imported tree offline**

Run:

```bash
make problem-import-verify ID=Prob-001
```

Expected: PASS and no read of `/Users/nzy/AutoQEC`.

- [ ] **Step 4: Rebuild generated indexes**

Run:

```bash
node scripts/build-problem-index.mjs --reserve-id Prob-000
```

Expected: `.generated/problem-index.json` includes `Prob-001`; `.generated/research-index.json` includes one `Prob-001` record with 200 attempts.

- [ ] **Step 5: Run structural checks**

Run:

```bash
node -e 'const fs=require("fs"); const r=JSON.parse(fs.readFileSync(".generated/research-index.json","utf8")); const rec=r.records.find(x=>x.problemId==="Prob-001"); if(!rec) process.exit(1); if(rec.attempts.length!==200) process.exit(2); if(rec.attempts[0].id!=="ATT-001" || rec.attempts[199].id!=="ATT-200") process.exit(3); if(rec.attempts.find(x=>x.id==="ATT-101").candidate.status!=="not-generated") process.exit(4); console.log("Prob-001 research index OK");'
```

Expected: prints `Prob-001 research index OK`.

- [ ] **Step 6: Verify copied file regularity**

Run:

```bash
find problems/Prob-001 -type l -print
```

Expected: no output.

Run:

```bash
find problems/Prob-001/infrastructure/snapshots -mindepth 1 -maxdepth 1 -type d | wc -l
```

Expected: `6`.

- [ ] **Step 7: Commit imported data**

```bash
git add problems/Prob-001
git commit -m "data: import AutoQEC CSS distance trials"
```

---

### Task 10: Keep Pages Synthetic and Exclude Imported Data

**Files:**
- Modify: `tests/pages-showcase.test.mjs`
- Modify: `scripts/build-pages-showcase.mjs`

**Interfaces:**
- Consumes: imported `problems/Prob-001` from Task 9.
- Produces: Pages build that still snapshots only `Prob-000` routes and excludes imported candidates and infrastructure.

- [ ] **Step 1: Add Pages exclusion tests**

Extend `tests/pages-showcase.test.mjs`:

```js
test("pages showcase excludes imported AutoQEC problem data", async () => {
  const files = await collectFiles(out);
  const artifactPaths = files.map((file) => relative(out, file));

  assert.equal(artifactPaths.some((path) => path.includes("Prob-001")), false);

  for (const file of files.filter((file) => /\.(?:html|json|txt|css|js)$/.test(file))) {
    const text = await readFile(file, "utf8");
    assert.doesNotMatch(text, /AutoQEC CSS-distance autoresearch record/);
    assert.doesNotMatch(text, /candidate\.py/);
    assert.doesNotMatch(text, /b6a0e03c05a653b4e85160a703c0be4eef06b619/);
    assert.doesNotMatch(text, /\/Users\/nzy\/AutoQEC/);
  }
});
```

- [ ] **Step 2: Run Pages tests and verify current behavior**

Run:

```bash
npm run test:pages
```

Expected: PASS if `scripts/build-pages-showcase.mjs` already indexes only `examples/showcase/problems`. If it fails, inspect the failure and keep the fix scoped to the Pages script route list or index command.

- [ ] **Step 3: Keep Pages route list explicit**

Confirm `scripts/build-pages-showcase.mjs` route list remains exactly:

```js
const routes = [
  "/",
  "/problems/Prob-000",
  "/problems/Prob-000/attempts/ATT-001",
  "/problems/Prob-000/attempts/ATT-002",
  "/problems/Prob-000/attempts/ATT-003",
  "/problems/Prob-000/attempts/ATT-004",
  "/problems/Prob-000/attempts/ATT-005",
];
```

If a prior task added dynamic route discovery, replace it with the explicit list above.

- [ ] **Step 4: Commit Pages exclusion coverage**

```bash
git add tests/pages-showcase.test.mjs scripts/build-pages-showcase.mjs
git commit -m "test: keep Pages showcase synthetic"
```

---

### Task 11: Final Verification and Branch Review

**Files:**
- No planned source edits unless a verification failure identifies a task-owned defect.

**Interfaces:**
- Consumes: all previous tasks.
- Produces: a verified branch ready for review or PR.

- [ ] **Step 1: Run focused verification**

Run:

```bash
make problem-import-verify ID=Prob-001
node --test tests/imported-research-schema.test.mjs tests/research-indexer.test.mjs tests/research-presentation.test.mjs tests/autoqec-css-distance-report.test.mjs tests/autoqec-css-distance-importer.test.mjs tests/autoqec-css-distance-verify.test.mjs tests/problem-routes-research.test.mjs
```

Expected: PASS.

- [ ] **Step 2: Run the full build**

Run:

```bash
make build
```

Expected: PASS, with `.generated/problem-index.json` and `.generated/research-index.json` regenerated and the app building successfully.

- [ ] **Step 3: Run the full test suite**

Run:

```bash
make test
```

Expected: PASS. If a failure is unrelated to this branch, record the exact command, failing test, and first relevant error line before deciding whether to fix or report it.

- [ ] **Step 4: Manually inspect key route output in a local build**

Start the test server:

```bash
npm run start:test
```

Open:

```text
http://127.0.0.1:4173/problems/Prob-001
http://127.0.0.1:4173/problems/Prob-001/attempts/ATT-001
http://127.0.0.1:4173/problems/Prob-001/attempts/ATT-101
http://127.0.0.1:4173/problems/Prob-001/attempts/ATT-200
```

Expected: the problem page shows 200 rows; each attempt page opens; `ATT-101` says `Candidate code was not generated`; no page renders imported Markdown as trusted HTML or executes code.

- [ ] **Step 5: Inspect git diff for boundary violations**

Run:

```bash
git diff --stat HEAD~11..HEAD
git diff --check
git status --short
```

Expected: no whitespace errors; working tree is clean except for intentionally uncommitted local artifacts if any. Confirm the diff does not edit `app/page.tsx`, `app/globals.css`, `app/layout.tsx`, `knowledge/`, `drafts/`, `literature/`, or `.openai/hosting.json`.

- [ ] **Step 6: Final commit if verification required fixes**

Only if Step 1 through Step 5 required a task-owned fix:

```bash
git add <fixed files>
git commit -m "fix: stabilize AutoQEC import verification"
```

---

## Self-Review

- Spec coverage: The plan covers the `Prob-001` layout, all 200 attempts, copied source artifacts, missing candidates, two cohorts, six infrastructure snapshots, offline verification, generated indexes, routes, Pages isolation, and trust boundary requirements.
- Red-flag scan: The plan contains no deferred implementation markers and every task has concrete files, interfaces, commands, and expected outcomes.
- Type consistency: The same normalized field names are used across schemas, importer, indexer, repository, presentation, routes, and tests: `problemId`, `attempts`, `sourceCommit`, `sourceInfrastructureCommit`, `candidate.status`, `metrics.timingStatus`, `publicContract`, and `sourceCohort`.
