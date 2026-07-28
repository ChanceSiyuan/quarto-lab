# Pages-Only Research Example Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Physically separate the synthetic `QMB-001` fixture from the local problem library so ordinary local builds return 404 for it while the GitHub Pages build continues to publish it.

**Architecture:** The generic indexer gains explicit `problemsDir` and `reservedIds` inputs. Local commands index only `problems/` and reserve `QMB-001` for allocation, while the self-contained Pages command indexes only `examples/showcase/problems/`, rebuilds vinext, and snapshots the showcase routes.

**Tech Stack:** Node.js 22+, ESM, Node test runner, vinext/Next.js 16, React 19, GitHub Pages static output.

## Global Constraints

- Local development and ordinary production builds index only `problems/`.
- GitHub Pages indexes only `examples/showcase/problems/`; it must never merge in local workspace problems.
- `QMB-001` is reserved for local ID allocation but absent from local records, summaries, diagnostics, routes, and display.
- Do not use hostname detection, request headers, or runtime visibility checks.
- Preserve the full five-attempt showcase and every synthetic-data disclaimer.
- Use test-first red-green-refactor for every behavior change.

## File Map

- `lib/problems/indexer.mjs`: generic index construction from a caller-selected problem directory plus caller-supplied reserved IDs.
- `scripts/build-problem-index.mjs`: CLI adapter for `--problems-dir` and repeatable `--reserve-id` arguments.
- `scripts/dev-problem-index.mjs`: local dev index invocation; always reserves `QMB-001` while watching only `problems/`.
- `scripts/build-pages-showcase.mjs`: self-contained showcase index, vinext build, and static snapshot orchestration.
- `examples/showcase/problems/QMB-001/**`: all public synthetic problem, generation, attempt, and log fixtures.
- `lib/problems/example-research.mjs`: imports and artifact paths for the relocated showcase fixture.
- `tests/problem-indexer.test.mjs`: selected-root and reserved-ID unit coverage.
- `tests/static-example-content.test.mjs`: physical isolation and showcase-index CLI coverage.
- `tests/example-research.test.mjs`: relocated artifact-path coverage.
- `tests/rendered-html.test.mjs`: ordinary local-build homepage and 404 coverage.
- `tests/pages-showcase.test.mjs`: showcase-only generated index and static artifact coverage.
- `package.json`: local reservation arguments and mode-ordered test command.
- `.github/workflows/pages.yml`: remove the redundant ordinary build before the self-contained Pages build.
- `README.md`: document the separate local and showcase roots.

---

### Task 1: Make problem index sources explicit

**Files:**
- Modify: `tests/problem-indexer.test.mjs`
- Modify: `lib/problems/indexer.mjs`
- Modify: `scripts/build-problem-index.mjs`

**Interfaces:**
- Consumes: existing valid `problem.json` and `problem.md` directory layout.
- Produces: `buildProblemIndex({ rootDir?: string, problemsDir?: string, reservedIds?: string[] }): Promise<ProblemIndex>`; CLI flags `--problems-dir <relative-or-absolute-path>` and repeatable `--reserve-id <QMB-id>`.

- [ ] **Step 1: Add a failing selected-root and reservation test**

Extend the test helper so it can write beneath an explicit problem root, then add:

```js
async function writeProblemAt(root, problemsDir, id, overrides = {}, problemMd = completeProblemMd) {
  const dir = join(root, problemsDir, id);
  await mkdir(join(dir, "generation"), { recursive: true });
  const manifest = {
    schemaVersion: 1,
    id,
    title: `${id} title`,
    summary: `${id} summary`,
    status: "draft",
    gate: { type: "interval-arithmetic", readiness: "specified" },
    provenance: { sourceCount: 3 },
    lastActivity: { summary: "Created", at: "2026-07-27T10:00:00Z" },
    createdAt: "2026-07-27T10:00:00Z",
    updatedAt: "2026-07-27T10:00:00Z",
    ...overrides,
  };
  await writeFile(join(dir, "problem.json"), JSON.stringify(manifest, null, 2));
  await writeFile(join(dir, "problem.md"), problemMd);
}

test("indexes only the selected problem root and honors reserved IDs", async () => {
  const root = await makeRoot();
  await writeProblemAt(root, "problems", "QMB-002");
  await writeProblemAt(root, "examples/showcase/problems", "QMB-001");

  const index = await buildProblemIndex({
    rootDir: root,
    problemsDir: "examples/showcase/problems",
    reservedIds: ["QMB-009"],
  });

  assert.deepEqual(index.problems.map((problem) => problem.id), ["QMB-001"]);
  assert.equal(index.nextProblemId, "QMB-010");
  assert.deepEqual(index.diagnostics, []);
});
```

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```bash
node --test --test-name-pattern="selected problem root" tests/problem-indexer.test.mjs
```

