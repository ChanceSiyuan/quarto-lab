# Public Problem Examples on GitHub Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `Prob-124` through `Prob-128` as static GitHub Pages examples without exposing any other official problem data.

**Architecture:** A focused staging module assembles an allowlisted public problem root under `.generated/` from the existing `Prob-000` fixture plus the two display files for each approved official record. The Pages builder consumes that root and derives static detail routes from the same allowlist, while the existing artifact tests enforce base-path rewriting and the absence of local-only material.

**Tech Stack:** Node.js ESM, `node:fs/promises`, Node's built-in test runner, vinext, GitHub Pages Actions.

## Global Constraints

- Preserve `app/page.tsx`, `app/globals.css`, and `app/layout.tsx` unchanged.
- Preserve `.openai/hosting.json` and its project ID unchanged.
- Publish exactly `Prob-000`, `Prob-124`, `Prob-125`, `Prob-126`, `Prob-127`, and `Prob-128` in the Pages problem index.
- Copy only `problem.json` and `problem.md` from each official allowlisted problem.
- Do not copy generation records, assessments, valuations, attempts, infrastructure, private files, or future problem IDs.
- Add detail routes only for `Prob-124` through `Prob-128`; keep the existing `Prob-000` showcase routes unchanged.
- Keep the existing GitHub Pages workflow and visual design unchanged.
- Add no dependencies.
- Treat a missing allowlisted source file as a build-stopping error naming the missing ID and file.

---

### Task 1: Build the public Pages problem staging boundary

**Files:**
- Create: `.research-loop/tooling/scripts/pages-showcase-problems.mjs`
- Create: `.research-loop/tests/pages-showcase-problems.test.mjs`

**Interfaces:**
- Produces: `PAGES_PUBLIC_PROBLEM_IDS`, an immutable ordered list containing `Prob-124` through `Prob-128`.
- Produces: `createPagesShowcaseRoutes()`, returning the complete ordered static route list.
- Produces: `stagePagesShowcaseProblems(options)`, returning `{ problemsDir, problemIds }` after assembling the public root.
- Consumes: real filesystem directories supplied through `fixtureProblemsDir`, `officialProblemsDir`, and `stageProblemsDir` options.

- [ ] **Step 1: Write the failing staging and route tests**

Create `.research-loop/tests/pages-showcase-problems.test.mjs` with real temporary directories. Catch the first missing-module import only so the failure is an assertion about the absent production interface:

```js
import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const stagingModule = await import("../tooling/scripts/pages-showcase-problems.mjs").catch(() => ({}));
const {
  PAGES_PUBLIC_PROBLEM_IDS,
  createPagesShowcaseRoutes,
  stagePagesShowcaseProblems,
} = stagingModule;

const OFFICIAL_IDS = ["Prob-124", "Prob-125", "Prob-126", "Prob-127", "Prob-128"];

async function writeDisplayFiles(root, id) {
  const dir = join(root, id);
  await mkdir(join(dir, "generation"), { recursive: true });
  await writeFile(join(dir, "problem.json"), `${JSON.stringify({ id })}\n`);
  await writeFile(join(dir, "problem.md"), `# ${id}\n`);
  await writeFile(join(dir, "generation", "private.json"), "do not copy\n");
}

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), "pages-showcase-problems-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const fixtureProblemsDir = join(root, "fixture");
  const officialProblemsDir = join(root, "official");
  const stageProblemsDir = join(root, "stage");
  await writeDisplayFiles(fixtureProblemsDir, "Prob-000");
  for (const id of OFFICIAL_IDS) await writeDisplayFiles(officialProblemsDir, id);
  return { fixtureProblemsDir, officialProblemsDir, stageProblemsDir };
}

