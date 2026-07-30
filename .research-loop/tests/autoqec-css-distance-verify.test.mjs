import assert from "node:assert/strict";
import { mkdir, mkdtemp, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { verifyImportedProblemTree } from "../../src/lib/problems/autoqec-css-distance/importer.mjs";

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
      sha256: "9b75290f6a6359a2a3471022cbba4b724e45105b313ae8f6c103a2f79e82a857",
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

test("offline verification rejects a problem ID outside the problem tree", async () => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-import-verify-"));
  const result = await verifyImportedProblemTree({ rootDir: root, id: "../outside" });

  assert.equal(result.ok, false);
  assert.deepEqual(result.errors, [{
    relativePath: "problems/../outside/import-manifest.json",
    field: "id",
    message: "id must be a Prob-### identifier.",
  }]);
});

test("offline verification rejects files missing from import-manifest", async () => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-import-verify-"));
  const problem = join(root, "problems", "Prob-001");
  await mkdir(join(problem, "attempts", "ATT-001"), { recursive: true });
  await writeFile(join(problem, "attempts", "ATT-001", "LOG.md"), "log\n");
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
  assert.match(result.errors.map((item) => item.message).join("\n"), /Non-regular file in imported problem tree: attempts\/ATT-001\/alias.md/);
});

test("offline verification reports a JSON manifest with an invalid shape", async () => {
  const root = await mkdtemp(join(tmpdir(), "research-loop-import-verify-"));
  const problem = join(root, "problems", "Prob-001");
  await mkdir(problem, { recursive: true });
  await writeFile(join(problem, "import-manifest.json"), "null\n");

  const result = await verifyImportedProblemTree({ rootDir: root });
  assert.equal(result.ok, false);
  assert.match(result.errors[0].message, /Manifest must be an object/);
});
