import {
  buildResearchAttemptDossier,
  buildResearchLedger,
} from "./research-presentation.mjs";

export function buildProblemDetailResearchState({ problem, researchRecord, diagnostics = [] }) {
  if (researchRecord) {
    return {
      kind: "research",
      problem,
      disclaimer: researchRecord.manifest.disclaimer,
      ledger: buildResearchLedger(researchRecord),
    };
  }
  if (diagnostics.length > 0) {
    return {
      kind: "research-diagnostics",
      problem,
      diagnostics: diagnostics.map((item) => ({ ...item })),
    };
  }
  return { kind: "generic", problem };
}

export function buildAttemptDetailResearchState({ problem, researchRecord, attemptId }) {
  const attempt = researchRecord?.attempts.find((item) => item.id === attemptId);
  if (!attempt) return { kind: "not-found", problem };
  return {
    kind: "research-attempt",
    problem,
    dossier: buildResearchAttemptDossier(attempt, researchRecord.manifest),
  };
}