test("declares the five official public problem IDs and derives their detail routes", () => {
  assert.equal(typeof createPagesShowcaseRoutes, "function");
  assert.deepEqual(PAGES_PUBLIC_PROBLEM_IDS, OFFICIAL_IDS);
  assert.deepEqual(createPagesShowcaseRoutes(), [
    "/",
    "/problems/Prob-000",
    "/problems/Prob-124",
    "/problems/Prob-125",
    "/problems/Prob-126",
    "/problems/Prob-127",
    "/problems/Prob-128",
    "/problems/Prob-000/autoresearch",
    "/problems/Prob-000/attempts/ATT-001",
    "/problems/Prob-000/attempts/ATT-002",
    "/problems/Prob-000/attempts/ATT-003",
    "/problems/Prob-000/attempts/ATT-004",
    "/problems/Prob-000/attempts/ATT-005",
  ]);
});

test("stages only display files for the five allowlisted official problems", async (t) => {
  assert.equal(typeof stagePagesShowcaseProblems, "function");
  const paths = await fixture(t);
  const result = await stagePagesShowcaseProblems(paths);
  assert.deepEqual(result.problemIds, ["Prob-000", ...OFFICIAL_IDS]);
  assert.deepEqual((await readdir(result.problemsDir)).sort(), ["Prob-000", ...OFFICIAL_IDS].sort());
  for (const id of OFFICIAL_IDS) {
    assert.deepEqual((await readdir(join(result.problemsDir, id))).sort(), ["problem.json", "problem.md"]);
    assert.equal(await readFile(join(result.problemsDir, id, "problem.md"), "utf8"), `# ${id}\n`);
  }
});

test("fails with the allowlisted ID and file when a public display source is missing", async (t) => {
  const paths = await fixture(t);
  await rm(join(paths.officialProblemsDir, "Prob-127", "problem.md"));
  await assert.rejects(
    stagePagesShowcaseProblems(paths),
    /Pages showcase source missing: problems\/Prob-127\/problem\.md/,
  );
});
```

- [ ] **Step 2: Run the test and verify RED**

Run:

```bash
node --test .research-loop/tests/pages-showcase-problems.test.mjs
```

Expected: FAIL at `declares the five official public problem IDs and derives their detail routes` because `createPagesShowcaseRoutes` is `undefined`.

- [ ] **Step 3: Implement the minimal staging module**

Create `.research-loop/tooling/scripts/pages-showcase-problems.mjs`:

```js
import { cp, mkdir, rm } from "node:fs/promises";
import { dirname, join } from "node:path";

export const PAGES_PUBLIC_PROBLEM_IDS = Object.freeze([
  "Prob-124",
  "Prob-125",
  "Prob-126",
  "Prob-127",
  "Prob-128",
]);

const DISPLAY_FILES = Object.freeze(["problem.json", "problem.md"]);

export function createPagesShowcaseRoutes() {
  return [
    "/",
    "/problems/Prob-000",
    ...PAGES_PUBLIC_PROBLEM_IDS.map((id) => `/problems/${id}`),
    "/problems/Prob-000/autoresearch",
    "/problems/Prob-000/attempts/ATT-001",
    "/problems/Prob-000/attempts/ATT-002",
    "/problems/Prob-000/attempts/ATT-003",
    "/problems/Prob-000/attempts/ATT-004",
    "/problems/Prob-000/attempts/ATT-005",
  ];
}

