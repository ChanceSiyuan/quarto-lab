# GitHub Pages Showcase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the existing `QMB-001` static research example as a GitHub Pages showcase at `https://nzy1997.github.io/research-loop/`.

**Architecture:** Keep the vinext/Next app as the source of truth and add a Pages-only snapshot builder. The builder renders known routes from the production worker, strips runtime scripts, rewrites root-relative links to the `/research-loop` Pages base path, copies `dist/client` assets, and writes `out/` for GitHub Actions Pages deployment.

**Tech Stack:** Node 22+, vinext build output, native `node:test`, GitHub Actions Pages workflow using `actions/configure-pages`, `actions/upload-pages-artifact`, and `actions/deploy-pages`.

## Global Constraints

- GitHub Pages target is `https://nzy1997.github.io/research-loop/`.
- Static display only: no algorithm run, agent start, worktree creation, private dataset read, stream, or AutoQEC runtime dependency.
- Keep the existing local/dev vinext app unchanged for normal repository use.
- Publish only the known showcase routes: `/`, `/problems/QMB-001`, and `/problems/QMB-001/attempts/ATT-001` through `ATT-005`.
- GitHub Pages artifact directory is `out/`.
- Pages base path is `/research-loop`.
- Use existing project patterns and no new npm dependencies.
- Do not stage `.superpowers/brainstorm/`.

---

## File Structure

- `scripts/build-pages-showcase.mjs`: Pages snapshot builder.
- `tests/pages-showcase.test.mjs`: verifies `out/` content and base-path rewrites.
- `.github/workflows/pages.yml`: GitHub Pages workflow.
- `package.json`: adds `pages:build` and includes the Pages test in `npm test`.
- `README.md`: documents Pages build and URL.

---

### Task 1: Pages Snapshot Builder

**Files:**
- Create: `tests/pages-showcase.test.mjs`
- Create: `scripts/build-pages-showcase.mjs`
- Modify: `package.json`
- Modify: `README.md`

**Interfaces:**
- Produces CLI: `node scripts/build-pages-showcase.mjs`
- Produces artifact: `out/index.html`, `out/problems/QMB-001/index.html`, attempt `index.html` files, copied client assets, and `out/.nojekyll`.

- [ ] **Step 1: Write failing Pages output test**

Create `tests/pages-showcase.test.mjs`:

```js
import assert from "node:assert/strict";
import { access, readFile, stat } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = fileURLToPath(new URL("../", import.meta.url));
const out = join(root, "out");

async function fileExists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

test("pages showcase writes static route files", async () => {
  for (const routeFile of [
    "index.html",
    "problems/QMB-001/index.html",
    "problems/QMB-001/attempts/ATT-001/index.html",
    "problems/QMB-001/attempts/ATT-002/index.html",
    "problems/QMB-001/attempts/ATT-003/index.html",
    "problems/QMB-001/attempts/ATT-004/index.html",
    "problems/QMB-001/attempts/ATT-005/index.html",
    ".nojekyll",
  ]) {
    assert.equal(await fileExists(join(out, routeFile)), true, `${routeFile} should exist`);
  }
});

test("pages showcase rewrites links for the repository base path", async () => {
  const html = await readFile(join(out, "problems/QMB-001/index.html"), "utf8");
  assert.match(html, /Example data - synthetic results for interface demonstration only\./);
  assert.match(html, /href="\/research-loop\/problems\/QMB-001\/attempts\/ATT-005"/);
  assert.match(html, /href="\/research-loop\/assets\//);
  assert.doesNotMatch(html, /href="\/problems\/QMB-001\/attempts\//);
  assert.doesNotMatch(html, /<script\b/i);
});

test("pages showcase copies client assets", async () => {
  const assets = await stat(join(out, "assets"));
  assert.equal(assets.isDirectory(), true);
});
```

Add the test to `package.json` before `tests/rendered-html.test.mjs` by changing the test script tail to:

```json
"test": "node --test tests/static-example-content.test.mjs tests/example-research.test.mjs tests/problem-schema.test.mjs tests/problem-indexer.test.mjs tests/dev-problem-index.test.mjs tests/problem-repository.test.mjs tests/codex-launch.test.mjs tests/problem-presentation.test.mjs tests/problem-view-state.test.mjs && npm run build && npm run pages:build && node --test tests/pages-showcase.test.mjs tests/rendered-html.test.mjs"
```

Add:

