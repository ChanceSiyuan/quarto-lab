import assert from "node:assert/strict";
import { mkdir, mkdtemp, realpath, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  INFRASTRUCTURE_ID_PATTERN,
  JOB_ID_PATTERN,
  isProblemId,
  nextInfrastructureId,
} from "../lib/autoresearch/ids.mjs";
import { assertContained, createAutoresearchPaths } from "../lib/autoresearch/paths.mjs";

test("autoresearch IDs accept only their host-owned forms and advance past occupied revisions", () => {
  assert.equal(JOB_ID_PATTERN.test("ARJ-20260728T080000Z-deadbeef"), true);
  assert.equal(INFRASTRUCTURE_ID_PATTERN.test("INF-001"), true);
  assert.equal(isProblemId("Prob-007"), true);
  assert.equal(isProblemId("Prob-7"), false);
  assert.equal(nextInfrastructureId(["INF-001", "broken", "INF-003"]), "INF-004");
});

test("autoresearch paths derive revisions beneath the named problem infrastructure", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "autoresearch-paths-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const paths = createAutoresearchPaths(root);
  const canonicalRoot = await realpath(root);

  assert.equal(paths.revisionRoot("Prob-007", "INF-004"), join(canonicalRoot, "problems", "Prob-007", "infrastructure", "INF-004"));
  assert.throws(() => paths.revisionRoot("../escape", "INF-001"), /problem ID/i);
  assert.throws(() => paths.revisionRoot("Prob-007", "../../escape"), /infrastructure ID/i);
  assert.throws(() => assertContained(join(root, "outside"), paths.jobsRoot), /outside/i);
});

test("autoresearch paths reject a configured root that is a symlink", async (t) => {
  const realRoot = await mkdtemp(join(tmpdir(), "autoresearch-paths-"));
  const linkParent = await mkdtemp(join(tmpdir(), "autoresearch-links-"));
  const linkedRoot = join(linkParent, "linked-root");
  t.after(() => Promise.all([rm(realRoot, { recursive: true, force: true }), rm(linkParent, { recursive: true, force: true })]));
  await symlink(realRoot, linkedRoot);

  assert.throws(() => createAutoresearchPaths(linkedRoot), /symlink/i);
});

test("canonical containment rejects a nominal job path that crosses a symlink", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "autoresearch-paths-"));
  const outside = await mkdtemp(join(tmpdir(), "autoresearch-outside-"));
  t.after(() => Promise.all([rm(root, { recursive: true, force: true }), rm(outside, { recursive: true, force: true })]));
  const paths = createAutoresearchPaths(root);
  const jobs = join(root, "jobs");
  await mkdir(jobs, { recursive: true });
  await symlink(outside, join(jobs, "ARJ-20260728T080000Z-deadbeef"));

  assert.throws(
    () => assertContained(join(jobs, "ARJ-20260728T080000Z-deadbeef", "payload"), jobs),
    /outside|symlink/i,
  );
  assert.equal(typeof await realpath(outside), "string");
  assert.equal(paths.jobsRoot, join(await realpath(root), "jobs"));
});

test("containment rejects symlinks even when their destination remains inside the root", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "autoresearch-paths-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const jobs = join(root, "jobs");
  await mkdir(join(jobs, "real-job"), { recursive: true });
  await symlink(join(jobs, "real-job"), join(jobs, "linked-job"));

  assert.throws(() => assertContained(join(jobs, "linked-job", "payload"), jobs), /symlink/i);
});