export async function stagePagesShowcaseProblems({
  fixtureProblemsDir,
  officialProblemsDir,
  stageProblemsDir,
}) {
  await rm(stageProblemsDir, { recursive: true, force: true });
  await mkdir(dirname(stageProblemsDir), { recursive: true });
  await cp(
    join(fixtureProblemsDir, "Prob-000"),
    join(stageProblemsDir, "Prob-000"),
    { recursive: true },
  );

  for (const id of PAGES_PUBLIC_PROBLEM_IDS) {
    const targetDir = join(stageProblemsDir, id);
    await mkdir(targetDir, { recursive: true });
    for (const file of DISPLAY_FILES) {
      try {
        await cp(join(officialProblemsDir, id, file), join(targetDir, file));
      } catch (error) {
        if (error.code === "ENOENT") {
          throw new Error(`Pages showcase source missing: problems/${id}/${file}`);
        }
        throw error;
      }
    }
  }

  return {
    problemsDir: stageProblemsDir,
    problemIds: ["Prob-000", ...PAGES_PUBLIC_PROBLEM_IDS],
  };
}
```

- [ ] **Step 4: Run the focused test and verify GREEN**

Run:

```bash
node --test .research-loop/tests/pages-showcase-problems.test.mjs
```

Expected: 3 tests pass, 0 fail.

- [ ] **Step 5: Commit the staging boundary**

```bash
git add .research-loop/tooling/scripts/pages-showcase-problems.mjs .research-loop/tests/pages-showcase-problems.test.mjs
git commit -m "feat: stage public Pages problem examples"
```

---

### Task 2: Wire the allowlisted data and routes into the Pages builder

**Files:**
- Modify: `.research-loop/tooling/scripts/build-pages-showcase.mjs:1-27,165-184`
- Modify: `.research-loop/tests/pages-showcase.test.mjs:36-59,188-210`

**Interfaces:**
- Consumes: `createPagesShowcaseRoutes()` and `stagePagesShowcaseProblems(options)` from Task 1.
- Produces: `.generated/problem-index.json` containing exactly six public records.
- Produces: static detail artifacts at `out/problems/Prob-124/index.html` through `out/problems/Prob-128/index.html`.

- [ ] **Step 1: Write the failing Pages artifact expectations**

In `.research-loop/tests/pages-showcase.test.mjs`, replace the single-record index expectation with the hand-derived IDs:

```js
const PUBLIC_PROBLEM_IDS = [
  "Prob-000",
  "Prob-124",
  "Prob-125",
  "Prob-126",
  "Prob-127",
  "Prob-128",
];

