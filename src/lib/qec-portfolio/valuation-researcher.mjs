import {
  COMMON_ECONOMIC_EVIDENCE,
  getQecPortfolioProblem,
  QEC_PORTFOLIO_PROBLEMS,
} from "./catalog.mjs";

const OPERATOR_SOURCE = {
  id: "operator-assumption",
  url: "https://research-loop.local/qec-portfolio",
  locator: "User-approved QEC portfolio evaluation policy, 2026-07-29.",
  kind: "operator-assumption",
};

const CAPTURABLE_VALUE_REASON = "No problem-specific pricing, licensing, contract, product-margin, or willingness-to-pay source has been identified.";
const VALUATION_PERSISTENT_ID_OVERRIDES = Object.freeze({
  "Prob-004": Object.freeze(["doi:10.1038/s41467-026-73331-6"]),
  "Prob-007": Object.freeze(["doi:10.1103/PhysRevLett.132.100603"]),
  "Prob-008": Object.freeze(["doi:10.1103/PhysRevX.14.011051"]),
  "Prob-014": Object.freeze(["doi:10.1103/PhysRevLett.132.100603"]),
});

export const PROB_001_VALUATION_PROFILE = Object.freeze({
  id: "Prob-001",
  title: "AutoQEC CSS Distance Campaign",
  summary: "Imported AutoQEC CSS-distance experimental audit record.",
  technicalAnchors: Object.freeze([Object.freeze({
    id: "anchor-fast-quantum-distance-2026",
    persistentId: "doi:10.1145/3795877",
    title: "Fast Algorithms and Implementations for Computing the Minimum Distance of Quantum Codes",
    sourceUrl: "https://doi.org/10.1145/3795877",
    relevanceRationale: "Direct published baseline for fast quantum-code minimum-distance computation.",
  }), Object.freeze({
    id: "anchor-qdistrnd-2022",
    persistentId: "doi:10.21105/joss.04120",
    title: "QDistRnd: A GAP package for computing the distance of quantum error-correcting codes",
    sourceUrl: "https://doi.org/10.21105/joss.04120",
    relevanceRationale: "Published open-software baseline for randomized quantum-code distance computation.",
  })]),
});

function catalogProfile(record) {
  if (!record) return record;
  const overrides = VALUATION_PERSISTENT_ID_OVERRIDES[record.id] ?? null;
  return {
    id: record.id,
    title: record.title,
    summary: record.summary,
    technicalAnchors: [record.technicalAnchor].map((anchor, index) => ({
      ...anchor,
      persistentId: overrides?.[index] ?? anchor.persistentId,
    })),
  };
}

function approvedProfile(problemId, catalog = null) {
  if (problemId === PROB_001_VALUATION_PROFILE.id) return PROB_001_VALUATION_PROFILE;
  const record = catalog === null
    ? getQecPortfolioProblem(problemId)
    : catalog.find((item) => item?.id === problemId);
  return catalogProfile(record);
}

function matchesApprovedCatalog(catalog) {
  return Array.isArray(catalog)
    && JSON.stringify(catalog) === JSON.stringify(QEC_PORTFOLIO_PROBLEMS);
}

function pointEvidence(id, value, unit) {
  return {
    id,
    state: "known",
    interval: { low: value, base: value, high: value },
    unit,
    visibility: "public",
    evidenceState: "reported",
    evidenceTier: "assumption",
    sourceIds: [OPERATOR_SOURCE.id],
    sources: [structuredClone(OPERATOR_SOURCE)],
  };
}

function unknownEvidence(id, reason) {
  return { id, state: "unknown", reason };
}

function candidateForProfile({ profile, quantumScope }) {
  const atomicInputs = [
    pointEvidence("attempt-budget", 200, "count"),
    pointEvidence("wall-clock-budget", 8, "hours"),
    pointEvidence("allowed-secondary-metric-regression", 0.05, "fraction"),
    unknownEvidence("technical-success", "The sealed gate has not run."),
  ];
  return {
    schemaVersion: 1,
    problemId: profile.id,
    scope: {
      status: quantumScope.status,
      domain: quantumScope.domain,
      quantumArea: quantumScope.quantumArea,
    },
    anchorCandidates: structuredClone(profile.technicalAnchors),
    paperInclusionRules: {
      include: ["Directly evaluates the declared QEC problem, baseline, gate metric, or implementation constraint."],
      exclude: ["General quantum-computing work without a direct QEC connection.", "Market forecasts used as technical or novelty evidence."],
    },
    technicalStages: [
      { id: "freeze-baseline", description: "Freeze the baseline, benchmark, and primary metric before optimization." },
      { id: "bounded-search", description: "Run at most 200 attempts or eight wall-clock hours." },
      { id: "sealed-evaluation", description: "Evaluate once on a sealed holdout and report regressions." },
    ],
    classicalBaseline: {
      description: "The declared implementation and metric reported by the approved technical anchor, frozen before optimization.",
      sourceUrl: profile.technicalAnchors[0].sourceUrl,
    },
    marketEvidence: structuredClone(COMMON_ECONOMIC_EVIDENCE),
    atomicInputs,
    materialAssumptions: [
      {
        id: "sealed-evaluation",
        question: "What exact sealed benchmark composition will be frozen before a campaign?",
        proposedValue: unknownEvidence("sealed-evaluation-value", "Exact sealed benchmark composition is unknown."),
        sensitivityRank: 1,
        confirmationRequired: false,
      },
      {
        id: "capturable-value",
        question: "What problem-specific capturable value is supported by public evidence?",
        proposedValue: unknownEvidence("capturable-value", CAPTURABLE_VALUE_REASON),
        sensitivityRank: 2,
        confirmationRequired: false,
      },
      {
        id: "fixed-budget",
        question: "Is the eight-hour wall-clock budget fixed for this advisory evaluation?",
        proposedValue: pointEvidence("fixed-budget-value", 8, "hours"),
        sensitivityRank: 3,
        confirmationRequired: false,
      },
    ],
    warnings: [
      "External valuation evidence is not trusted knowledge; it is frozen for local advisory assessment only.",
      "Citation counts measure scientific attention, not novelty or solution quality.",
      "The McKinsey range and IBM investment are broad enabling signals, not problem-specific capturable value.",
      "Technical success remains uncertain until the declared gate is run on a sealed benchmark.",
    ],
  };
}

export function buildApprovedValuationCandidate({ problem, quantumScope }) {
  const profile = approvedProfile(problem?.id);
  if (!profile) throw new RangeError(`${problem?.id} is not an approved QEC portfolio problem.`);
  return candidateForProfile({ profile, quantumScope });
}

export function createQecPortfolioValuationResearcher({ catalog = QEC_PORTFOLIO_PROBLEMS } = {}) {
  const catalogIsApproved = matchesApprovedCatalog(catalog);
  return Object.freeze({
    async run({ problem, quantumScope }) {
      if (!catalogIsApproved) {
        return {
          ok: false,
          code: "INVALID_APPROVED_CATALOG",
          message: "Supplied catalog does not match the approved QEC portfolio.",
        };
      }
      const profile = approvedProfile(problem?.id);
      if (!profile) {
        return {
          ok: false,
          code: "UNAPPROVED_PORTFOLIO_PROBLEM",
          message: `${problem?.id} is not an approved QEC portfolio problem.`,
        };
      }
      return { ok: true, candidate: candidateForProfile({ profile, quantumScope }), stderr: "", eventsText: "" };
    },
  });
}
