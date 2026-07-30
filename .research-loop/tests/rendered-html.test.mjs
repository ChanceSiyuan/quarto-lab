import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

const execFileAsync = promisify(execFile);
const workspaceRoot = fileURLToPath(new URL("../../", import.meta.url));
const generatedIndexUrl = new URL("../../.generated/problem-index.json", import.meta.url);
const generatedIndex = JSON.parse(
  await readFile(generatedIndexUrl, "utf8"),
);
const fixedPublicationTargetPattern = new RegExp(["publication", "target"].join("\\s+"), "i");

const completeProblemMd = [
  "Background and Gap",
  "Research Objective",
  "Publication Threshold",
  "Executable Gate",
  "Novelty Evidence",
  "Provenance",
  "Fresh Evaluation Plan",
].map((heading) => `## ${heading}\nConcrete fixture content.`).join("\n\n");

async function render(pathname = "/") {
  const workerUrl = new URL("../../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${pathname}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
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
}

async function buildCurrentIndex(env = {}) {
  await execFileAsync(
    fileURLToPath(new URL("../../node_modules/.bin/vinext", import.meta.url)),
    ["build"],
    {
      cwd: workspaceRoot,
      env: { ...process.env, ...env, WRANGLER_LOG_PATH: ".wrangler/wrangler.log" },
      maxBuffer: 10 * 1024 * 1024,
    },
  );
}

async function writeFixtureProblem(root, manifest) {
  const problemDir = join(root, "problems", manifest.id);
  await mkdir(join(problemDir, "generation"), { recursive: true });
  await writeFile(join(problemDir, "problem.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  await writeFile(join(problemDir, "problem.md"), completeProblemMd);
  await writeFile(join(problemDir, "generation", "initial-prompt.md"), "Fixture prompt.");
  await writeFile(join(problemDir, "generation", "transcript.md"), "Fixture transcript.");
  await writeFile(join(problemDir, "generation", "decision.md"), "Fixture decision.");
}

async function renderFilesystemFixture({ manifests, damagedIds = [], buildEnv = {} }, pathname = "/?fixture=filesystem") {
  const originalIndexText = await readFile(generatedIndexUrl, "utf8");
  const fixtureRoot = await mkdtemp(join(tmpdir(), "research-loop-render-"));
  await mkdir(join(fixtureRoot, "problems"), { recursive: true });
  for (const manifest of manifests) {
    await writeFixtureProblem(fixtureRoot, manifest);
  }
  for (const id of damagedIds) {
    const damagedDir = join(fixtureRoot, "problems", id);
    await mkdir(damagedDir, { recursive: true });
    await writeFile(join(damagedDir, "problem.json"), "{ broken json");
  }

  try {
    await execFileAsync(
      process.execPath,
      [
        ".research-loop/tooling/scripts/build-problem-index.mjs",
        "--root",
        fixtureRoot,
        "--out",
        fileURLToPath(generatedIndexUrl),
      ],
      {
        cwd: workspaceRoot,
        maxBuffer: 10 * 1024 * 1024,
      },
    );
    await buildCurrentIndex(buildEnv);
    const response = await render(pathname);
    const html = await response.text();
    return new Response(html, { status: response.status, headers: response.headers });
  } finally {
    await writeFile(generatedIndexUrl, originalIndexText);
    await buildCurrentIndex();
    await rm(fixtureRoot, { recursive: true, force: true });
  }
}

const acceptedFixture = {
  schemaVersion: 1,
  id: "Prob-017",
  title: "Fresh Hamiltonian gate",
  summary: "Interval arithmetic on held-out instances.",
  status: "accepted",
  gate: { type: "interval-arithmetic", readiness: "executable" },
  provenance: { sourceCount: 12 },
  lastActivity: {
    summary: "Accepted after novelty review",
    at: "2026-07-27T10:30:00.000Z",
  },
  createdAt: "2026-07-27T09:00:00.000Z",
  updatedAt: "2026-07-27T11:45:00.000Z",
};

test("server-renders the problem console shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Research Loop/);
  assert.match(html, /Problem Console/);
  assert.match(html, /<a class="topbar-link" href="\/knowledge\/">Knowledge <span aria-hidden="true">→<\/span><\/a>/);
  assert.match(html, />\+ Add problem<\/a>/);
  assert.match(html, /AutoQEC CSS Distance Campaign/);
  assert.match(html, /href="\/problems\/Prob-001"/);
  assert.doesNotMatch(html, />\+ Add first problem<\/a>/);
  assert.match(html, /Cannot open Codex\?/);
  assert.match(html, /codex:\/\/threads\/new/);
  assert.match(html, /<span class="status-badge status-draft">Draft<\/span>/);
  assert.match(html, /<span class="status-badge status-solved">Solved<\/span>/);
  assert.doesNotMatch(html, /metric-strip/);
  assert.doesNotMatch(html, /console-toolbar/);
  assert.doesNotMatch(html, /Index diagnostics/);
  assert.doesNotMatch(html, fixedPublicationTargetPattern);
  assert.doesNotMatch(html, /\/\s*5\b/);
  assert.doesNotMatch(html, /[\u3400-\u9FFF]/u);
  assert.match(
    html,
    /<th scope="col">Problem<\/th><th scope="col">Status<\/th><th scope="col">Executable gate<\/th><th scope="col">Provenance<\/th><th scope="col">Recent activity<\/th><th scope="col">Updated<\/th><th scope="col">Open<\/th>/,
  );
  assert.doesNotMatch(html, /Turn open literature into/);
  assert.doesNotMatch(html, /Reset demo/);
  assert.doesNotMatch(html, /localStorage/);
});

test("ordinary local build indexes all tracked QEC problems and reserves the next problem ID", () => {
  assert.deepEqual(
    generatedIndex.problems.map((problem) => problem.id).sort(),
    [
      ...Array.from({ length: 21 }, (_, index) => `Prob-${String(index + 1).padStart(3, "0")}`),
      "Prob-124",
      "Prob-125",
      "Prob-126",
      "Prob-127",
      "Prob-128",
    ].sort(),
  );
  assert.equal(generatedIndex.nextProblemId, "Prob-129");
  assert.deepEqual(generatedIndex.diagnostics, []);
  assert.deepEqual(generatedIndex.summary, {
    total: 26,
    accepted: 4,
    solved: 1,
    published: 0,
    rejected: 0,
    archived: 2,
  });
});

test("homepage table links do not rely on absolute row overlays", async () => {
  const css = await readFile(new URL("../../src/app/globals.css", import.meta.url), "utf8");

  assert.doesNotMatch(css, /\.problem-row-link::after\s*\{/);
  assert.doesNotMatch(css, /\.problem-table-row\s*\{[^}]*position:\s*relative[^}]*\}/s);
});

test("server-renders populated desktop and narrow problem rows", async () => {
  const response = await renderFilesystemFixture({
    manifests: [acceptedFixture],
    damagedIds: ["Prob-018"],
  });
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<tr class="problem-table-row"><th scope="row"><a class="problem-row-link" href="\/problems\/Prob-017">/);
  assert.match(html, /<td><a class="open-affordance" href="\/problems\/Prob-017">Open <span aria-hidden="true">→<\/span><\/a><\/td>/);
  assert.match(html, /<a class="problem-list-item" href="\/problems\/Prob-017" aria-label="Open Prob-017: Fresh Hamiltonian gate">/);
  assert.match(html, /Fresh Hamiltonian gate/);
  assert.match(html, /Interval arithmetic on held-out instances\./);
  assert.match(html, /interval-arithmetic/);
  assert.match(html, /12 sources/);
  assert.match(html, /Accepted after novelty review/);
  assert.match(html, /2026-07-27 11:45:00 UTC/);
  assert.match(html, /1 index errors/);
  assert.match(html, /problems\/Prob-018\/problem\.json/);
  assert.match(html, /Invalid JSON/);
});

