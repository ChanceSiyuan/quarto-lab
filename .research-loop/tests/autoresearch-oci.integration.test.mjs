import assert from "node:assert/strict";
import { access, mkdir, mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { runOciProcess } from "../../src/lib/autoresearch/oci-process.mjs";
import { ProcessExecutionError, runProcess } from "../../src/lib/autoresearch/process.mjs";

const PINNED_ALPINE_IMAGE = "alpine@sha256:4bcff63911fcb4448bd4fdacec207030997caf25e9bea4045fa6c8c44de311d1";
const CONTAINER_NAME = "autoresearch-containment-integration";
const HOST_PATH_SENTINEL = `${process.env.PATH}:/autoresearch-host-path-sentinel`;
const HOST_HOME_SENTINEL = "/autoresearch-host-home-sentinel";
const requireContainment = process.env.AUTORESEARCH_REQUIRE_OCI_CONTAINMENT === "1";

function docker(args, cwd) {
  return runProcess({
    command: "docker",
    args,
    cwd,
    env: process.env,
    timeoutMs: 10_000,
    graceMs: 1_000,
  });
}

function isDockerUnavailable(error) {
  return error?.code === "ENOENT" || (error instanceof ProcessExecutionError && /cannot connect to the docker daemon|error during connect|permission denied while trying to connect to the docker api|is the docker daemon running/i.test(error.stderr));
}

function isMissingImage(error) {
  return error instanceof ProcessExecutionError && /no such image|no such object|not found/i.test(error.stderr);
}

function isMissingContainer(error) {
  if (!(error instanceof ProcessExecutionError)) return false;
  const stderr = error.stderr.toLowerCase();
  return [
    `no such container: ${CONTAINER_NAME}`,
    `no such object: ${CONTAINER_NAME}`,
    `container ${CONTAINER_NAME} not found`,
  ].some((message) => stderr.includes(message));
}

function skipUnlessContainmentRequired(t, message, error) {
  if (requireContainment) {
    throw new Error(`${message} Required OCI containment verification cannot continue.`, { cause: error });
  }
  t.skip(message);
}

test("OCI preflight runner confines writes, network, and container lifetime", async (t) => {
  const root = await mkdtemp(join(tmpdir(), "autoresearch-oci-integration-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const workspace = join(root, "workspace");
  const hostSibling = join(root, "sibling");
  await mkdir(workspace);

  try {
    await docker(["info"], root);
  } catch (error) {
    if (!isDockerUnavailable(error)) throw error;
    skipUnlessContainmentRequired(t, "Docker is unavailable (docker info failed).", error);
    return;
  }

  let image;
  try {
    image = (await docker(["image", "inspect", "--format={{index .RepoDigests 0}}", PINNED_ALPINE_IMAGE], root)).stdout.trim();
  } catch (error) {
    if (isDockerUnavailable(error)) {
      skipUnlessContainmentRequired(t, "Docker became unavailable while inspecting the pinned Alpine image.", error);
      return;
    }
    if (!isMissingImage(error)) throw error;
    skipUnlessContainmentRequired(t, `Pinned Alpine image is not preloaded (${PINNED_ALPINE_IMAGE}).`, error);
    return;
  }
  assert.match(image, /^[a-z0-9][a-z0-9._/-]*@sha256:[a-f0-9]{64}$/);

  const result = await runOciProcess({
    image,
    resources: { memoryMb: 64 },
    command: "/bin/sh",
    args: ["-ec", "printf inside > /workspace/inside; if printf escaped > /workspace/../sibling; then exit 1; fi; if wget -q -T 1 -O - http://1.1.1.1; then exit 1; fi; printf '%s\\n%s\\n' \"${PATH-}\" \"${HOME-}\""],
    cwd: workspace,
    env: { LANG: "C", PATH: HOST_PATH_SENTINEL, HOME: HOST_HOME_SENTINEL },
    timeoutMs: 10_000,
    graceMs: 1_000,
    randomUUIDFn: () => "containment-integration",
  });

  assert.equal(result.code, 0);
  const [containerPath, containerHome] = result.stdout.trim().split("\n");
  assert.notEqual(containerPath, HOST_PATH_SENTINEL);
  assert.notEqual(containerHome, HOST_HOME_SENTINEL);
  assert.equal(await readFile(join(workspace, "inside"), "utf8"), "inside");
  await assert.rejects(() => access(hostSibling));
  await assert.rejects(() => docker(["container", "inspect", CONTAINER_NAME], root), isMissingContainer);
});
