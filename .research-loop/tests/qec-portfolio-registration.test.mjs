import assert from "node:assert/strict";
import { cp, mkdir, mkdtemp, readFile, readdir, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { QEC_PORTFOLIO_PROBLEMS } from "../../src/lib/qec-portfolio/catalog.mjs";
import {
  registerQecPortfolio,
  renderGenerationAudit,
  renderProblemManifest,
  renderProblemMarkdown,
  stageQecProblem,
  verifyPublishedProblem,
} from "../../src/lib/qec-portfolio/registration.mjs";

async function relativeFiles(directory, prefix = "") {
  const files = [];
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const relativePath = `${prefix}${entry.name}`;
    if (entry.isDirectory()) files.push(...await relativeFiles(join(directory, entry.name), `${relativePath}/`));
    else files.push(relativePath);
  }
  return files.sort();
}

async function createRegistrationFixture() {
  const rootDir = await mkdtemp(join(tmpdir(), "research-loop-qec-registration-"));
  const now = "2026-07-29T12:00:00.000Z";
  await mkdir(join(rootDir, "problems", "Prob-001"), { recursive: true });
  await writeFile(join(rootDir, "problems", "Prob-001", "problem.json"), `${JSON.stringify({
    schemaVersion: 1,
    id: "Prob-001",
    title: "Existing problem",
    summary: "Existing approved problem.",
    status: "draft",
    gate: { type: "existing-gate", readiness: "specified" },
    provenance: { sourceCount: 1 },
    lastActivity: { summary: "Existing draft.", at: now },
    createdAt: now,
    updatedAt: now,
  }, null, 2)}\n`);
  return { rootDir };
}

test("renders the exact approved draft manifest, markdown, and audit boundary", () => {
  const record = QEC_PORTFOLIO_PROBLEMS[0];
  assert.deepEqual(renderProblemManifest(record), {
    schemaVersion: 1,
    id: "Prob-002",
    title: "Finite-Length qLDPC Code Search Under Hardware Constraints",
    summary: "Search for finite-length qLDPC codes that improve the rate–distance–check-weight–decoder-performance frontier.",
    domain: "quantum-computing",
    quantumArea: "error-correction-and-fault-tolerance",
    status: "draft",
    gate: { type: "finite-length-code-pareto", readiness: "specified" },
    provenance: { sourceCount: 3 },
    lastActivity: { summary: "Draft registered from QEC portfolio brainstorming.", at: record.updatedAt },
    createdAt: record.createdAt,
    updatedAt: record.updatedAt,
  });
  const markdown = renderProblemMarkdown(record);
  assert.deepEqual(markdown.match(/^# .+$/gm), [
    "# Candidate Question",
    "# Motivation and Context",
    "# Discussion Summary",
    "# Evidence Mentioned",
    "# Open Qualification Questions",
  ]);
  assert.match(markdown, /Registration does not start an autoresearch campaign\./);
  assert.doesNotMatch(markdown, /\p{Script=Han}/u);
  assert.deepEqual([...renderGenerationAudit(record).keys()], ["initial-prompt.md", "transcript.md", "decision.md"]);
  assert.equal(renderGenerationAudit(record).get("decision.md"), "Approved after exact preview on 2026-07-29; publish as draft only.\n");
});

