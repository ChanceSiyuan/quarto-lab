import { createHash } from "node:crypto";
import { lstat, readFile } from "node:fs/promises";
import { join } from "node:path";

import { validateInfrastructureManifest } from "./preparation-contract.mjs";
import { runProcess } from "./process.mjs";

export const PREFLIGHT_CHECK_IDS = Object.freeze([
  "manifest-integrity", "clean-environment", "candidate-api", "public-smoke",
  "correctness-negative", "hard-code-negative", "crash-negative", "timeout-negative",
  "containment", "private-data-isolation", "baseline-reproduction", "score-arithmetic",
  "reproducibility",
]);

const MAX_DIAGNOSTIC_LENGTH = 1024;
const HOST_ENVIRONMENT_KEYS = ["PATH", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "TERM"];
const EVALUATOR_CHECKS = new Set(["correctness-negative", "hard-code-negative", "baseline-reproduction", "score-arithmetic", "reproducibility"]);

function fixedEnvironment(source) {
  const env = {};
  for (const key of HOST_ENVIRONMENT_KEYS) if (typeof source?.[key] === "string") env[key] = source[key];
  return Object.freeze(env);
}

function escapeDiagnostic(value) {
  return String(value ?? "preflight command failed")
    .replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;").replaceAll("'", "&#39;").replace(/[\r\n\t]+/g, " ")
    .slice(0, MAX_DIAGNOSTIC_LENGTH);
}

function timestamp(now) {
  const value = typeof now === "function" ? now() : new Date();
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.valueOf())) throw new TypeError("now must produce a valid date");
  return date.toISOString();
}

function check(id, status, started, now, summary, diagnostics = []) {
  const completed = typeof now === "function" ? now() : new Date();
  const completedAt = completed instanceof Date ? completed : new Date(completed);
  if (Number.isNaN(completedAt.valueOf())) throw new TypeError("now must produce a valid date");
  return { id, status, durationMs: Math.max(0, completedAt.valueOf() - started.valueOf()), summary, diagnostics: diagnostics.map(escapeDiagnostic) };
}

function sha256(value) { return createHash("sha256").update(value).digest("hex"); }

async function verifyRegularFile(path, expectedDigest, expectedSize) {
  const info = await lstat(path);
  if (!info.isFile() || info.isSymbolicLink()) throw new Error("expected a regular file");
  const content = await readFile(path);
  if (expectedSize !== undefined && content.length !== expectedSize) throw new Error("file size disagrees with manifest");
  if (sha256(content) !== expectedDigest) throw new Error("SHA-256 digest disagrees with manifest");
}

function datasetPath(stageDir, privateDataRoot, name, manifest) {
  return join(name === "public" ? stageDir : privateDataRoot, manifest.datasets[name].manifestPath);
}

function commandFor(manifest, id) {
  if (id === "containment") return manifest.commands.containmentCheck;
  if (id === "baseline-reproduction") return manifest.commands.reproduceBaseline;
  if (EVALUATOR_CHECKS.has(id)) return manifest.commands.evaluateDevelopment;
  return manifest.commands.publicCheck;
}

function outcomePasses(id, outcome) {
  if (!outcome || typeof outcome !== "object") return false;
  if (id === "hard-code-negative") return outcome.ok === false;
  if (id === "score-arithmetic") return outcome.ok === true && Number.isFinite(outcome.score) && Array.isArray(outcome.components) && outcome.components.length > 0 && outcome.components.every(Number.isFinite) && outcome.components.reduce((total, value) => total + value, 0) === outcome.score;
  return outcome.ok === true;
}

function baselineIdentity(outcome) {
  const baseline = outcome?.baseline;
  if (!baseline || typeof baseline !== "object" || typeof baseline.id !== "string" || baseline.id.length === 0 || !/^[a-f0-9]{64}$/.test(baseline.digest) || !Number.isFinite(baseline.score)) return null;
  return { id: baseline.id, digest: baseline.digest, score: baseline.score };
}

