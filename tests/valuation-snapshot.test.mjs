import assert from "node:assert/strict";
import { mkdtemp, mkdir, readdir, readFile, symlink, unlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  canonicalJson,
  createValuationSnapshotStore,
  snapshotDigest,
} from "../lib/valuations/snapshot-store.mjs";

async function makeRoot() {
  const root = await mkdtemp(join(tmpdir(), "research-loop-valuation-snapshot-"));
  await mkdir(join(root, "problems"), { recursive: true });
  return root;
}

function snapshotInputs() {
  return {
    manifest: {
      schemaVersion: 1,
      quantumArea: "hardware-and-control",
      createdAt: "2026-07-29T09:10:11Z",
    },
    papers: [{ id: "W1", title: "A paper" }],
    marketEvidence: [{ id: "src-1", kind: "market" }],
  };
}

test("canonical JSON sorts object keys without changing array order", () => {
  assert.equal(canonicalJson({ z: [{ b: 2, a: 1 }], a: true }), '{"a":true,"z":[{"a":1,"b":2}]}');
  assert.notEqual(canonicalJson({ values: ["first", "second"] }), canonicalJson({ values: ["second", "first"] }));
});

test("snapshot identity is stable and non-self-referential", () => {
  const left = snapshotDigest({
    manifest: { schemaVersion: 1, snapshotId: "ignored-a", contentHash: "ignored-b", quantumArea: "hardware-and-control" },
    papers: [{ id: "W1" }],
    marketEvidence: [{ id: "src-1" }],
  });
  const right = snapshotDigest({
    marketEvidence: [{ id: "src-1" }],
    papers: [{ id: "W1" }],
    manifest: { quantumArea: "hardware-and-control", contentHash: "changed", snapshotId: "changed", schemaVersion: 1 },
  });
  assert.equal(left, right);
});

test("freezes exactly three verified files through a contained staging directory", async () => {
  const root = await makeRoot();
  const store = createValuationSnapshotStore({ rootDir: root, now: () => new Date("2026-07-29T09:10:11Z") });
  const inputs = snapshotInputs();
  const digest = snapshotDigest(inputs);

  const frozen = await store.freeze("Prob-001", inputs);
  const snapshotId = `20260729T091011Z-${digest.slice(0, 12)}`;
  const snapshotDir = join(root, "problems", "Prob-001", "valuation", "snapshots", snapshotId);

  assert.equal(frozen.manifest.snapshotId, snapshotId);
  assert.equal(frozen.manifest.contentHash, digest);
  assert.deepEqual((await readdir(snapshotDir)).sort(), ["manifest.json", "market-evidence.json", "papers.json"]);
  assert.equal((await readdir(join(root, ".generated", "valuation-snapshots"))).length, 0);
  assert.deepEqual(await store.list("Prob-001"), [snapshotId]);
  assert.deepEqual(await store.read("Prob-001", snapshotId), frozen);
  assert.deepEqual(await store.verify("Prob-001", snapshotId), frozen);
});

test("refuses tampered snapshots and paths outside the problem", async () => {
  const root = await makeRoot();
  const store = createValuationSnapshotStore({ rootDir: root, now: () => new Date("2026-07-29T09:10:11Z") });
  const frozen = await store.freeze("Prob-001", snapshotInputs());
  const manifestPath = join(root, "problems", "Prob-001", "valuation", "snapshots", frozen.manifest.snapshotId, "manifest.json");
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
  manifest.quantumArea = "algorithms-and-applications";
  await writeFile(manifestPath, `${JSON.stringify(manifest)}\n`);

  await assert.rejects(store.verify("Prob-001", frozen.manifest.snapshotId), /hash mismatch/i);
  await assert.rejects(store.read("../Prob-001", frozen.manifest.snapshotId), /Invalid problem ID/i);
});

test("private overlays are local-only and make frozen snapshots private", async () => {
  const root = await makeRoot();
  const store = createValuationSnapshotStore({ rootDir: root, now: () => new Date("2026-07-29T09:10:11Z") });
  await store.writeInputs("Prob-001", { confirmationIds: ["confirm-1"], input: { visibility: "public", value: 3 } });
  const overlayPath = join(root, "problems", "Prob-001", "valuation", "inputs.private.json");
  await writeFile(overlayPath, JSON.stringify({ input: { visibility: "private", value: 42 } }));

  assert.deepEqual(await store.readInputs("Prob-001"), {
    confirmationIds: ["confirm-1"],
    input: { visibility: "private", value: 42 },
  });
  const frozen = await store.freeze("Prob-001", { ...snapshotInputs(), manifest: { ...snapshotInputs().manifest, ...(await store.readInputs("Prob-001")) } });
  assert.equal(frozen.manifest.visibility, "private");
});

test("refuses a symlinked public inputs file for both reads and writes", async () => {
  const root = await makeRoot();
  const store = createValuationSnapshotStore({ rootDir: root });
  const valuationDir = join(root, "problems", "Prob-001", "valuation");
  const outside = join(root, "outside-public.json");
  await mkdir(valuationDir, { recursive: true });
  await writeFile(outside, '{"outside":true}');
  await symlink(outside, join(valuationDir, "inputs.json"));

  await assert.rejects(store.readInputs("Prob-001"), /symbolic link/i);
  await assert.rejects(store.writeInputs("Prob-001", { visibility: "public", value: 3 }), /symbolic link/i);
  assert.equal(await readFile(outside, "utf8"), '{"outside":true}');
});

test("refuses a symlinked private inputs overlay", async () => {
  const root = await makeRoot();
  const store = createValuationSnapshotStore({ rootDir: root });
  const valuationDir = join(root, "problems", "Prob-001", "valuation");
  const outside = join(root, "outside-private.json");
  await mkdir(valuationDir, { recursive: true });
  await writeFile(join(valuationDir, "inputs.json"), '{"public":true}');
  await writeFile(outside, '{"secret":42}');
  await symlink(outside, join(valuationDir, "inputs.private.json"));

  await assert.rejects(store.readInputs("Prob-001"), /symbolic link/i);
  await unlink(join(valuationDir, "inputs.private.json"));
  assert.equal(await readFile(outside, "utf8"), '{"secret":42}');
});
