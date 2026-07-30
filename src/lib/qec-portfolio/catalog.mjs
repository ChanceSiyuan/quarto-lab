import { PROBLEM_ID_PATTERN } from "../problems/schema.mjs";

const CREATED_AT = "2026-07-29T12:33:33.000Z";
const VISIBLE_FIELDS = ["title", "summary", "candidateQuestion", "gateType"];
const RECORD_FIELDS = ["id", "title", "summary", "candidateQuestion", "gateType", "technicalAnchor", "createdAt", "updatedAt"];
const ANCHOR_FIELDS = ["id", "title", "sourceUrl", "persistentId", "relevanceRationale"];
const ANCHOR_COPY_FIELDS = ["id", "title", "relevanceRationale"];
const TIMESTAMP_FIELDS = ["createdAt", "updatedAt"];
const CJK = /\p{Script=Han}/u;
const EXPECTED_IDS = Array.from({ length: 20 }, (_, index) => `Prob-${String(index + 2).padStart(3, "0")}`);

const APPROVED_ROWS = [
  ["Prob-002", "Finite-Length qLDPC Code Search Under Hardware Constraints", "Search for finite-length qLDPC codes that improve the rate–distance–check-weight–decoder-performance frontier.", "Can automated search outperform declared finite-length baselines on sealed instances?", "finite-length-code-pareto", "Quantum Low-Density Parity-Check Codes", "https://arxiv.org/abs/2510.14090", "doi:10.48550/arXiv.2510.14090", CREATED_AT],
  ["Prob-003", "Circuit-Level qLDPC Decoder Optimization", "Optimize qLDPC decoders under circuit-level noise and bounded runtime.", "Can search improve logical error rate without exceeding latency and memory budgets?", "circuit-level-decoder-benchmark", "An efficient decoder for a linear distance quantum LDPC code", "https://arxiv.org/abs/2206.06557", "doi:10.48550/arXiv.2206.06557", CREATED_AT],
  ["Prob-004", "Real-Time Decoder Tail-Latency Minimization", "Minimize decoder tail latency while preserving logical accuracy.", "Can implementation search improve p95/p99 latency and avoid syndrome backlog?", "tail-latency-decoder-benchmark", "Demonstrating real-time and low-latency quantum error correction with superconducting qubits", "https://arxiv.org/abs/2410.05202", "doi:10.48550/arXiv.2410.05202", CREATED_AT],
  ["Prob-005", "Bounded-Memory Streaming QEC Decoder", "Design a streaming decoder with bounded state and stable throughput.", "Can it match batch-decoder accuracy without unbounded memory or backlog?", "bounded-memory-streaming-benchmark", "Real-Time Quantum Error Correction System Stack: Architecture, Algorithms, and Engineering Practice", "https://arxiv.org/abs/2605.30765", "doi:10.48550/arXiv.2605.30765", CREATED_AT],
  ["Prob-006", "Adaptive Decoding Under Correlated and Drifting Noise", "Adapt decoder parameters to correlated, nonstationary noise.", "Does online adaptation improve held-out logical error rates without leakage from final evaluation?", "noise-drift-holdout", "Statistical mechanical models for quantum codes with correlated noise", "https://arxiv.org/abs/1809.10704", "doi:10.48550/arXiv.1809.10704", CREATED_AT],
  ["Prob-007", "Leakage-Aware Decoder and Reset-Policy Co-Design", "Jointly optimize leakage inference, decoder behavior, and reset placement.", "Can the policy reduce logical failures and cycle cost on held-out leakage traces?", "leakage-reset-policy-benchmark", "Model-based Optimization of Superconducting Qubit Readout", "https://arxiv.org/abs/2308.02079", "doi:10.48550/arXiv.2308.02079", CREATED_AT],
  ["Prob-008", "Erasure-Biased Code–Decoder Co-Design", "Co-design finite codes and decoders for erasure-dominated hardware.", "Can search improve logical error and physical-resource Pareto performance?", "erasure-code-decoder-pareto", "Demonstrating a long-coherence dual-rail erasure qubit using tunable transmons", "https://arxiv.org/abs/2307.08737", "doi:10.48550/arXiv.2307.08737", CREATED_AT],
  ["Prob-009", "Generalizable Neural Decoder with Calibrated Uncertainty", "Train a decoder that transfers across codes and noise shifts while reporting calibrated confidence.", "Can it beat classical baselines on unseen domains?", "cross-domain-neural-decoder", "Toward Uncertainty-Aware and Generalizable Neural Decoding for Quantum LDPC Codes", "https://arxiv.org/abs/2510.06257", "doi:10.48550/arXiv.2510.06257", CREATED_AT],
  ["Prob-010", "Rare-Event Logical Failure Estimation", "Estimate very low logical failure probabilities with auditable uncertainty.", "Can the estimator reduce simulation cost while maintaining calibrated coverage?", "rare-event-estimator-calibration", "Fail fast: techniques to probe rare events in quantum error correction", "https://arxiv.org/abs/2511.15177", "doi:10.48550/arXiv.2511.15177", CREATED_AT],
  ["Prob-011", "Reproducible Cross-Code QEC Benchmark Suite", "Build a reproducible benchmark spanning codes, decoders, and noise models.", "Can it produce implementation-independent rankings with complete audit records?", "cross-code-benchmark-reproducibility", "qecsim — Quantum Error Correction Simulator; citing work: Tailoring surface codes: Improvements in quantum error correction with biased noise", "https://qecsim.github.io/overview.html", "doi:10.25910/x8xw-9077", CREATED_AT],
  ["Prob-012", "Syndrome-Extraction Schedule Search", "Search valid stabilizer-measurement schedules that control error propagation.", "Can automated scheduling reduce logical error and circuit depth on sealed codes?", "syndrome-schedule-benchmark", "AlphaSyndrome: Tackling the Syndrome Measurement Circuit Scheduling Problem for QEC Codes", "https://arxiv.org/abs/2601.12509", "doi:10.48550/arXiv.2601.12509", CREATED_AT],
  ["Prob-013", "Flag-Sharing Ancilla Circuit Synthesis", "Synthesize fault-tolerant flag-sharing syndrome circuits.", "Can search reduce ancilla count and circuit area while passing exhaustive bounded-fault checks?", "flag-circuit-fault-enumeration", "Reducing Quantum Error Correction Overhead with Versatile Flag-Sharing Syndrome Extraction Circuits", "https://arxiv.org/abs/2407.00607", "doi:10.48550/arXiv.2407.00607", CREATED_AT],
  ["Prob-014", "Noise-Aware Stabilizer Measurement Scheduling", "Allocate measurement cadence using heterogeneous and drifting error rates.", "Can adaptive scheduling reduce logical error per unit cycle cost?", "measurement-cadence-benchmark", "Model-based Optimization of Superconducting Qubit Readout", "https://arxiv.org/abs/2308.02079", "doi:10.48550/arXiv.2308.02079", CREATED_AT],
  ["Prob-015", "Lattice-Surgery Routing and Scheduling", "Optimize logical-patch placement, routing, and operation timing.", "Can search reduce spacetime volume while respecting dependencies and factory supply?", "lattice-surgery-scheduling-benchmark", "PureMagic: A Dynamic Scheduler for Lattice Surgery", "https://arxiv.org/abs/2512.06484", "doi:10.48550/arXiv.2512.06484", CREATED_AT],
  ["Prob-016", "Multi-Level Magic-State Factory Optimization", "Optimize factory topology, level count, allocation, and buffering.", "Can search improve the physical-qubit/runtime/error Pareto frontier?", "magic-state-factory-pareto", "Optimizing Multi-level Magic State Factories for Fault-Tolerant Quantum Architectures", "https://arxiv.org/abs/2411.04270", "doi:10.48550/arXiv.2411.04270", CREATED_AT],
  ["Prob-017", "Fault-Tolerant Code-Switching Protocol Synthesis", "Search verified protocols for switching between complementary codes.", "Can synthesis reduce qubit and gate overhead while satisfying bounded-fault correctness?", "code-switching-fault-enumeration", "Experimental fault-tolerant code switching", "https://arxiv.org/abs/2403.13732", "doi:10.48550/arXiv.2403.13732", CREATED_AT],
  ["Prob-018", "Bias-Preserving Logical Operation Co-Optimization", "Co-optimize biased-noise codes, logical operations, and decoding.", "Can search preserve noise bias and reduce logical error across a universal workload?", "bias-preserving-logical-benchmark", "The XZZX Surface Code", "https://arxiv.org/abs/2009.07851", "doi:10.48550/arXiv.2009.07851", CREATED_AT],
  ["Prob-019", "Bosonic–Outer-Code Concatenation Co-Design", "Co-design bosonic inner encodings and discrete outer codes.", "Can search reduce hardware and cycle overhead at a fixed logical-error target?", "bosonic-outer-code-pareto", "Bosonic quantum error correction codes in superconducting quantum circuits", "https://arxiv.org/abs/2010.08699", "doi:10.48550/arXiv.2010.08699", CREATED_AT],
  ["Prob-020", "End-to-End Fault-Tolerant Resource Allocation Under Uncertainty", "Jointly allocate code distances, factories, routing capacity, and error budgets.", "Can robust optimization reduce total cost across uncertain hardware parameters?", "end-to-end-resource-estimation-benchmark", "Optimizing Multi-level Magic State Factories for Fault-Tolerant Quantum Architectures", "https://arxiv.org/abs/2411.04270", "doi:10.48550/arXiv.2411.04270", CREATED_AT],
  ["Prob-021", "Automated Fault-Tolerance Verification for QEC Circuits", "Develop scalable formal verification for stabilizer-code circuits and fault-tolerant logical protocols.", "Can an automated verifier prove bounded-fault correctness or produce minimal counterexamples across a sealed corpus of syndrome-extraction, logical-gate, and code-switching circuits?", "fault-tolerance-formal-verification", "Efficient Formal Verification of Quantum Error Correcting Programs", "https://arxiv.org/abs/2504.07732", "doi:10.48550/arXiv.2504.07732", "2026-07-29T12:36:58.000Z"],
];

