import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join, relative, resolve } from "node:path";

import { ASSESSMENT_POLICY_VERSION } from "./policy.mjs";
import { evaluateValuationFreshness } from "../valuations/freshness.mjs";
import { canonicalJson } from "../valuations/snapshot-store.mjs";

export function sha256Text(text) {
  return createHash("sha256").update(text).digest("hex");
}

export async function hashFile(path) {
  try {
    return sha256Text(await readFile(path, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

function cloneJson(value) {
  return value === undefined ? undefined : structuredClone(value);
}

export function buildValuationInput(valuationSnapshot, { now = new Date() } = {}) {
  if (!valuationSnapshot) return null;
  const manifest = valuationSnapshot.manifest ?? {};
  const valuationInput = {
    snapshotId: manifest.snapshotId,
    contentHash: manifest.contentHash,
    snapshotHash: sha256Text(canonicalJson(valuationSnapshot)),
    visibility: manifest.visibility ?? "public",
    freshness: evaluateValuationFreshness(valuationSnapshot, now),
    recalculationInputs: cloneJson(valuationSnapshot.recalculationInputs ?? {
      manifest,
      papers: valuationSnapshot.papers ?? [],
      marketEvidence: valuationSnapshot.marketEvidence ?? [],
    }),
  };
  return valuationInput;
}

export async function buildInputSnapshot({ rootDir, problem, envelope, skillPath, schemaPath, selectedAlternative = null, valuationSnapshot = null, valuationInput = null, now = new Date() }) {
  const root = resolve(rootDir);
  const problemDir = join(root, "problems", problem.id);
  const resolver = envelope.knowledgeResolution;
  const bundle = [];
  for (const orderedPath of resolver.orderedFiles ?? []) {
    bundle.push({
      path: orderedPath,
      hash: await hashFile(join(root, orderedPath)),
    });
  }
  const frozenValuation = valuationInput ?? buildValuationInput(valuationSnapshot, { now });
  return {
    schemaVersion: frozenValuation ? 2 : 1,
    policyVersion: ASSESSMENT_POLICY_VERSION,
    problemId: problem.id,
    problemTitle: problem.title,
    problemSummary: problem.summary,
    problemJsonHash: await hashFile(join(problemDir, "problem.json")),
    problemMdHash: await hashFile(join(problemDir, "problem.md")),
    skillPath: relative(root, skillPath),
    skillHash: await hashFile(skillPath),
    schemaPath: relative(root, schemaPath),
    schemaHash: await hashFile(schemaPath),
    resolver: {
      query: resolver.query,
      status: resolver.status,
      topic: resolver.topic,
      orderedFiles: [...(resolver.orderedFiles ?? [])],
      ...(selectedAlternative?.page ? { selectedPage: selectedAlternative.page } : {}),
    },
    bundle,
    ...(frozenValuation ? { valuation: frozenValuation } : {}),
  };
}