async function runCommand({ id, stageDir, manifest, privateDataRoot, processRunner, env }) {
  const command = commandFor(manifest, id);
  const evaluator = EVALUATOR_CHECKS.has(id);
  const options = {
    command: command[0], args: [...command.slice(1), "--preflight-check", id], cwd: stageDir,
    env, timeoutMs: manifest.resources.attemptTimeoutSeconds * 1000, shell: false,
  };
  if (evaluator) Object.assign(options, { privateDataRoot });
  const result = await processRunner(options);
  try { return JSON.parse(result.stdout); } catch { throw new Error("command did not emit a JSON result"); }
}

export async function runInfrastructurePreflight({ stageDir, manifest, privateDataRoot, processRunner = runProcess, now = () => new Date(), environment = process.env }) {
  if (typeof stageDir !== "string" || !stageDir || typeof privateDataRoot !== "string" || !privateDataRoot) throw new TypeError("stageDir and privateDataRoot are required");
  if (typeof processRunner !== "function") throw new TypeError("processRunner must be a function");
  const startedDate = typeof now === "function" ? now() : new Date();
  const started = startedDate instanceof Date ? startedDate : new Date(startedDate);
  const startedAt = timestamp(() => started);
  const checks = [];
  const env = fixedEnvironment(environment);
  let validated;
  try {
    validated = validateInfrastructureManifest(manifest);
    for (const file of validated.files) await verifyRegularFile(join(stageDir, file.path), file.sha256, file.size);
    for (const name of ["public", "development", "blind"]) await verifyRegularFile(datasetPath(stageDir, privateDataRoot, name, validated), validated.datasets[name].digest);
    checks.push(check("manifest-integrity", "passed", started, now, "Manifest, files, and dataset digests match."));
  } catch (error) {
    checks.push(check("manifest-integrity", "failed", started, now, "Manifest integrity verification failed.", ["Integrity verification did not match the frozen manifest."]));
    return report(validated ?? manifest, startedAt, timestamp(now), null, checks);
  }
  checks.push(check("clean-environment", "passed", started, now, "Commands use the fixed host environment."));

  for (const id of PREFLIGHT_CHECK_IDS.slice(2)) {
    try {
      const outcome = await runCommand({ id, stageDir, manifest: validated, privateDataRoot, processRunner, env });
      let passed = outcomePasses(id, outcome);
      if (id === "baseline-reproduction") {
        const repeated = await runCommand({ id, stageDir, manifest: validated, privateDataRoot, processRunner, env });
        const first = baselineIdentity(outcome);
        const second = baselineIdentity(repeated);
        passed = outcome.ok === true && repeated.ok === true && first !== null && second !== null && JSON.stringify(first) === JSON.stringify(second);
      }
      if (id === "reproducibility") {
        const repeated = await runCommand({ id, stageDir, manifest: validated, privateDataRoot, processRunner, env });
        passed = passed && JSON.stringify(outcome) === JSON.stringify(repeated);
      }
      const evaluator = EVALUATOR_CHECKS.has(id);
      const diagnostic = evaluator ? "Evaluator reported an unsuccessful result." : outcome.diagnostics ?? JSON.stringify(outcome);
      checks.push(check(id, passed ? "passed" : "failed", started, now, passed ? "Command outcome met the preflight expectation." : "Command outcome failed the preflight expectation.", passed ? [] : [diagnostic]));
      if (id === "containment" && !passed) break;
    } catch (error) {
      checks.push(check(id, "failed", started, now, "Preflight command failed.", [EVALUATOR_CHECKS.has(id) ? "Evaluator command failed." : error.message]));
      if (id === "containment") break;
    }
  }
  return report(validated, startedAt, timestamp(now), validated.resources.attemptTimeoutSeconds + validated.resources.terminationGraceSeconds, checks);
}

function report(manifest, startedAt, completedAt, attemptRuntimeUpperBoundSeconds, checks) {
  return {
    schemaVersion: 1, problemId: manifest?.problemId ?? null, infrastructureId: manifest?.id ?? null,
    status: checks.every((item) => item.status === "passed") ? "passed" : "failed",
    startedAt, completedAt, attemptRuntimeUpperBoundSeconds, checks,
  };
}
