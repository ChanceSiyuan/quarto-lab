import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import test from "node:test";

const execFileAsync = promisify(execFile);
const workspaceRoot = fileURLToPath(new URL("../../", import.meta.url));

test("Prob-000 static example is accepted by the problem index", async () => {
  const tempRoot = await mkdtemp(join(tmpdir(), "research-loop-index-"));
  const outPath = join(tempRoot, "problem-index.json");
  try {
    await execFileAsync(
      process.execPath,
      [
        ".research-loop/tooling/scripts/build-problem-index.mjs",
        "--root", workspaceRoot,
        "--problems-dir", ".research-loop/fixtures/showcase/problems",
        "--out", outPath,
      ],
      { cwd: workspaceRoot, maxBuffer: 10 * 1024 * 1024 },
    );
    const index = JSON.parse(await readFile(outPath, "utf8"));
    const problem = index.problems.find((item) => item.id === "Prob-000");
    assert.ok(problem);
    assert.equal(problem.title, "CSS code-distance algorithm search");
    assert.equal(problem.status, "solving");
    assert.deepEqual(problem.gate, {
      type: "python-benchmark",
      readiness: "executable",
    });
    assert.equal(problem.provenance.sourceCount, 3);
    assert.equal(problem.lastActivity.summary, "Static example ledger prepared");
  } finally {
    await rm(tempRoot, { recursive: true, force: true });
  }
});

test("Prob-000 static example records are labeled as synthetic display data", async () => {
  const example = JSON.parse(
    await readFile(new URL("../fixtures/showcase/problems/Prob-000/example.json", import.meta.url), "utf8"),
  );
  assert.equal(example.kind, "static-research-example");
  assert.equal(
    example.disclaimer,
    "Example data - synthetic results for interface demonstration only.",
  );
  assert.equal(example.baseline.label, "Synthetic SOTA baseline");
  assert.equal(example.baseline.suiteRuntimeSeconds, 1820.4);

  for (const name of ["initial-prompt.md", "transcript.md", "decision.md"]) {
    const text = await readFile(
      new URL(`../fixtures/showcase/problems/Prob-000/generation/${name}`, import.meta.url),
      "utf8",
    );
    assert.match(text, /static example/i);
    assert.match(text, /synthetic/i);
  }

  await assert.rejects(
    readFile(new URL("../../problems/Prob-000/problem.json", import.meta.url), "utf8"),
    { code: "ENOENT" },
  );
});
