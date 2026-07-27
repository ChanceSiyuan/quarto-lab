import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

const execFileAsync = promisify(execFile);
const workspaceRoot = fileURLToPath(new URL("../", import.meta.url));
const generatedIndexUrl = new URL("../.generated/problem-index.json", import.meta.url);
const generatedIndex = JSON.parse(
  await readFile(generatedIndexUrl, "utf8"),
);

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
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

async function renderPopulatedFixture(pathname = "/?fixture=populated") {
  const originalIndexText = await readFile(generatedIndexUrl, "utf8");
  const fixtureIndex = {
    ...generatedIndex,
    generatedAt: "2026-07-27T12:00:00.000Z",
    nextProblemId: "QMB-018",
    problems: [
      {
        schemaVersion: 1,
        id: "QMB-017",
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
      },
    ],
    summary: {
      total: 1,
      accepted: 1,
      solved: 0,
      published: 0,
      rejected: 0,
      archived: 0,
      target: generatedIndex.summary.target,
    },
    diagnostics: [],
  };

  async function buildCurrentIndex() {
    await execFileAsync(
      fileURLToPath(new URL("../node_modules/.bin/vinext", import.meta.url)),
      ["build"],
      {
        cwd: workspaceRoot,
        env: { ...process.env, WRANGLER_LOG_PATH: ".wrangler/wrangler.log" },
        maxBuffer: 10 * 1024 * 1024,
      },
    );
  }

  await writeFile(generatedIndexUrl, `${JSON.stringify(fixtureIndex, null, 2)}\n`);
  try {
    await buildCurrentIndex();
    const response = await render(pathname);
    const html = await response.text();
    return new Response(html, { status: response.status, headers: response.headers });
  } finally {
    await writeFile(generatedIndexUrl, originalIndexText);
    await buildCurrentIndex();
  }
}

test("server-renders the problem console shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Research Loop/);
  assert.match(html, /问题/);
  assert.match(html, /增加问题/);
  assert.match(html, /Cannot open Codex\?/);
  assert.match(html, /codex:\/\/threads\/new/);
  assert.match(html, /Accepted/);
  assert.match(html, /Solved/);
  assert.match(html, /Published/);
  for (const [label, key] of [
    ["Accepted", "accepted"],
    ["Solved", "solved"],
    ["Published", "published"],
  ]) {
    assert.match(
      html,
      new RegExp(`<dt>${label}</dt><dd>${generatedIndex.summary[key]} / ${generatedIndex.summary.target}</dd>`),
    );
  }
  assert.match(
    html,
    /<th scope="col">Problem<\/th><th scope="col">Status<\/th><th scope="col">Executable gate<\/th><th scope="col">Provenance<\/th><th scope="col">Recent activity<\/th><th scope="col">Updated<\/th><th scope="col">Open<\/th>/,
  );
  assert.doesNotMatch(html, /Turn open literature into/);
  assert.doesNotMatch(html, /Reset demo/);
  assert.doesNotMatch(html, /localStorage/);
});

test("server-renders populated desktop and narrow problem rows", async () => {
  const response = await renderPopulatedFixture();
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(
    html,
    /<tr><th scope="row"><a href="\/problems\/QMB-017"><span>QMB-017<\/span><strong>Fresh Hamiltonian gate<\/strong><small>Interval arithmetic on held-out instances\.<\/small><\/a><\/th><td><span class="status-badge status-accepted">已接受<\/span><\/td><td class="cell-stack"><strong>interval-arithmetic<\/strong><small>executable<\/small><\/td><td>12 sources<\/td><td class="cell-stack"><strong>Accepted after novelty review<\/strong><small>2026-07-27 10:30:00 UTC<\/small><\/td><td>2026-07-27 11:45:00 UTC<\/td><td><a class="open-affordance" href="\/problems\/QMB-017">Open <span aria-hidden="true">→<\/span><\/a><\/td><\/tr>/,
  );
  assert.match(
    html,
    /<article class="problem-list-item"><div class="mobile-problem-field"><span class="mobile-field-label">Problem<\/span><span class="problem-id">QMB-017<\/span><h2>Fresh Hamiltonian gate<\/h2><p>Interval arithmetic on held-out instances\.<\/p><\/div><dl><div><dt>Status<\/dt><dd><span class="status-badge status-accepted">已接受<\/span><\/dd><\/div><div><dt>Executable gate<\/dt><dd>interval-arithmetic<!-- --> · <!-- -->executable<\/dd><\/div><div><dt>Provenance<\/dt><dd>12 sources<\/dd><\/div><div><dt>Recent activity<\/dt><dd>Accepted after novelty review<!-- --> · <!-- -->2026-07-27 10:30:00 UTC<\/dd><\/div><div><dt>Updated<\/dt><dd>2026-07-27 11:45:00 UTC<\/dd><\/div><div><dt>Open<\/dt><dd><a class="open-affordance" href="\/problems\/QMB-017">Open problem<!-- --> <span aria-hidden="true">→<\/span><\/a><\/dd><\/div><\/dl><\/article>/,
  );
});

test("returns a stable detail route response for unknown problem IDs", async () => {
  const response = await render("/problems/QMB-999");
  assert.equal(response.status, 404);
});

test("server-renders the populated problem detail shell", async () => {
  const response = await renderPopulatedFixture("/problems/QMB-017?fixture=populated");
  assert.equal(response.status, 200);

  const html = await response.text();
  assert.match(html, /<p class="eyebrow">QMB-017<\/p>/);
  assert.match(html, /<h1>Fresh Hamiltonian gate<\/h1>/);
  assert.match(html, /<p class="detail-summary">Interval arithmetic on held-out instances\.<\/p>/);
  assert.match(html, /详情界面将在后续设计；本页先固定路由、身份和返回路径。/);
  assert.match(html, /<a href="\/" class="back-link">← Back to problems<\/a>/);
});