test("stages exactly the approved five-file draft", async () => {
  const { rootDir } = await createRegistrationFixture();
  const result = await stageQecProblem({ rootDir, runId: "20260729T130000Z-catalog", record: QEC_PORTFOLIO_PROBLEMS[0] });
  assert.deepEqual(await relativeFiles(result.stageDir), [
    "generation/decision.md",
    "generation/initial-prompt.md",
    "generation/transcript.md",
    "problem.json",
    "problem.md",
  ]);
  const manifest = JSON.parse(await readFile(join(result.stageDir, "problem.json"), "utf8"));
  assert.deepEqual(manifest.gate, { type: "finite-length-code-pareto", readiness: "specified" });
  assert.equal(manifest.provenance.sourceCount, 3);
  assert.ok(Date.parse(manifest.createdAt) <= Date.parse(manifest.updatedAt));
  const markdown = await readFile(join(result.stageDir, "problem.md"), "utf8");
  assert.match(markdown, /^# Candidate Question\n/m);
  assert.doesNotMatch(`${manifest.title}\n${manifest.summary}\n${markdown}`, /\p{Script=Han}/u);
  assert.match(result.digest, /^[a-f0-9]{64}$/);
});

test("stops at a publisher collision without publishing later IDs", async () => {
  const { rootDir } = await createRegistrationFixture();
  const calls = [];
  const summary = await registerQecPortfolio({
    rootDir,
    records: QEC_PORTFOLIO_PROBLEMS.slice(0, 3),
    publish: async ({ id }) => {
      calls.push(id);
      if (id === "Prob-003") return { status: "collision", id, nextProblemId: "Prob-004" };
      return { status: "published", id };
    },
  });
  assert.deepEqual(calls, ["Prob-002", "Prob-003"]);
  assert.deepEqual(summary, {
    published: ["Prob-002"],
    skipped: [],
    failed: [{ id: "Prob-003", code: "PROBLEM_COLLISION", message: "Problem ID is already occupied." }],
  });
});

test("skips only an exact previously published five-file draft on restart", async () => {
  const { rootDir } = await createRegistrationFixture();
  const record = QEC_PORTFOLIO_PROBLEMS[0];
  const staged = await stageQecProblem({ rootDir, runId: "first-run", record });
  await cp(staged.stageDir, join(rootDir, "problems", record.id), { recursive: true });
  assert.equal(await verifyPublishedProblem({ rootDir, record, digest: staged.digest }), true);
  const calls = [];
  const summary = await registerQecPortfolio({ rootDir, records: [record], publish: async ({ id }) => {
    calls.push(id);
    return { status: "published", id };
  }});
  assert.deepEqual(calls, []);
  assert.deepEqual(summary, { published: [], skipped: ["Prob-002"], failed: [] });
});

test("skips an exact published draft with allowed local runtime artifacts on restart", async () => {
  const { rootDir } = await createRegistrationFixture();
  const record = QEC_PORTFOLIO_PROBLEMS[0];
  const staged = await stageQecProblem({ rootDir, runId: "first-run", record });
  const target = join(rootDir, "problems", record.id);
  await cp(staged.stageDir, target, { recursive: true });
  await mkdir(join(target, "valuation", "snapshots", "20260729T010203Z-0123456789ab"), { recursive: true });
  await writeFile(join(target, "valuation", "snapshots", "20260729T010203Z-0123456789ab", "manifest.json"), "{}\n");
  await mkdir(join(target, "assessments", "20260729T010204Z-b1c2d3"), { recursive: true });
  await writeFile(join(target, "assessments", "20260729T010204Z-b1c2d3", "run.json"), "{}\n");

  assert.equal(await verifyPublishedProblem({ rootDir, record, digest: staged.digest }), true);
  const calls = [];
  const summary = await registerQecPortfolio({ rootDir, records: [record], publish: async ({ id }) => {
    calls.push(id);
    return { status: "published", id };
  }});

  assert.deepEqual(calls, []);
  assert.deepEqual(summary, { published: [], skipped: ["Prob-002"], failed: [] });
});

test("rejects a restart target with an extra file before publishing later IDs", async () => {
  const { rootDir } = await createRegistrationFixture();
  const record = QEC_PORTFOLIO_PROBLEMS[0];
  const staged = await stageQecProblem({ rootDir, runId: "first-run", record });
  const target = join(rootDir, "problems", record.id);
  await cp(staged.stageDir, target, { recursive: true });
  await writeFile(join(target, "extra.md"), "This file is not part of the approved draft.\n");
  assert.equal(await verifyPublishedProblem({ rootDir, record, digest: staged.digest }), false);
  const calls = [];
  const summary = await registerQecPortfolio({ rootDir, records: QEC_PORTFOLIO_PROBLEMS.slice(0, 2), publish: async ({ id }) => {
    calls.push(id);
    return { status: "published", id };
  }});
  assert.deepEqual(calls, []);
  assert.deepEqual(summary, {
    published: [],
    skipped: [],
    failed: [{ id: "Prob-002", code: "PROBLEM_COLLISION", message: "Existing problem does not match the approved staged draft." }],
  });
});

test("reports a non-identical existing draft before invoking the publisher or later IDs", async () => {
  const { rootDir } = await createRegistrationFixture();
  const record = QEC_PORTFOLIO_PROBLEMS[0];
  await mkdir(join(rootDir, "problems", record.id), { recursive: true });
  await writeFile(join(rootDir, "problems", record.id, "problem.json"), "{ not the approved draft }\n");
  const calls = [];
  const summary = await registerQecPortfolio({ rootDir, records: QEC_PORTFOLIO_PROBLEMS.slice(0, 2), publish: async ({ id }) => {
    calls.push(id);
    return { status: "published", id };
  }});
  assert.deepEqual(calls, []);
  assert.deepEqual(summary, {
    published: [],
    skipped: [],
    failed: [{ id: "Prob-002", code: "PROBLEM_COLLISION", message: "Existing problem does not match the approved staged draft." }],
  });
});