function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    for (const nested of Object.values(value)) deepFreeze(nested);
    Object.freeze(value);
  }
  return value;
}

function catalogRecord([id, title, summary, candidateQuestion, gateType, anchorTitle, sourceUrl, persistentId, createdAt]) {
  return {
    id,
    title,
    summary,
    candidateQuestion,
    gateType,
    technicalAnchor: {
      id: `anchor-${id}`,
      title: anchorTitle,
      sourceUrl,
      persistentId,
      relevanceRationale: `This source directly motivates the declared gate for ${title}.${id === "Prob-011" ? " The official qecsim Citing page maps the software documentation to the persistent thesis DOI." : ""}`,
    },
    createdAt,
    updatedAt: createdAt,
  };
}

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function hasExactFields(value, fields) {
  return isRecord(value)
    && Object.keys(value).length === fields.length
    && fields.every((field) => Object.hasOwn(value, field));
}

function nonEmptyString(value) {
  return typeof value === "string" && value.trim() !== "";
}

function validTimestamp(value) {
  return nonEmptyString(value) && !Number.isNaN(Date.parse(value));
}

export const QEC_PORTFOLIO_PROBLEMS = deepFreeze(APPROVED_ROWS.map(catalogRecord));
export const QEC_PORTFOLIO_IDS = deepFreeze(QEC_PORTFOLIO_PROBLEMS.map((record) => record.id));