test("server-renders rejected records in the unfiltered index listing", async () => {
  const response = await renderFilesystemFixture({
    manifests: [{
      ...acceptedFixture,
      id: "Prob-020",
      title: "Rejected fixture",
      status: "rejected",
      gate: { type: "python", readiness: "specified" },
      rejection: { kind: "human", reason: "Novelty failed." },
    }],
  });
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /Rejected fixture/);
  assert.match(html, /<span class="status-badge status-rejected">Rejected<\/span>/);
  assert.match(html, /<span class="problem-id">Prob-020<\/span>/);
});

test("pages static showcase homepage makes archived public examples visible", async () => {
  const archivedFixture = {
    ...acceptedFixture,
    id: "Prob-124",
    title: "Archived public example",
    summary: "Archived display record for GitHub Pages.",
    status: "archived",
    gate: { type: "documentation", readiness: "specified" },
  };
  const response = await renderFilesystemFixture({
    manifests: [archivedFixture],
    buildEnv: { PAGES_STATIC_SHOWCASE: "1" },
  });
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<span>Prob-124<\/span>/);
  assert.match(html, /Archived public example/);
  assert.doesNotMatch(html, /No matching problems/);
});

test("returns a stable detail route response for unknown problem IDs", async () => {
  const response = await render("/problems/Prob-999");
  assert.equal(response.status, 404);
});