test("pages build indexes only the approved public problem records", () => {
  assert.deepEqual(generatedIndex.problems.map((problem) => problem.id).sort(), PUBLIC_PROBLEM_IDS);
  assert.equal(generatedIndex.summary.total, 6);
});
```

Add these five files to the existing static route list:

```js
"problems/Prob-124/index.html",
"problems/Prob-125/index.html",
"problems/Prob-126/index.html",
"problems/Prob-127/index.html",
"problems/Prob-128/index.html",
```

Replace `pages showcase copies only the Prob-000 problem source` with:

```js
test("pages showcase exposes exactly the approved public problem routes", async () => {
  assert.deepEqual(generatedIndex.problems.map((problem) => problem.id).sort(), PUBLIC_PROBLEM_IDS);
  const problemEntries = await readdir(join(out, "problems"), { withFileTypes: true });
  assert.deepEqual(
    problemEntries.filter((entry) => entry.isDirectory()).map((entry) => entry.name).sort(),
    PUBLIC_PROBLEM_IDS,
  );
});
```

Add a detail-page assertion that checks every new page and its base-path return link:

```js
test("pages showcase renders the five official public problem details", async () => {
  for (const id of PUBLIC_PROBLEM_IDS.slice(1)) {
    const html = await readFile(join(out, "problems", id, "index.html"), "utf8");
    assert.match(html, new RegExp(`<p class="eyebrow">${id}</p>`));
    assert.match(html, /href="\/research-loop\/"/);
    assert.doesNotMatch(html, /<script\b/i);
    assert.doesNotMatch(html, /codex:\/\//i);
    assert.doesNotMatch(html, /\/__local\//);
  }
});
```

- [ ] **Step 2: Verify the existing artifact does not satisfy the new contract**

Run the focused unit test from Task 1 again and inspect the pre-change generated index:

```bash
node --test .research-loop/tests/pages-showcase-problems.test.mjs
node -e 'const i=require("./.generated/problem-index.json"); console.log(i.problems.map(p=>p.id))'
```

Expected: the focused unit test passes, while the existing generated index prints only `[ 'Prob-000' ]`; the new integration assertions therefore require a builder change.

- [ ] **Step 3: Integrate the staging module into the builder**

In `.research-loop/tooling/scripts/build-pages-showcase.mjs`, import the staging interfaces and replace the hard-coded route array:

```js
import {
  createPagesShowcaseRoutes,
  stagePagesShowcaseProblems,
} from "./pages-showcase-problems.mjs";

const routes = createPagesShowcaseRoutes();
```

At the start of `buildShowcaseApp()`, stage the public root and pass its repository-relative path to the existing index command:

```js
const { problemsDir } = await stagePagesShowcaseProblems({
  fixtureProblemsDir: join(root, ".research-loop/fixtures/showcase/problems"),
  officialProblemsDir: join(root, "problems"),
  stageProblemsDir: join(root, ".generated/pages-showcase/problems"),
});

await execFileAsync(
  process.execPath,
  [
    ".research-loop/tooling/scripts/build-problem-index.mjs",
    "--public",
    "--problems-dir", relative(root, problemsDir),
  ],
  { cwd: root, maxBuffer: 10 * 1024 * 1024 },
);
```

Do not alter the HTML rewrite rules, visual components, or GitHub workflow.

- [ ] **Step 4: Verify the public staging root and application build**

Run:

```bash
node --input-type=module -e 'import {stagePagesShowcaseProblems} from "./.research-loop/tooling/scripts/pages-showcase-problems.mjs"; await stagePagesShowcaseProblems({fixtureProblemsDir:".research-loop/fixtures/showcase/problems",officialProblemsDir:"problems",stageProblemsDir:".generated/pages-showcase/problems"})'
node .research-loop/tooling/scripts/build-problem-index.mjs --public --problems-dir .generated/pages-showcase/problems
npm run build:app
```

Expected: the index command succeeds with six records and `build:app` exits 0.

- [ ] **Step 5: Run the complete Pages test when Quarto is available**

Run:

```bash
npm run test:pages
```

Expected with Quarto installed: the Pages build writes the five new detail routes and every Pages test passes. If local Quarto remains unavailable, record the `spawn quarto ENOENT` limitation and require the GitHub Pages workflow to pass before merge.

- [ ] **Step 6: Commit the builder and artifact contract**

```bash
git add .research-loop/tooling/scripts/build-pages-showcase.mjs .research-loop/tests/pages-showcase.test.mjs
git commit -m "feat: publish public problem examples on Pages"
```

---

### Task 3: Final privacy and regression verification

**Files:**
- Verify only; no planned production file changes.

**Interfaces:**
- Consumes: the staging module, Pages builder, and test contracts from Tasks 1 and 2.
- Produces: evidence that the feature diff is limited to the approved Pages surface and contains no generated artifact.

- [ ] **Step 1: Run focused tests and validation**

```bash
node --test .research-loop/tests/pages-showcase-problems.test.mjs
node --test .research-loop/tests/problem-schema.test.mjs .research-loop/tests/problem-indexer.test.mjs
git diff --check origin/main...HEAD
```

Expected: all focused tests pass and `git diff --check` prints nothing.

- [ ] **Step 2: Inspect the public staging root**

```bash
find .generated/pages-showcase/problems -maxdepth 3 -type f -print | sort
```

Expected: `Prob-000` retains its fixture files; each of `Prob-124` through `Prob-128` contains exactly `problem.json` and `problem.md`.

- [ ] **Step 3: Inspect the feature diff and repository status**

```bash
git diff --stat origin/main...HEAD
git diff origin/main...HEAD -- .research-loop/tooling/scripts/pages-showcase-problems.mjs .research-loop/tooling/scripts/build-pages-showcase.mjs .research-loop/tests/pages-showcase-problems.test.mjs .research-loop/tests/pages-showcase.test.mjs
git status --short
```

Expected: no `out/`, `.generated/`, `public/knowledge/`, dependency, hosting configuration, or preserved dashboard source appears in the commit diff; the worktree is clean.

- [ ] **Step 4: Require hosted deployment verification**

After the branch is pushed and merged, require the existing `Deploy GitHub Pages showcase` workflow to pass. Then verify these URLs return HTTP 200:

```text
https://nzy1997.github.io/research-loop/problems/Prob-124/
https://nzy1997.github.io/research-loop/problems/Prob-125/
https://nzy1997.github.io/research-loop/problems/Prob-126/
https://nzy1997.github.io/research-loop/problems/Prob-127/
https://nzy1997.github.io/research-loop/problems/Prob-128/
```