export const COMMON_ECONOMIC_EVIDENCE = deepFreeze([
  {
    id: "mckinsey-qc-internal-market-2035",
    state: "known",
    interval: { low: 43_000_000_000, base: 57_000_000_000, high: 71_000_000_000 },
    unit: "USD_2035",
    visibility: "public",
    evidenceState: "reported",
    evidenceTier: "authoritative-secondary",
    sourceIds: ["source-mckinsey-quantum-monitor-2026"],
    sources: [{
      id: "source-mckinsey-quantum-monitor-2026",
      url: "https://www.mckinsey.com/capabilities/mckinsey-technology/our-insights/mckinsey-quantum-technology-monitor-2026-a-commercial-tipping-point",
      locator: "The 2035 internal quantum-computing market range is USD 43–71 billion, represented as low/base/high USD 43/57/71 billion in 2035 dollars.",
      kind: "market-report",
    }],
    currency: "USD",
    priceBaseYear: 2035,
    conversionSourceId: "source-mckinsey-quantum-monitor-2026",
    kind: "broad-enabling-market-proxy",
  },
  {
    id: "ibm-quantum-investment-floor-2026",
    state: "known",
    interval: { low: 10_000_000_000, base: 10_000_000_000, high: 10_000_000_000 },
    unit: "USD_2026",
    visibility: "public",
    evidenceState: "reported",
    evidenceTier: "vendor-or-news",
    sourceIds: ["source-ibm-quantum-investment-2026"],
    sources: [{
      id: "source-ibm-quantum-investment-2026",
      url: "https://newsroom.ibm.com/2026-06-02-ibm-commits-more-than-10-billion-to-quantum-computing%2C-funding-its-roadmap-from-todays-leading-systems-to-the-worlds-first-fault-tolerant-quantum-computers",
      locator: "IBM announced more than USD 10 billion over five years, encoded as a USD 10 billion floor, not a point estimate or capturable value, in 2026 dollars.",
      kind: "vendor-announcement",
    }],
    currency: "USD",
    priceBaseYear: 2026,
    conversionSourceId: "source-ibm-quantum-investment-2026",
    kind: "investment-floor",
  },
]);

