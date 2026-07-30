import { readFile } from "node:fs/promises";
import { join } from "node:path";

import { validateAssessmentEnvelope } from "../assessments/contract.mjs";
import { summarizeCompletedAssessment } from "../assessments/contract.mjs";
import { createArtifactStore } from "../assessments/artifact-store.mjs";
import { renderAssessmentReport, escapeHtml } from "../assessments/html-report.mjs";
import { buildInputSnapshot } from "../assessments/input-snapshot.mjs";
import { ASSESSMENT_SCHEMA_PATH_SEGMENTS } from "../assessments/policy.mjs";
import { resolveExistingRunDir } from "../assessments/paths.mjs";
import { SCIENTIFIC_DEMAND_FORMULA_ID } from "../valuations/citations.mjs";

export const VALUATION_ONLY_NOTICE = "Qualitative assessment retained from a prior completed run; quantitative valuation refreshed from the bound Scientific Demand snapshot.";

const CJK = /[\u3400-\u9fff]/;
const SCORE_RANGE = /\b\d+(?:\.\d+)?\s*\(\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?\s*\)/;

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function cloneJson(value) {
  return value === undefined ? undefined : structuredClone(value);
}

function visibleText(value) {
  return typeof value === "string" ? value : JSON.stringify(value ?? null);
}

function knownPoint(value) {
  return value?.state === "known"
    && Number.isFinite(value.interval?.low)
    && Number.isFinite(value.interval?.base)
    && Number.isFinite(value.interval?.high);
}

function quantitativeValueState(value) {
  return value?.state === "known" || value?.state === "unknown";
}

function requireCurrentSnapshot(valuationSnapshot) {
  const manifest = valuationSnapshot?.manifest;
  const citation = manifest?.citation;
  const demand = citation?.scientificDemand ?? citation?.scientificAttention;
  if (!isRecord(manifest)
    || manifest.complete !== true
    || citation?.formulaId !== SCIENTIFIC_DEMAND_FORMULA_ID
    || !knownPoint(demand)
    || !quantitativeValueState(citation?.momentum)
    || !Number.isFinite(citation.coverage)
    || !isRecord(citation.components)
    || !["low", "medium", "high"].includes(citation.evidenceConfidence)
    || !Number.isInteger(citation.paperCount)) {
    throw new Error(`A complete verified ${SCIENTIFIC_DEMAND_FORMULA_ID} valuation snapshot is required.`);
  }
  return { manifest, citation, demand };
}

function snapshotFreshness(manifest) {
  return manifest.freshness === "stale" ? "stale" : "fresh";
}

export function sourceAssessmentQualifies({ run, input, assessment, report }) {
  const envelope = assessment?.envelope;
  const payload = visibleText({ summary: run?.summary, envelope });
  return run?.status === "completed"
    && Boolean(run.summary)
    && input?.schemaVersion === 2
    && typeof input.valuation?.snapshotId === "string"
    && envelope?.outcome === "assessment"
    && envelope.language === "en"
    && envelope.assessment?.schemaVersion === 2
    && envelope.assessment?.visibility === "public"
    && !CJK.test(payload)
    && !CJK.test(visibleText(report));
}

