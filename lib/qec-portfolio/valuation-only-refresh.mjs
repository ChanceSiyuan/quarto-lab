import { validateAssessmentEnvelope } from "../assessments/contract.mjs";
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

function requireCurrentSnapshot(valuationSnapshot) {
  const manifest = valuationSnapshot?.manifest;
  const citation = manifest?.citation;
  const demand = citation?.scientificDemand ?? citation?.scientificAttention;
  if (!isRecord(manifest)
    || manifest.complete !== true
    || citation?.formulaId !== SCIENTIFIC_DEMAND_FORMULA_ID
    || !knownPoint(demand)
    || !knownPoint(citation?.momentum)
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
