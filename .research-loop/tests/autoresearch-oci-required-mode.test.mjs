import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { chmod, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

const integrationTest = ".research-loop/tests/autoresearch-oci.integration.test.mjs";

function runNodeTest(environment) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ["--test", integrationTest], {
      cwd: process.cwd(),
      env: environment,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk; });
    child.stderr.on("data", (chunk) => { stderr += chunk; });
    child.once("error", reject);
    child.once("close", (code) => {
      if (code === 0) resolve({ stdout, stderr });
      else reject(Object.assign(new Error(`node --test exited with ${code}`), { stdout, stderr }));
    });
  });
}

test("required OCI containment mode fails when Docker is unavailable", async (t) => {
  const bin = await mkdtemp(join(tmpdir(), "autoresearch-oci-required-mode-"));
  t.after(() => rm(bin, { recursive: true, force: true }));

  const docker = join(bin, "docker");
  await writeFile(docker, "#!/bin/sh\necho 'Cannot connect to the Docker daemon.' >&2\nexit 1\n");
  await chmod(docker, 0o755);
  const environment = { ...process.env };
  delete environment.NODE_TEST_CONTEXT;

  await assert.rejects(
    () => runNodeTest({
      ...environment,
      PATH: `${bin}:${process.env.PATH}`,
      AUTORESEARCH_REQUIRE_OCI_CONTAINMENT: "1",
    }),
    (error) => {
      const output = `${error.stdout}${error.stderr}`;
      assert.match(output, /Docker is unavailable/i);
      assert.doesNotMatch(output, /# SKIP/);
      return true;
    },
  );
});