Expected: FAIL because `buildProblemIndex` still always reads `problems/` and ignores `reservedIds`.

- [ ] **Step 3: Implement generic selected-root and reserved-ID inputs**

Change the indexer entry point and initialization to:

```js
export async function buildProblemIndex({
  rootDir = process.cwd(),
  problemsDir = "problems",
  reservedIds: initialReservedIds = [],
} = {}) {
  const workspacePath = resolve(rootDir);
  const problemsPath = resolve(workspacePath, problemsDir);
  const diagnostics = [];
  const problems = [];
  const seenIds = new Set();
  const reservedIds = new Set(initialReservedIds);
```

Keep the existing directory validation, sorting, summary calculation, and relative diagnostic paths unchanged.

- [ ] **Step 4: Add CLI parsing for the new inputs**

In `scripts/build-problem-index.mjs`, add:

```js
function readArgs(name) {
  return process.argv.flatMap((value, index) => (
    value === name && process.argv[index + 1] ? [process.argv[index + 1]] : []
  ));
}

const problemsDir = readArg("--problems-dir", "problems");
const reservedIds = readArgs("--reserve-id");
const index = await buildProblemIndex({ rootDir, problemsDir, reservedIds });
```

Replace the existing `buildProblemIndex({ rootDir })` call rather than adding a second call.

- [ ] **Step 5: Run indexer tests and verify GREEN**

Run:

```bash
node --test tests/problem-indexer.test.mjs
```

Expected: all tests PASS, including the new selected-root test.

- [ ] **Step 6: Commit the index interface**

```bash
git add tests/problem-indexer.test.mjs lib/problems/indexer.mjs scripts/build-problem-index.mjs
git commit -m "feat: select problem index source"
```

---

### Task 2: Relocate the synthetic showcase fixture

**Files:**
- Move: `problems/QMB-001/**` to `examples/showcase/problems/QMB-001/**`
- Modify: `tests/static-example-content.test.mjs`
- Modify: `tests/example-research.test.mjs`
- Modify: `lib/problems/example-research.mjs`

**Interfaces:**
- Consumes: Task 1 CLI `--problems-dir examples/showcase/problems`.
- Produces: fixture root `examples/showcase/problems/QMB-001`; `getStaticResearchArtifactPath()` values rooted at `examples/showcase/problems/`.

- [ ] **Step 1: Change tests to require physical isolation**

Update the static content test to run the index command against the showcase root:

```js
await execFileAsync(
  process.execPath,
  [
    "scripts/build-problem-index.mjs",
    "--root", workspaceRoot,
    "--problems-dir", "examples/showcase/problems",
    "--out", outPath,
  ],
  { cwd: workspaceRoot, maxBuffer: 10 * 1024 * 1024 },
);
```

Update fixture reads to `../examples/showcase/problems/QMB-001/...` and add:

```js
await assert.rejects(
  readFile(new URL("../problems/QMB-001/problem.json", import.meta.url), "utf8"),
  { code: "ENOENT" },
);
```

Change the artifact path expectations in `tests/example-research.test.mjs` to:

```js
assert.equal(
  getStaticResearchArtifactPath("QMB-001", "ATT-003", "LOG.md"),
  "examples/showcase/problems/QMB-001/attempts/ATT-003/LOG.md",
);
assert.deepEqual(dossier.artifacts, [
  "examples/showcase/problems/QMB-001/attempts/ATT-004/attempt.json",
  "examples/showcase/problems/QMB-001/attempts/ATT-004/LOG.md",
]);
```

- [ ] **Step 2: Run focused tests and verify RED**

Run:

```bash
node --test tests/static-example-content.test.mjs tests/example-research.test.mjs
```

Expected: FAIL because the fixture still lives under `problems/QMB-001` and helper paths still point there.

- [ ] **Step 3: Move every fixture file without changing its content**

Use `apply_patch` moves for these sixteen files, preserving their contents exactly:

```text
problem.json
problem.md
example.json
generation/initial-prompt.md
generation/transcript.md
generation/decision.md
attempts/ATT-001/attempt.json
attempts/ATT-001/LOG.md
attempts/ATT-002/attempt.json
attempts/ATT-002/LOG.md
attempts/ATT-003/attempt.json
attempts/ATT-003/LOG.md
attempts/ATT-004/attempt.json
attempts/ATT-004/LOG.md
attempts/ATT-005/attempt.json
attempts/ATT-005/LOG.md
```

Each destination is the same relative suffix beneath `examples/showcase/problems/QMB-001/`.

- [ ] **Step 4: Update imports and displayed artifact paths**

