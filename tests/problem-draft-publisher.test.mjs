import assert from "node:assert/strict";
import { copyFile, lstat, mkdir, mkdtemp, readFile, rename, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";

import {
  DEFAULT_PUBLISH_FILE_OPS,
  publishStagedDraft,
} from "../lib/problems/draft-publisher.mjs";
import { buildProblemIndex } from "../lib/problems/indexer.mjs";

const DRAFT_MARKDOWN = [
  "Candidate Question",
  "Motivation and Context",
  "Discussion Summary",
  "Evidence Mentioned",
  "Open Qualification Questions",
].map((heading) => `## ${heading}\nConcrete draft content.`).join("\n\n");

async function makePublisherFixture(id) {
  const rootDir = await mkdtemp(join(tmpdir(), "research-loop-draft-publisher-"));
  const stageDir = join(rootDir, ".generated", "problem-staging", "run-001", id);
  await mkdir(join(stageDir, "generation"), { recursive: true });
  const now = "2026-07-28T08:00:00.000Z";
  await writeFile(join(stageDir, "problem.json"), `${JSON.stringify({
    schemaVersion: 1,
    id,
    title: "Candidate title",
    summary: "Candidate summary",
    status: "draft",
    gate: { type: "unspecified", readiness: "missing" },
    provenance: { sourceCount: 0 },
    lastActivity: { summary: "Draft registered from brainstorming.", at: now },
    createdAt: now,
    updatedAt: now,
  }, null, 2)}\n`);
  await writeFile(join(stageDir, "problem.md"), `${DRAFT_MARKDOWN}\n`);
  await writeFile(join(stageDir, "generation", "initial-prompt.md"), "Short launch prompt.\n");
  await writeFile(join(stageDir, "generation", "transcript.md"), "## User\nCandidate discussion.\n");
  await writeFile(join(stageDir, "generation", "decision.md"), "Registered as draft after confirmation.\n");
  return { rootDir, stageDir };
}

test("publishes non-manifest files before atomically publishing problem.json", async () => {
  const fixture = await makePublisherFixture("Prob-001");
  const events = [];
  const fileOps = {
    ...DEFAULT_PUBLISH_FILE_OPS,
    async copyFile(source, target) {
      events.push(["copy", target]);
      return copyFile(source, target);
    },
    async rename(source, target) {
      events.push(["rename", target]);
      return rename(source, target);
    },
  };
  const result = await publishStagedDraft({
    rootDir: fixture.rootDir,
    stageDir: fixture.stageDir,
    expectedId: "Prob-001",
    fileOps,
    rebuildIndex: (rootDir) => buildProblemIndex({ rootDir, reservedIds: ["Prob-000"] }),
  });
  assert.equal(result.status, "published");
  assert.equal(events.at(-1)[0], "rename");
  assert.match(events.at(-1)[1], /problems\/Prob-001\/problem\.json$/);
  assert.equal(JSON.parse(await readFile(join(fixture.rootDir, result.problemPath, "problem.json"))).status, "draft");
});

test("reports a collision from a damaged reserved directory without overwriting it", async () => {
  const fixture = await makePublisherFixture("Prob-001");
  const reserved = join(fixture.rootDir, "problems", "Prob-001");
  await mkdir(reserved, { recursive: true });
  await writeFile(join(reserved, "problem.json"), "{ broken json");
  const before = await readFile(join(reserved, "problem.json"), "utf8");
  const result = await publishStagedDraft({ ...fixture, expectedId: "Prob-001" });
  assert.deepEqual(result, { status: "collision", id: "Prob-001", nextProblemId: "Prob-002" });
  assert.equal(await readFile(join(reserved, "problem.json"), "utf8"), before);
});

test("cleans only its incomplete target when copying fails and retains staging", async () => {
  const fixture = await makePublisherFixture("Prob-001");
  const fileOps = {
    ...DEFAULT_PUBLISH_FILE_OPS,
    async copyFile(source, target) {
      if (source.endsWith("transcript.md")) throw new Error("injected copy failure");
      return copyFile(source, target);
    },
  };
  await assert.rejects(
    publishStagedDraft({ ...fixture, expectedId: "Prob-001", fileOps }),
    /injected copy failure/,
  );
  await assert.rejects(lstat(join(fixture.rootDir, "problems", "Prob-001")), { code: "ENOENT" });
  assert.equal((await lstat(fixture.stageDir)).isDirectory(), true);
});

test("keeps a published draft when index refresh fails", async () => {
  const fixture = await makePublisherFixture("Prob-001");
  const result = await publishStagedDraft({
    ...fixture,
    expectedId: "Prob-001",
    rebuildIndex: async () => { throw new Error("injected index failure"); },
  });
  assert.equal(result.status, "published-index-stale");
  assert.match(result.error, /injected index failure/);
  assert.equal(JSON.parse(await readFile(join(fixture.rootDir, "problems", "Prob-001", "problem.json"))).id, "Prob-001");
});

test("returns a collision without cleaning a target created by a concurrent publisher", async () => {
  const fixture = await makePublisherFixture("Prob-001");
  const target = join(fixture.rootDir, "problems", "Prob-001");
  let targetMkdirCalls = 0;
  let cleanupCalls = 0;
  const fileOps = {
    ...DEFAULT_PUBLISH_FILE_OPS,
    async mkdir(path, options) {
      if (path === target && options?.recursive === false) {
        targetMkdirCalls += 1;
        await mkdir(path, { recursive: false });
        const error = new Error("target appeared concurrently");
        error.code = "EEXIST";
        throw error;
      }
      return mkdir(path, options);
    },
    async rm(path, options) {
      cleanupCalls += 1;
      return DEFAULT_PUBLISH_FILE_OPS.rm(path, options);
    },
  };
  const result = await publishStagedDraft({ ...fixture, expectedId: "Prob-001", fileOps });
  assert.equal(targetMkdirCalls, 1);
  assert.equal(cleanupCalls, 0);
  assert.deepEqual(result, { status: "collision", id: "Prob-001", nextProblemId: "Prob-002" });
  assert.equal((await lstat(target)).isDirectory(), true);
});

test("CLI publishes a complete staged draft as one JSON object", async () => {
  const fixture = await makePublisherFixture("Prob-001");
  const child = spawnSync(process.execPath, [
    "scripts/publish-problem.mjs",
    "--root", fixture.rootDir,
    "--stage", fixture.stageDir,
    "--id", "Prob-001",
  ], { cwd: resolve("."), encoding: "utf8" });
  assert.equal(child.status, 0, child.stderr);
  assert.deepEqual(JSON.parse(child.stdout), {
    status: "published",
    id: "Prob-001",
    problemPath: "problems/Prob-001",
    indexPath: ".generated/problem-index.json",
  });
});