```json
"pages:build": "node scripts/build-pages-showcase.mjs"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `npm run pages:build && node --test tests/pages-showcase.test.mjs`

Expected: FAIL because `scripts/build-pages-showcase.mjs` does not exist.

- [ ] **Step 3: Implement the snapshot builder**

Create `scripts/build-pages-showcase.mjs`:

```js
import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const outDir = join(root, "out");
const clientDir = join(root, "dist/client");
const basePath = process.env.PAGES_BASE_PATH ?? "/research-loop";

const routes = [
  "/",
  "/problems/QMB-001",
  "/problems/QMB-001/attempts/ATT-001",
  "/problems/QMB-001/attempts/ATT-002",
  "/problems/QMB-001/attempts/ATT-003",
  "/problems/QMB-001/attempts/ATT-004",
  "/problems/QMB-001/attempts/ATT-005",
];

function routeToOutputPath(route) {
  const routePath = route === "/" ? "index.html" : `${route.slice(1)}/index.html`;
  return join(outDir, routePath);
}

function rewriteHtml(html) {
  return html
    .replace(/<script\b[\s\S]*?<\/script>/gi, "")
    .replace(/\s+href="\/(assets\/[^"]*)"/g, ` href="${basePath}/$1"`)
    .replace(/\s+src="\/(assets\/[^"]*)"/g, ` src="${basePath}/$1"`)
    .replace(/\s+href="\/problems\/([^"]*)"/g, ` href="${basePath}/problems/$1"`)
    .replace(/\s+href="\/"/g, ` href="${basePath}/"`);
}

async function renderRoute(worker, route) {
  const response = await worker.fetch(
    new Request(`http://localhost${route}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );

  if (response.status !== 200) {
    throw new Error(`Cannot snapshot ${route}: HTTP ${response.status}`);
  }
  return rewriteHtml(await response.text());
}

async function main() {
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });
  await cp(clientDir, outDir, { recursive: true });
  await writeFile(join(outDir, ".nojekyll"), "");

  const workerUrl = pathToFileURL(join(root, "dist/server/index.js"));
  workerUrl.searchParams.set("pages", `${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  for (const route of routes) {
    const outputPath = routeToOutputPath(route);
    await mkdir(dirname(outputPath), { recursive: true });
    await writeFile(outputPath, await renderRoute(worker, route));
    console.log(`pages showcase: wrote ${relative(root, outputPath)}`);
  }
}

await main();
```

- [ ] **Step 4: Update README**

Add a short section under the existing command list:

```markdown
### GitHub Pages showcase

`npm run pages:build` snapshots the static `QMB-001` example into `out/` for
GitHub Pages. The published project URL is
`https://nzy1997.github.io/research-loop/`.
```

- [ ] **Step 5: Verify**

Run:

```bash
npm run build
npm run pages:build
node --test tests/pages-showcase.test.mjs
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add package.json README.md scripts/build-pages-showcase.mjs tests/pages-showcase.test.mjs
git commit -m "feat: add github pages showcase build"
```

---

### Task 2: GitHub Pages Workflow

**Files:**
- Create: `.github/workflows/pages.yml`

**Interfaces:**
- Produces workflow `pages.yml` that builds `out/`, uploads it as a Pages artifact, and deploys to GitHub Pages.

- [ ] **Step 1: Create workflow**

Create `.github/workflows/pages.yml`:

```yaml
name: Deploy GitHub Pages showcase

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: false

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: 24
          cache: npm
      - name: Install dependencies
        run: npm ci
      - name: Build app
        run: npm run build
      - name: Build Pages showcase
        run: npm run pages:build
      - name: Test Pages showcase
        run: node --test tests/pages-showcase.test.mjs
      - name: Upload Pages artifact
        uses: actions/upload-pages-artifact@v4
        with:
          path: out

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Verify local checks**

Run:

```bash
npm test
npm run lint
git status --short
```

Expected: PASS, with only unrelated `.superpowers/brainstorm/` untracked.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/pages.yml
git commit -m "ci: deploy github pages showcase"
```

---

## Self-Review

- Spec coverage: Task 1 covers snapshot generation, base path rewriting, route output, assets, `.nojekyll`, tests, package script, and README. Task 2 covers the official GitHub Pages Actions deployment.
- Placeholder scan: no placeholders or incomplete instructions remain.
- Type consistency: `pages:build`, `out/`, `/research-loop`, and the route list are consistent across tasks and tests.