Change all six JSON imports at the top of `lib/problems/example-research.mjs` from `../../problems/QMB-001/...` to `../../examples/showcase/problems/QMB-001/...`.

Change the artifact helper to:

```js
export function getStaticResearchArtifactPath(problemId, attemptId, artifact) {
  return `examples/showcase/problems/${problemId}/attempts/${attemptId}/${artifact}`;
}
```

- [ ] **Step 5: Run focused tests and verify GREEN**

Run:

```bash
node --test tests/static-example-content.test.mjs tests/example-research.test.mjs
```

Expected: all tests PASS.

- [ ] **Step 6: Commit the physical separation**

```bash
git add problems/QMB-001 examples/showcase/problems/QMB-001 lib/problems/example-research.mjs tests/static-example-content.test.mjs tests/example-research.test.mjs
git commit -m "refactor: isolate pages showcase fixture"
```

---

### Task 3: Disable the example in every ordinary local build

**Files:**
- Modify: `tests/rendered-html.test.mjs`
- Modify: `scripts/dev-problem-index.mjs`
- Modify: `package.json`

**Interfaces:**
- Consumes: Task 1 repeatable `--reserve-id` CLI flag and Task 2 removal of `QMB-001` from `problems/`.
- Produces: ordinary generated index with `problems: []` for the current repository, `nextProblemId: "QMB-002"`, and no example routes.

- [ ] **Step 1: Replace local example rendering expectations with disabled-state assertions**

In the homepage test, replace the example title/link assertions with:

```js
assert.doesNotMatch(html, /CSS code-distance algorithm search/);
assert.doesNotMatch(html, /href="\/problems\/QMB-001"/);
assert.match(html, />\+ Add first problem<\/a>/);
```

Add a generated-index assertion:

```js
test("ordinary local build excludes and reserves the showcase problem", () => {
  assert.deepEqual(generatedIndex.problems.map((problem) => problem.id), []);
  assert.equal(generatedIndex.nextProblemId, "QMB-002");
  assert.deepEqual(generatedIndex.summary, {
    total: 0,
    accepted: 0,
    solved: 0,
    published: 0,
    rejected: 0,
    archived: 0,
  });
});
```

Replace the ledger, dossier, and unknown-example-attempt rendering tests with one route matrix:

```js
test("ordinary local build returns 404 for every showcase route", async () => {
  for (const pathname of [
    "/problems/QMB-001",
    "/problems/QMB-001/attempts/ATT-001",
    "/problems/QMB-001/attempts/ATT-005",
    "/problems/QMB-001/attempts/ATT-999",
  ]) {
    const response = await render(pathname);
    assert.equal(response.status, 404, pathname);
  }
});
```

- [ ] **Step 2: Build and verify RED**

Run:

```bash
npm run build
node --test tests/rendered-html.test.mjs
```

Expected: the route and homepage checks pass because the fixture moved, but the reservation test FAILS with `nextProblemId` equal to `QMB-001`.

- [ ] **Step 3: Reserve the example ID in local commands**

Change the local build and lint commands in `package.json` to invoke:

```json
"build": "node scripts/build-problem-index.mjs --reserve-id QMB-001 && WRANGLER_LOG_PATH=.wrangler/wrangler.log vinext build",
"lint": "node scripts/build-problem-index.mjs --reserve-id QMB-001 && eslint . --ignore-pattern dist --ignore-pattern .next --ignore-pattern .generated"
```

Change the dev builder spawn arguments to:

```js
const builder = spawn(
  process.execPath,
  ["scripts/build-problem-index.mjs", "--reserve-id", "QMB-001"],
  { cwd: rootDir, stdio: "inherit" },
);
```

Do not change `watchProblemFiles`; it already watches only `problems/`.

- [ ] **Step 4: Rebuild and verify GREEN**

Run:

```bash
npm run build
node --test tests/rendered-html.test.mjs
node --test tests/dev-problem-index.test.mjs
```

Expected: all tests PASS; the generated local index is empty, `QMB-001` routes return 404, and `nextProblemId` is `QMB-002`.

- [ ] **Step 5: Commit local disabling**

```bash
git add tests/rendered-html.test.mjs scripts/dev-problem-index.mjs package.json
git commit -m "fix: disable showcase example locally"
```

---

### Task 4: Make the Pages build showcase-only and self-contained

**Files:**
- Modify: `tests/pages-showcase.test.mjs`
- Modify: `scripts/build-pages-showcase.mjs`
- Modify: `package.json`
- Modify: `.github/workflows/pages.yml`
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 1 `--problems-dir` CLI and Task 2 `examples/showcase/problems/QMB-001` fixture.
- Produces: `npm run pages:build`, which creates a showcase-only `.generated/problem-index.json`, rebuilds `dist/`, and emits `out/`.