export function createValuationOnlyEnvelope({ sourceEnvelope, valuationSnapshot }) {
  const { manifest, citation, demand } = requireCurrentSnapshot(valuationSnapshot);
  const envelope = cloneJson(sourceEnvelope);
  if (envelope?.outcome !== "assessment" || !isRecord(envelope.assessment)) {
    throw new Error("A completed assessment envelope is required.");
  }
  const assessment = envelope.assessment;
  assessment.quantitativeEvidence = {
    domain: "quantum-computing",
    quantumArea: "error-correction-and-fault-tolerance",
    snapshot: {
      snapshotId: manifest.snapshotId,
      contentHash: manifest.contentHash,
      createdAt: manifest.createdAt,
      freshness: snapshotFreshness(manifest),
      visibility: manifest.visibility ?? "public",
    },
    scientificAttention: {
      value: cloneJson(demand),
      momentum: cloneJson(citation.momentum),
      coverage: citation.coverage,
      concentration: citation.concentration ?? null,
      warnings: [...(citation.warnings ?? [])],
      formulaId: SCIENTIFIC_DEMAND_FORMULA_ID,
      components: cloneJson(citation.components),
      evidenceConfidence: citation.evidenceConfidence,
      paperCount: citation.paperCount,
    },
    technicalFeasibility: cloneJson(manifest.feasibility ?? { state: "unknown", reason: "No sealed technical gate has been measured." }),
    socialValue: cloneJson(manifest.value ?? { state: "unknown", reason: "No problem-specific social-value model has been identified." }),
    capturableValue: cloneJson(manifest.value ?? { state: "unknown", reason: "No problem-specific capturable value model has been identified." }),
    informationValue: { state: "unknown", reason: "No problem-specific sample-information value model has been identified." },
    scoreAnchors: [],
    sensitivity: [],
    assumptions: [VALUATION_ONLY_NOTICE],
    warnings: [
      ...(manifest.confirmedCandidate?.warnings ?? []),
      ...(citation.warnings ?? []),
    ],
  };

  const validation = validateAssessmentEnvelope(envelope);
  if (!validation.ok) {
    const error = new Error(`Invalid valuation-only assessment envelope: ${validation.errors.join(" ")}`);
    error.code = "INVALID_VALUATION_ONLY_ENVELOPE";
    throw error;
  }
  return validation.value;
}

export function createValuationOnlyDerivation({ problemId, run, sourceRun, sourceInput, valuationSnapshot }) {
  return {
    schemaVersion: 1,
    kind: "qec-valuation-only-refresh",
    problemId,
    runId: run.runId,
    sourceRunId: sourceRun.runId,
    sourceSnapshotId: sourceInput.valuation.snapshotId,
    refreshedSnapshotId: valuationSnapshot.manifest.snapshotId,
    notice: VALUATION_ONLY_NOTICE,
    createdAt: run.createdAt,
  };
}

export function assertValuationOnlyVisibleReport(html) {
  const text = visibleText(html);
  if (CJK.test(text)) throw new Error("Derived report contains visible Chinese text.");
  if (/\bUnknown\b/.test(text)) throw new Error("Derived report contains visible Unknown text.");
  if (/\bPending\b/.test(text)) throw new Error("Derived report contains visible Pending text.");
  if (SCORE_RANGE.test(text)) throw new Error("Derived report contains a visible score range.");
}

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

async function readJsonIfPresent(path) {
  try {
    return await readJson(path);
  } catch (error) {
    if (error.code === "ENOENT") return null;
    throw error;
  }
}

function runTime(run) {
  const value = Date.parse(run?.updatedAt ?? run?.createdAt ?? "");
  return Number.isFinite(value) ? value : 0;
}

function newestFirst(runs) {
  return [...runs].sort((left, right) => runTime(right) - runTime(left) || String(right.runId).localeCompare(String(left.runId)));
}

async function readRunArtifacts(rootDir, problemId, runId) {
  const runDir = await resolveExistingRunDir(rootDir, problemId, runId);
  const [run, input, assessment, report] = await Promise.all([
    readJson(join(runDir, "run.json")),
    readJson(join(runDir, "input.json")),
    readJson(join(runDir, "assessment.json")),
    readFile(join(runDir, "report.html"), "utf8"),
  ]);
  return { run, input, assessment, report, runDir };
}

async function readDerivation(rootDir, problemId, runId) {
  const runDir = await resolveExistingRunDir(rootDir, problemId, runId);
  return readJsonIfPresent(join(runDir, "derivation.json"));
}

export async function findLatestCompletedSourceRun({ rootDir, store, problemId, excludeSnapshotId }) {
  for (const candidate of newestFirst(await store.listRuns(problemId))) {
    if (candidate.status !== "completed" || !candidate.summary) continue;
    try {
      const artifacts = await readRunArtifacts(rootDir, problemId, candidate.runId);
      if (artifacts.input?.valuation?.snapshotId === excludeSnapshotId) continue;
      if (sourceAssessmentQualifies(artifacts)) return artifacts;
    } catch {
      // Incomplete immutable runs are retained for audit but are not valid sources.
    }
  }
  return null;
}

