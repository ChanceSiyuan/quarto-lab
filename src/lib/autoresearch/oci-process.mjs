import { randomUUID } from "node:crypto";

import { runProcess } from "./process.mjs";

const DEFAULT_RUNTIME_CANDIDATES = Object.freeze(["docker", "podman"]);
const DEFAULT_GRACE_MS = 5_000;
const CLEANUP_TIMEOUT_MS = 5_000;
const OCI_IMAGE = /^[a-z0-9][a-z0-9._\/-]*(?::[a-z0-9][a-z0-9._-]*)?@sha256:[a-f0-9]{64}$/;
const CONTAINER_NAME = /^[A-Za-z0-9][A-Za-z0-9_.-]*$/;
const LOCALE_ENVIRONMENT_KEYS = ["LANG", "LC_ALL", "LC_CTYPE"];

export class OciRuntimeUnavailableError extends Error {
  constructor(runtimeCandidates) {
    super(`No OCI runtime is available (${runtimeCandidates.join(", ")})`);
    this.name = "OciRuntimeUnavailableError";
    this.code = "oci-runtime-unavailable";
  }
}

function assertMountSource(path, name) {
  if (typeof path !== "string" || path.length === 0) throw new TypeError(`${name} must be a non-empty mount source path`);
  if (/[\0,\r\n]/.test(path)) throw new TypeError(`${name} must be a safe mount source path`);
}

function assertPositiveInteger(value, name) {
  if (!Number.isInteger(value) || value <= 0) throw new TypeError(`${name} must be a positive integer`);
}

function validateOptions(options) {
  if (!options || typeof options !== "object") throw new TypeError("options must be an object");
  const {
    image, resources, command, args, cwd, env, timeoutMs,
    privateDataRoot, graceMs = DEFAULT_GRACE_MS, signal,
    runtimeCandidates = DEFAULT_RUNTIME_CANDIDATES, runProcessFn = runProcess,
    uid = process.getuid?.() ?? 1000, gid = process.getgid?.() ?? 1000,
    randomUUIDFn = randomUUID,
  } = options;
  if (typeof image !== "string" || !OCI_IMAGE.test(image)) throw new TypeError("image must be an immutable OCI image digest");
  if (!resources || typeof resources !== "object" || Array.isArray(resources)) throw new TypeError("resources must be an object");
  assertPositiveInteger(resources.memoryMb, "resources.memoryMb");
  if (typeof command !== "string" || command.length === 0 || command.includes("\0")) throw new TypeError("command must be a non-empty NUL-free string");
  if (!Array.isArray(args) || args.some((value) => typeof value !== "string" || value.includes("\0"))) throw new TypeError("args must be a NUL-free string array");
  assertMountSource(cwd, "cwd");
  if (!env || typeof env !== "object" || Array.isArray(env)) throw new TypeError("env must be an object");
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new TypeError("timeoutMs must be positive");
  if (!Number.isFinite(graceMs) || graceMs < 0) throw new TypeError("graceMs must be non-negative");
  if (privateDataRoot !== undefined) assertMountSource(privateDataRoot, "privateDataRoot");
  if (!Array.isArray(runtimeCandidates) || runtimeCandidates.length === 0 || runtimeCandidates.some((value) => typeof value !== "string" || value.length === 0)) throw new TypeError("runtimeCandidates must be a non-empty string array");
  if (typeof runProcessFn !== "function") throw new TypeError("runProcessFn must be a function");
  if (!Number.isInteger(uid) || uid < 0 || !Number.isInteger(gid) || gid < 0) throw new TypeError("uid and gid must be non-negative integers");
  if (typeof randomUUIDFn !== "function") throw new TypeError("randomUUIDFn must be a function");

  const runId = randomUUIDFn();
  if (typeof runId !== "string" || !CONTAINER_NAME.test(runId)) throw new TypeError("randomUUIDFn must return a safe container-name fragment");
  return { image, resources, command, args, cwd, env, timeoutMs, privateDataRoot, graceMs, signal, runtimeCandidates, runProcessFn, uid, gid, name: `autoresearch-${runId}` };
}

function runnerOptions({ runtime, args, cwd, env, timeoutMs, graceMs, signal }) {
  return { command: runtime, args, cwd, env, timeoutMs, graceMs, signal };
}

async function selectRuntime(options) {
  for (const runtime of options.runtimeCandidates) {
    try {
      await options.runProcessFn(runnerOptions({ ...options, runtime, args: ["version"] }));
      return runtime;
    } catch (error) {
      if (error?.code !== "ENOENT") throw error;
    }
  }
  throw new OciRuntimeUnavailableError(options.runtimeCandidates);
}

function containerEnvironment(env, privateDataRoot) {
  const values = [];
  for (const key of LOCALE_ENVIRONMENT_KEYS) if (typeof env[key] === "string") values.push(`--env=${key}=${env[key]}`);
  if (privateDataRoot !== undefined) values.push("--env=AUTORESEARCH_PRIVATE_ROOT=/private");
  return values;
}

function runArguments(options) {
  const args = [
    "run", "--rm", "--pull=never", `--name=${options.name}`,
    "--network=none", `--memory=${options.resources.memoryMb}m`,
    `--memory-swap=${options.resources.memoryMb}m`, "--pids-limit=128",
    "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
    `--user=${options.uid}:${options.gid}`, "--workdir=/workspace",
    "--tmpfs=/tmp:rw,nosuid,nodev,size=64m",
    `--mount=type=bind,source=${options.cwd},target=/workspace`,
    ...containerEnvironment(options.env, options.privateDataRoot),
  ];
  if (options.privateDataRoot !== undefined) args.push(`--mount=type=bind,source=${options.privateDataRoot},target=/private,readonly`);
  return [...args, options.image, options.command, ...options.args];
}

export async function runOciProcess(options) {
  const validated = validateOptions(options);
  const runtime = await selectRuntime(validated);
  try {
    return await validated.runProcessFn(runnerOptions({ ...validated, runtime, args: runArguments(validated) }));
  } finally {
    try {
      await validated.runProcessFn(runnerOptions({
        ...validated,
        runtime,
        args: ["rm", "-f", validated.name],
        timeoutMs: Math.min(validated.timeoutMs, CLEANUP_TIMEOUT_MS),
        graceMs: Math.min(validated.graceMs, CLEANUP_TIMEOUT_MS),
        signal: undefined,
      }));
    } catch {
      // A failed best-effort cleanup must not conceal the command's outcome.
    }
  }
}