- [ ] **Step 1: Add a failing showcase-only index assertion**

At the top of `tests/pages-showcase.test.mjs`, add:

```js
const generatedIndex = JSON.parse(
  await readFile(join(root, ".generated/problem-index.json"), "utf8"),
);

test("pages build indexes only the public showcase root", () => {
  assert.deepEqual(generatedIndex.problems.map((problem) => problem.id), ["QMB-001"]);
  assert.equal(generatedIndex.summary.total, 1);
  assert.equal(generatedIndex.problems[0].title, "CSS code-distance algorithm search");
});
```

- [ ] **Step 2: Run from an ordinary local build and verify RED**

Run:

```bash
npm run build
node scripts/build-pages-showcase.mjs
```

Expected: FAIL while snapshotting `/problems/QMB-001` with HTTP 404 because the script currently reuses the ordinary local `dist/` build.

- [ ] **Step 3: Add self-contained Pages application build orchestration**

In `scripts/build-pages-showcase.mjs`, import child-process helpers:

```js
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const vinextBin = fileURLToPath(new URL("../node_modules/.bin/vinext", import.meta.url));
```

Add and call this before deleting or writing `out/`:

```js
async function buildShowcaseApp() {
  await execFileAsync(
    process.execPath,
    [
      "scripts/build-problem-index.mjs",
      "--problems-dir", "examples/showcase/problems",
    ],
    { cwd: root, maxBuffer: 10 * 1024 * 1024 },
  );
  await execFileAsync(vinextBin, ["build"], {
    cwd: root,
    env: { ...process.env, WRANGLER_LOG_PATH: ".wrangler/wrangler.log" },
    maxBuffer: 10 * 1024 * 1024,
  });
}

async function main() {
  await buildShowcaseApp();
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });
  await copyStaticClientAssets();
  await writeFile(join(outDir, ".nojekyll"), "");
}
```

Keep the existing worker import and route snapshot loop immediately after these
initialization lines.

Keep `pages:build` as `node scripts/build-pages-showcase.mjs`; it is now self-contained.

- [ ] **Step 4: Order the full test command by deployment mode**

Change `package.json` so the test script runs:

```json
"test": "node --test tests/static-example-content.test.mjs tests/example-research.test.mjs tests/problem-schema.test.mjs tests/problem-indexer.test.mjs tests/dev-problem-index.test.mjs tests/problem-repository.test.mjs tests/codex-launch.test.mjs tests/problem-presentation.test.mjs tests/problem-view-state.test.mjs && npm run build && node --test tests/rendered-html.test.mjs && npm run pages:build && node --test tests/pages-showcase.test.mjs"
```

This must verify the local worker before the Pages command replaces `.generated/problem-index.json` and `dist/` with the showcase variant.

- [ ] **Step 5: Update CI and README**

Remove the redundant `Build app` step from `.github/workflows/pages.yml`; `npm run pages:build` now owns both index and vinext builds.

Add to the README's local console section:

```markdown
Only `problems/` is indexed by local development and ordinary production
builds. The synthetic public example lives separately under
`examples/showcase/problems/` and is not available from local routes.
```

Replace the Pages command description with:

```markdown
- `npm run pages:build`: build only the synthetic fixtures under
  `examples/showcase/problems/` and snapshot them into `out/` for GitHub Pages
  at `https://nzy1997.github.io/research-loop/`
```

- [ ] **Step 6: Run Pages tests and verify GREEN**

Run:

```bash
npm run pages:build
node --test tests/pages-showcase.test.mjs
```

Expected: all tests PASS; `.generated/problem-index.json` contains exactly `QMB-001`, and all seven showcase route files exist.

- [ ] **Step 7: Run complete verification**

Run:

```bash
npm test
npm run lint
git diff --check
```

Expected: all commands exit 0 with no test, lint, or whitespace errors.

- [ ] **Step 8: Commit Pages orchestration and documentation**

```bash
git add tests/pages-showcase.test.mjs scripts/build-pages-showcase.mjs package.json .github/workflows/pages.yml README.md
git commit -m "build: isolate pages showcase data"
```

---

## Final Verification Matrix

| Mode | Indexed root | `QMB-001` homepage entry | `QMB-001` routes | Next local ID |
|---|---|---:|---:|---:|
| `npm run dev` | `problems/` | absent | 404 | `QMB-002` when no real problems exist |
| `npm run build` + `npm start` | `problems/` | absent | 404 | `QMB-002` when no real problems exist |
| `npm run pages:build` | `examples/showcase/problems/` | present | static 200 pages | not used for local allocation |