async function findExistingDerivedRun({ rootDir, store, problemId, sourceRunId, snapshotId }) {
  for (const run of newestFirst(await store.listRuns(problemId))) {
    if (run.status !== "completed" || !run.summary) continue;
    try {
      const derivation = await readDerivation(rootDir, problemId, run.runId);
      if (derivation?.kind === "qec-valuation-only-refresh"
        && derivation.sourceRunId === sourceRunId
        && derivation.refreshedSnapshotId === snapshotId
        && derivation.notice === VALUATION_ONLY_NOTICE) return run;
    } catch {
      // A malformed provenance file prevents reuse but does not affect older artifacts.
    }
  }
  return null;
}

function withProvenanceNotice(html) {
  const notice = `<p class="muted"><strong>Valuation-only refresh:</strong> ${escapeHtml(VALUATION_ONLY_NOTICE)}</p>`;
  return html.includes("<main>")
    ? html.replace("<main>", `<main>\n  ${notice}`)
    : `${notice}\n${html}`;
}

export async function refreshValuationOnlyProblem({
  rootDir,
  repository,
  store = createArtifactStore({ rootDir }),
  problemId,
  snapshot,
  now = () => new Date(),
} = {}) {
  requireCurrentSnapshot(snapshot);
  const problem = repository?.getProblem?.(problemId);
  if (!problem) {
    const error = new Error(`Problem ${problemId} was not found.`);
    error.code = "UNKNOWN_PROBLEM";
    throw error;
  }
  const source = await findLatestCompletedSourceRun({
    rootDir,
    store,
    problemId,
    excludeSnapshotId: snapshot.manifest.snapshotId,
  });
  if (!source) {
    const error = new Error(`No completed public English source assessment found for ${problemId}.`);
    error.code = "SOURCE_ASSESSMENT_REQUIRED";
    throw error;
  }

  const existing = await findExistingDerivedRun({
    rootDir,
    store,
    problemId,
    sourceRunId: source.run.runId,
    snapshotId: snapshot.manifest.snapshotId,
  });
  if (existing) {
    return {
      status: "verified-existing",
      problemId,
      runId: existing.runId,
      sourceRunId: source.run.runId,
      snapshotId: snapshot.manifest.snapshotId,
    };
  }

  const run = await store.createAcceptedRun({ problemId });
  const envelope = createValuationOnlyEnvelope({
    sourceEnvelope: source.assessment.envelope,
    valuationSnapshot: snapshot,
  });
  const validation = validateAssessmentEnvelope(envelope);
  if (!validation.ok) {
    const error = new Error(`Invalid valuation-only assessment envelope: ${validation.errors.join(" ")}`);
    error.code = "INVALID_VALUATION_ONLY_ENVELOPE";
    throw error;
  }
  const skillPath = join(rootDir, "skills", "assess-research-problem", "SKILL.md");
  const schemaPath = join(rootDir, ...ASSESSMENT_SCHEMA_PATH_SEGMENTS);
  const input = await buildInputSnapshot({
    rootDir,
    problem,
    envelope,
    skillPath,
    schemaPath,
    valuationSnapshot: snapshot,
    now: now(),
  });
  const computed = validation.computed;
  const reportHtml = withProvenanceNotice(renderAssessmentReport({ run, input, envelope, computed }));
  assertValuationOnlyVisibleReport(reportHtml);
  const summary = summarizeCompletedAssessment({ run, envelope, computed, input });
  const derivation = createValuationOnlyDerivation({
    problemId,
    run,
    sourceRun: source.run,
    sourceInput: source.input,
    valuationSnapshot: snapshot,
  });
  await store.writeTerminalArtifacts(run, {
    status: "completed",
    input,
    assessment: { envelope, computed },
    summary,
    reportHtml,
    derivation,
    eventsText: `${JSON.stringify({ type: "valuation-only-refresh", sourceRunId: source.run.runId, snapshotId: snapshot.manifest.snapshotId })}\n`,
    stderr: "",
  });
  return {
    status: "completed",
    problemId,
    runId: run.runId,
    sourceRunId: source.run.runId,
    snapshotId: snapshot.manifest.snapshotId,
  };
}