test("ordinary local build serves the static demo route and rejects unknown demo attempts", async () => {
  const problemResponse = await render("/problems/Prob-000");
  assert.equal(problemResponse.status, 200);
  const problemHtml = await problemResponse.text();
  assert.doesNotMatch(problemHtml, /Assessment methodology demo/);
  assert.match(problemHtml, /Scientific Demand Score/);
  assert.match(problemHtml, /Expected Attributable Net Social Value/);
  assert.match(problemHtml, /\+\$180K USD 2026/);
  assert.doesNotMatch(problemHtml, /Industry \/ social proxy/);
  assert.doesNotMatch(problemHtml, /\$57\.0B USD 2035/);
  assert.match(problemHtml, /Autoresearch Fit/);
  assert.match(problemHtml, /Discuss in Codex/);
  assert.match(problemHtml, /href="\/problems\/Prob-000\/autoresearch"/);
  assert.doesNotMatch(problemHtml, /Local assessment unavailable/);
  assert.doesNotMatch(problemHtml, /\/__local\/assessments/);

  const autoresearchResponse = await render("/problems/Prob-000/autoresearch");
  assert.equal(autoresearchResponse.status, 200);
  const autoresearchHtml = await autoresearchResponse.text();
  assert.match(autoresearchHtml, /Autoresearch results/);
  assert.match(autoresearchHtml, /ATT-001/);
  assert.match(autoresearchHtml, /Best speedup/);
  assert.match(autoresearchHtml, /Example data - synthetic results for interface demonstration only\./);
  assert.doesNotMatch(autoresearchHtml, /Local assessment unavailable/);

  for (const pathname of [
    "/problems/Prob-000/attempts/ATT-001",
    "/problems/Prob-000/attempts/ATT-005",
  ]) {
    const response = await render(pathname);
    assert.equal(response.status, 200, pathname);
    const html = await response.text();
    assert.match(html, /Example data - synthetic results for interface demonstration only\./);
  }

  const unknownAttempt = await render("/problems/Prob-000/attempts/ATT-999");
  assert.equal(unknownAttempt.status, 404);
});

test("returns 404 for attempt routes on non-example problems", async () => {
  const response = await renderFilesystemFixture(
    { manifests: [acceptedFixture] },
    "/problems/Prob-017/attempts/ATT-001?fixture=filesystem",
  );
  assert.equal(response.status, 404);
});

test("server-renders the generic problem detail shell for non-example problems", async () => {
  const response = await renderFilesystemFixture(
    { manifests: [acceptedFixture] },
    "/problems/Prob-017?fixture=filesystem",
  );
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<p class="eyebrow">Prob-017<\/p>/);
  assert.match(html, /<h1>Fresh Hamiltonian gate<\/h1>/);
  assert.match(html, /<p class="detail-summary">Interval arithmetic on held-out instances\.<\/p>/);
  assert.match(html, /Available in local mode/);
  assert.match(html, /<button[^>]*disabled=""[^>]*>Prepare autoresearch<\/button>/);
  assert.doesNotMatch(html, /<h2[^>]*>Prepare infrastructure<\/h2>/);
  assert.match(html, /<section class="assessment-panel assessment-unavailable" aria-labelledby="assessment-heading">/);
  assert.match(html, /Local assessment unavailable/);
  assert.match(html, /The detailed problem workspace will be designed next; this page currently locks the route, identity, and return path\./);
  assert.doesNotMatch(html, /[\u3400-\u9FFF]/u);
  assert.match(html, /<a href="\/" class="back-link">← Back to problems<\/a>/);
});

test("pages static showcase renders public problem details without local controls", async () => {
  const response = await renderFilesystemFixture(
    {
      manifests: [acceptedFixture],
      buildEnv: { PAGES_STATIC_SHOWCASE: "1" },
    },
    "/problems/Prob-017?fixture=filesystem",
  );
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<p class="eyebrow">Prob-017<\/p>/);
  assert.match(html, /<h1>Fresh Hamiltonian gate<\/h1>/);
  assert.match(html, /<p class="detail-summary">Interval arithmetic on held-out instances\.<\/p>/);
  assert.match(html, /The detailed problem workspace will be designed next; this page currently locks the route, identity, and return path\./);
  assert.doesNotMatch(html, /Available in local mode/);
  assert.doesNotMatch(html, /Prepare autoresearch/);
  assert.doesNotMatch(html, /Local assessment unavailable/);
  assert.doesNotMatch(html, /\/__local\/assessments/);
  assert.doesNotMatch(html, /\/__local\/autoresearch/);
});

test("server-renders the static assessment methodology demo for the static example detail shell", async () => {
  const response = await renderFilesystemFixture(
    { manifests: [{ ...acceptedFixture, id: "Prob-000" }] },
    "/problems/Prob-000?fixture=filesystem",
  );
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.doesNotMatch(html, /Example data - synthetic results for interface demonstration only\./);
  assert.doesNotMatch(html, /Available in local mode/);
  assert.match(html, /<section class="assessment-panel [^"]+" aria-label="Assessment">/);
  assert.doesNotMatch(html, /Assessment methodology demo/);
  assert.match(html, /Scientific Demand Score/);
  assert.match(html, /Expected Attributable Net Social Value/);
  assert.match(html, /\+\$180K USD 2026/);
  assert.doesNotMatch(html, /Industry \/ social proxy/);
  assert.doesNotMatch(html, /\$57\.0B USD 2035/);
  assert.match(html, /Autoresearch Fit/);
  assert.match(html, /Methodology documentation/);
  assert.doesNotMatch(html, /Technical Success Estimate/);
  assert.doesNotMatch(html, /Local assessment unavailable/);
});
