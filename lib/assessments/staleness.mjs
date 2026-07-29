import { join } from "node:path";

import { hashFile, sha256Text } from "./input-snapshot.mjs";
import { canonicalJson } from "../valuations/snapshot-store.mjs";

function sameJson(left, right) {
  return JSON.stringify(left) === JSON.stringify(right);
}

export async function evaluateAssessmentStaleness({ rootDir, input, resolveKnowledge, currentHashes = null, valuationStore = null }) {
  const reasons = [];
  const advisoryReasons = [];
  const hashes = currentHashes ?? {
    problemJsonHash: await hashFile(join(rootDir, "problems", input.problemId, "problem.json")),
    problemMdHash: await hashFile(join(rootDir, "problems", input.problemId, "problem.md")),
    skillHash: await hashFile(join(rootDir, input.skillPath)),
    schemaHash: await hashFile(join(rootDir, input.schemaPath)),
    bundle: await Promise.all((input.bundle ?? []).map(async (item) => ({
      path: item.path,
      hash: await hashFile(join(rootDir, item.path)),
    }))),
  };
  for (const key of ["problemJsonHash", "problemMdHash", "skillHash", "schemaHash"]) {
    if (hashes[key] !== input[key]) reasons.push(`${key} changed`);
  }
  const resolverNow = await resolveKnowledge(input.resolver.query, input.resolver.selectedPage
    ? { selectedPage: input.resolver.selectedPage }
    : undefined);
  const storedResolver = {
    status: input.resolver.status,
    topic: input.resolver.topic,
    orderedFiles: input.resolver.orderedFiles,
  };
  const currentResolver = {
    status: resolverNow.status,
    topic: resolverNow.status === "match" ? resolverNow.bundle?.topic ?? null : null,
    orderedFiles: resolverNow.status === "match" ? resolverNow.bundle?.orderedFiles ?? [] : [],
  };
  if (!sameJson(storedResolver, currentResolver)) reasons.push("resolver result changed");
  if (!sameJson(input.bundle ?? [], hashes.bundle ?? [])) reasons.push("resolver bundle hash changed");
  if (input.valuation?.snapshotId && valuationStore) {
    try {
      const snapshots = typeof valuationStore.list === "function" ? await valuationStore.list(input.problemId) : [];
      const latest = snapshots.at(-1) ?? null;
      if (latest && latest !== input.valuation.snapshotId) advisoryReasons.push("newer valuation snapshot available");
      const snapshot = await (valuationStore.verify ?? valuationStore.read)?.(input.problemId, input.valuation.snapshotId);
      if (snapshot) {
        if (snapshot.manifest?.contentHash !== input.valuation.contentHash) reasons.push("valuation snapshot content hash changed");
        if (input.valuation.snapshotHash && sha256Text(canonicalJson(snapshot)) !== input.valuation.snapshotHash) reasons.push("valuation snapshot hash changed");
      }
    } catch (error) {
      reasons.push(`valuation snapshot verification failed: ${error.message}`);
    }
  }
  const result = { stale: reasons.length > 0, reasons };
  if (advisoryReasons.length > 0) result.advisoryReasons = advisoryReasons;
  return result;
}