export function getQecPortfolioProblem(id) {
  return QEC_PORTFOLIO_PROBLEMS.find((record) => record.id === id) ?? null;
}

export function validateQecPortfolioCatalog(records = QEC_PORTFOLIO_PROBLEMS) {
  const errors = [];
  if (!Array.isArray(records) || records.length !== 20) errors.push("Catalog must contain exactly twenty new problems.");
  const list = Array.isArray(records) ? records : [];
  if (JSON.stringify(list.map((record) => record?.id)) !== JSON.stringify(EXPECTED_IDS)) errors.push("Catalog IDs must be contiguous from Prob-002 through Prob-021.");
  for (const record of list) {
    const id = record?.id;
    if (!PROBLEM_ID_PATTERN.test(id)) {
      errors.push(`Invalid problem ID: ${id}`);
      continue;
    }
    const recordKeys = Object.keys(record);
    const recordHasMissingNonTimestampField = RECORD_FIELDS
      .filter((field) => !TIMESTAMP_FIELDS.includes(field))
      .some((field) => !Object.hasOwn(record, field));
    if (recordHasMissingNonTimestampField || recordKeys.some((field) => !RECORD_FIELDS.includes(field))) errors.push(`Catalog record fields are invalid for ${id}.`);
    if (TIMESTAMP_FIELDS.some((field) => !validTimestamp(record[field]))) errors.push(`Registration timestamps are invalid for ${id}.`);
    if (VISIBLE_FIELDS.some((field) => typeof record[field] !== "string" || record[field].trim() === "")) errors.push(`Visible copy is incomplete for ${id}.`);
    if (VISIBLE_FIELDS.some((field) => CJK.test(record[field]))) errors.push(`Visible copy must be English-only for ${id}.`);
    const anchorHasExactFields = hasExactFields(record.technicalAnchor, ANCHOR_FIELDS);
    if (!anchorHasExactFields) errors.push(`Technical anchor fields are invalid for ${id}.`);
    if (anchorHasExactFields && ANCHOR_COPY_FIELDS.some((field) => !nonEmptyString(record.technicalAnchor[field]))) errors.push(`Technical anchor copy is incomplete for ${id}.`);
    if (!/^https:\/\//.test(record.technicalAnchor?.sourceUrl ?? "")) errors.push(`Technical source URL is invalid for ${id}.`);
    if (!/^doi:10\./i.test(record.technicalAnchor?.persistentId ?? "")) errors.push(`OpenAlex persistent ID is invalid for ${id}.`);
  }
  return { ok: errors.length === 0, errors };
}
