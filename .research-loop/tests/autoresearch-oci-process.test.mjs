import assert from "node:assert/strict";
import test from "node:test";

import { OciRuntimeUnavailableError, runOciProcess } from "../../src/lib/autoresearch/oci-process.mjs";

const image = `example.invalid/research-loop/preflight@sha256:${"a".repeat(64)}`;

function options(overrides = {}) {
  return {
    image,
    resources: { memoryMb: 256 },
    command: "python3",
    args: ["check.py", "--safe"],
    cwd: "/stage",
    env: { LANG: "C", LC_ALL: "C", LC_CTYPE: "C.UTF-8", PATH: "/host/path", HOME: "/host/home", SECRET: "never" },
    timeoutMs: 12_000,
    uid: 1001,
    gid: 1002,
    randomUUIDFn: () => "fixed-run-id",
    ...overrides,
  };
}

function recordingRunner(calls, behavior = {}) {
  return async (call) => {
    calls.push(call);
    if (call.args[0] === "version") return behavior.version?.(call) ?? { stdout: "ok", stderr: "", code: 0, signal: null };
    if (call.args[0] === "run") return behavior.run?.(call) ?? { stdout: "result", stderr: "", code: 0, signal: null };
    return behavior.cleanup?.(call) ?? { stdout: "", stderr: "", code: 0, signal: null };
  };
}

test("runs an immutable image with hardened OCI argv and locale-only container environment", async () => {
  const calls = [];
  const result = await runOciProcess({ ...options(), runProcessFn: recordingRunner(calls) });
  const runCall = calls.find((call) => call.args[0] === "run");

  assert.deepEqual(result, { stdout: "result", stderr: "", code: 0, signal: null });
  for (const required of [
    "run", "--rm", "--pull=never", "--network=none",
    "--memory=256m", "--memory-swap=256m", "--pids-limit=128",
    "--read-only",
  ]) assert.ok(runCall.args.includes(required));
  assert.ok(runCall.args.includes("--mount=type=bind,source=/stage,target=/workspace"));
  assert.ok(!runCall.args.some((arg) => arg.includes("/operator-private")));
  for (const required of [
    "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user=1001:1002", "--workdir=/workspace",
    "--tmpfs=/tmp:rw,nosuid,nodev,size=64m",
  ]) assert.ok(runCall.args.includes(required));
  assert.equal(runCall.args.at(-4), image);
  assert.deepEqual(runCall.args.slice(-3), ["python3", "check.py", "--safe"]);
  assert.ok(runCall.args.includes("--env=LANG=C"));
  assert.ok(runCall.args.includes("--env=LC_ALL=C"));
  assert.ok(runCall.args.includes("--env=LC_CTYPE=C.UTF-8"));
  assert.ok(!runCall.args.some((arg) => arg.includes("PATH=") || arg.includes("HOME=") || arg.includes("SECRET=")));
});

test("uses Podman only when Docker is unavailable", async () => {
  const calls = [];
  const unavailable = Object.assign(new Error("not found"), { code: "ENOENT" });
  await runOciProcess({
    ...options(),
    runProcessFn: recordingRunner(calls, { version: (call) => call.command === "docker" ? Promise.reject(unavailable) : undefined }),
  });

  assert.deepEqual(calls.map((call) => [call.command, call.args[0]]), [
    ["docker", "version"], ["podman", "version"], ["podman", "run"], ["podman", "rm"],
  ]);
});

test("fails closed when no OCI runtime is available", async () => {
  const calls = [];
  const unavailable = Object.assign(new Error("not found"), { code: "ENOENT" });

  await assert.rejects(
    () => runOciProcess({ ...options(), runProcessFn: recordingRunner(calls, { version: () => Promise.reject(unavailable) }) }),
    OciRuntimeUnavailableError,
  );
  assert.deepEqual(calls.map((call) => [call.command, call.args]), [
    ["docker", ["version"]], ["podman", ["version"]],
  ]);
  assert.ok(calls.every((call) => call.command !== "python3"));
});

test("mounts private data read-only only in evaluator mode", async () => {
  const evaluatorCalls = [];
  await runOciProcess({ ...options({ privateDataRoot: "/operator-private" }), runProcessFn: recordingRunner(evaluatorCalls) });
  const evaluatorRun = evaluatorCalls.find((call) => call.args[0] === "run");
  assert.ok(evaluatorRun.args.includes("--mount=type=bind,source=/operator-private,target=/private,readonly"));
  assert.ok(evaluatorRun.args.includes("--env=AUTORESEARCH_PRIVATE_ROOT=/private"));

  const candidateCalls = [];
  await runOciProcess({ ...options(), runProcessFn: recordingRunner(candidateCalls) });
  const candidateRun = candidateCalls.find((call) => call.args[0] === "run");
  assert.ok(!candidateRun.args.some((arg) => arg.includes("/operator-private") || arg.includes("AUTORESEARCH_PRIVATE_ROOT")));
});

test("removes a named container after completion and preserves the primary execution error when cleanup fails", async () => {
  const successCalls = [];
  await runOciProcess({ ...options(), runProcessFn: recordingRunner(successCalls) });
  assert.deepEqual(successCalls.at(-1).args, ["rm", "-f", "autoresearch-fixed-run-id"]);

  const failureCalls = [];
  const primary = new Error("container command failed");
  const cleanup = new Error("cleanup failed");
  await assert.rejects(
    () => runOciProcess({
      ...options(),
      runProcessFn: recordingRunner(failureCalls, { run: () => Promise.reject(primary), cleanup: () => Promise.reject(cleanup) }),
    }),
    (error) => error === primary,
  );
  assert.deepEqual(failureCalls.at(-1).args, ["rm", "-f", "autoresearch-fixed-run-id"]);
});

test("runs cleanup without an aborted caller signal", async () => {
  const calls = [];
  const controller = new AbortController();
  const aborted = new Error("cancelled");
  controller.abort(aborted);

  await assert.rejects(
    () => runOciProcess({
      ...options({ signal: controller.signal }),
      runProcessFn: recordingRunner(calls, { run: () => Promise.reject(aborted) }),
    }),
    (error) => error === aborted,
  );
  assert.equal(calls.at(-1).args[0], "rm");
  assert.equal(calls.at(-1).signal, undefined);
});

test("rejects unsafe mount sources before invoking a runtime", async () => {
  for (const unsafePath of ["/stage\u0000bad", "/stage,bad", "/stage\rbad", "/stage\nbad"]) {
    const calls = [];
    await assert.rejects(
      () => runOciProcess({ ...options({ cwd: unsafePath }), runProcessFn: recordingRunner(calls) }),
      /mount source path/i,
    );
    assert.equal(calls.length, 0);
  }
});
