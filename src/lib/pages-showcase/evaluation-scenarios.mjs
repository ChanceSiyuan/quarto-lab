const SCIENTIFIC_ACTIVE_WEIGHT = 0.9;

const STATIC_EXAMPLE_POINTS = Object.freeze({
  scientificDemand: 33.4,
  eansv: 181_422.55,
  eansvDisplay: "+$180K USD 2026",
  autoresearchFit: 88.5,
});

export const AUTORESEARCH_DIMENSIONS = Object.freeze([
  { id: "modifiable", label: "modifiable search object", weight: 20 },
  { id: "objective", label: "executable objective", weight: 20 },
  { id: "correctness", label: "correctness and anti-gaming", weight: 15 },
  { id: "feedback", label: "incremental feedback", weight: 15 },
  { id: "fresh", label: "fresh evaluation", weight: 10 },
  { id: "reproducibility", label: "reproducibility, auditability", weight: 10 },
  { id: "runtime", label: "attempt runtime", weight: 10 },
]);

function round(value, digits = 1) {
  const factor = 10 ** digits;
  return Math.round((value + Number.EPSILON) * factor) / factor;
}

export function calculateScientificDemand({ influence, momentum, breadth }, digits = 1) {
  return round(100 * (0.45 * influence + 0.30 * momentum + 0.15 * breadth) / SCIENTIFIC_ACTIVE_WEIGHT, digits);
}

export function calculateEansv({ incrementalSuccessProbability, conditionalSocialValue, informationValue, researchCost }) {
  return incrementalSuccessProbability * conditionalSocialValue + informationValue - researchCost;
}

export function calculateAutoresearchFit(scores, digits = 1) {
  const byId = new Map(scores.map((item) => [item.id, item.score]));
  const weightedSum = AUTORESEARCH_DIMENSIONS.reduce((sum, item) => sum + item.weight * byId.get(item.id), 0);
  return round(weightedSum / 5, digits);
}

const SCENARIOS = Object.freeze({
  "Prob-124": {
    scientific: { influence: 0.81, momentum: 0.79, breadth: 0.73, range: [72, 86], digits: 0 },
    eansv: { incrementalSuccessProbability: 0.05, conditionalSocialValue: 4_000_000, informationValue: 400_000, researchCost: 300_000, range: [-700_000, 9_000_000] },
    fit: [["modifiable", 4.5], ["objective", 2.5], ["correctness", 5], ["feedback", 3.5], ["fresh", 4], ["reproducibility", 3], ["runtime", 1.5]],
    scientificReason: "The kagome antiferromagnet has strong and sustained scholarly attention, while certified two-sided bounds remain a narrower subfield than the variational literature.",
    eansvReason: "Reusable certification methods create value, but the missing public repin, heavy SDP/PEPS cost, and substantial without-project progress keep attributable value modest.",
    fitReason: "Certificates and a bracket-width objective are hard to game, but the baseline is not yet publicly repinned and each SDP/PEPS feedback cycle is expensive.",
  },
  "Prob-125": {
    scientific: { influence: 0.86, momentum: 0.88, breadth: 0.76, range: [78, 91], digits: 0 },
    eansv: { incrementalSuccessProbability: 0.02, conditionalSocialValue: 5_000_000, informationValue: 400_000, researchCost: 500_000, range: [-1_100_000, 5_000_000] },
    fit: [["modifiable", 5], ["objective", 4.5], ["correctness", 4.5], ["feedback", 4.5], ["fresh", 4.5], ["reproducibility", 4], ["runtime", 1.5]],
    scientificReason: "J1-J2 at maximal frustration is the most crowded and visible leaderboard among these five problems, with active PEPS and neural-quantum-state work.",
    eansvReason: "High scientific demand does not imply high attribution: a crowded race raises the probability that comparable progress occurs without this project, while training and independent sampling remain costly.",
    fitReason: "The variational objective and fresh sampling gate are strong, but large-model training and statistically independent evaluation slow the loop.",
  },
  "Prob-126": {
    scientific: { influence: 0.74, momentum: 0.64, breadth: 0.70, range: [61, 78], digits: 0 },
    eansv: { incrementalSuccessProbability: 0.04, conditionalSocialValue: 15_000_000, informationValue: 800_000, researchCost: 600_000, range: [-800_000, 26_000_000] },
    fit: [["modifiable", 4], ["objective", 2.5], ["correctness", 5], ["feedback", 3], ["fresh", 4], ["reproducibility", 2.5], ["runtime", 1]],
    scientificReason: "A new AKLT spectral-gap theorem has a high ceiling and durable mathematical value, but the literature audience and active-paper breadth are comparatively specialized.",
    eansvReason: "A successful theorem has durable transferable value and useful negative information, but the probability of closing an open lattice case is low and certified ED/DMRG is expensive.",
    fitReason: "The final interval-certified inequality is exceptionally strong, but the target lattice is not yet repinned and finite-cluster ED/DMRG makes feedback slow.",
  },
  "Prob-127": {
    scientific: { influence: 0.82, momentum: 0.80, breadth: 0.80, range: [73, 88], digits: 0 },
    eansv: { incrementalSuccessProbability: 0.15, conditionalSocialValue: 15_000_000, informationValue: 1_000_000, researchCost: 250_000, range: [-200_000, 60_000_000] },
    fit: [["modifiable", 5], ["objective", 5], ["correctness", 5], ["feedback", 5], ["fresh", 5], ["reproducibility", 4.5], ["runtime", 4.5]],
    scientificReason: "Contraction-order optimization remains active across quantum-circuit simulation, tensor methods, and statistical mechanics, with broad direct software reuse.",
    eansvReason: "Exact low-cost evaluation, a high probability of usable improvements, open-source adoption, and direct compute savings produce the largest base EANSV of the five.",
    fitReason: "Candidates are explicit trees, exact costs are independently recomputable, memory budgets are pinned, and feedback is fast and directional.",
  },
  "Prob-128": {
    scientific: { influence: 0.80, momentum: 0.80, breadth: 0.74, range: [70, 86], digits: 0 },
    eansv: { incrementalSuccessProbability: 0.08, conditionalSocialValue: 12_000_000, informationValue: 750_000, researchCost: 310_000, range: [-600_000, 40_000_000] },
    fit: [["modifiable", 5], ["objective", 4.5], ["correctness", 5], ["feedback", 4.5], ["fresh", 4.5], ["reproducibility", 4.5], ["runtime", 3.5]],
    scientificReason: "Rigorous product-formula bounds are foundational to Hamiltonian simulation and resource estimation, with sustained theoretical interest and recent extensions.",
    eansvReason: "Sharper certified bounds can reduce downstream resource estimates and transfer across Hamiltonians, while attribution is limited by parallel theoretical progress.",
    fitReason: "The objective and symbolic certificate are precise and hard to game; only the combinatorial growth of commutator bookkeeping materially slows feedback.",
  },
});

function formatDecimal(value, digits = 1) {
  return Number(value).toFixed(digits);
}

function formatUsd(value) {
  const sign = value < 0 ? "-" : "";
  return `${sign}$${formatDecimal(Math.abs(value) / 1_000_000, 1)}M`;
}

function scientificCard(scenario) {
  const value = calculateScientificDemand(scenario.scientific, scenario.scientific.digits);
  const { influence, momentum, breadth, range, digits } = scenario.scientific;
  return {
    label: "Scientific Demand Score",
    value: `${formatDecimal(value, digits)} / 100`,
    formula: [
      "influence weight = 0.45; recent momentum = 0.30; research breadth = 0.15",
      "citation-network weight = 0.10 reserved; active weights renormalize to 0.90",
      "",
      `score = 100 x (0.45 x ${influence} + 0.30 x ${momentum} + 0.15 x ${breadth}) / 0.90`,
      `      = ${formatDecimal(value, digits)} / 100`,
      `scenario interval = ${range[0]} - ${range[1]} / 100`,
    ],
    reason: scenario.scientificReason,
  };
}

function eansvCard(scenario) {
  const value = calculateEansv(scenario.eansv);
  const { incrementalSuccessProbability, conditionalSocialValue, informationValue, researchCost, range } = scenario.eansv;
  return {
    label: "Expected Attributable Net Social Value (EANSV)",
    value: `${formatUsd(value)} USD 2026`,
    formula: [
      "incremental success probability",
      "  = P(useful outcome with this research) - P(useful outcome without this research)",
      "",
      "EANSV = incremental success probability x conditional social value",
      "      + expected information value - expected research cost",
      `      = ${formatDecimal(incrementalSuccessProbability * 100, 1)}% x ${formatUsd(conditionalSocialValue)}`,
      `      + ${formatUsd(informationValue)} - ${formatUsd(researchCost)}`,
      `      = ${formatUsd(value)} USD 2026`,
      `coherent scenario interval = ${formatUsd(range[0])} to ${formatUsd(range[1])} USD 2026`,
    ],
    reason: scenario.eansvReason,
  };
}

function fitCard(scenario) {
  const scores = scenario.fit.map(([id, score]) => ({ id, score }));
  const byId = new Map(scores.map((item) => [item.id, item.score]));
  const weightedSum = AUTORESEARCH_DIMENSIONS.reduce((sum, item) => sum + item.weight * byId.get(item.id), 0);
  const raw = calculateAutoresearchFit(scores, 1);
  const digits = scenario.fitDigits ?? 0;
  const point = digits === 0 ? Math.round(raw) : raw;
  return {
    label: "Autoresearch Fit",
    value: `${formatDecimal(point, digits)} / 100`,
    formula: [
      "A = 100 x weighted_average(0-5 dimension estimates) / 5",
      "",
      ...AUTORESEARCH_DIMENSIONS.map((item) => {
        const score = byId.get(item.id);
        return `${item.label.padEnd(34)} ${String(item.weight).padStart(2)} x ${formatDecimal(score, 1)} = ${formatDecimal(item.weight * score, 1).padStart(5)}`;
      }),
      `${"weighted sum".padEnd(38)} = ${formatDecimal(weightedSum, 1)}`,
      "",
      `A = ${formatDecimal(weightedSum, 1)} / 5 = ${formatDecimal(raw, 1)}; displayed point = ${point}`,
    ],
    reason: scenario.fitReason,
  };
}

export function getStaticEvaluation(problemId) {
  const scenario = SCENARIOS[problemId];
  if (!scenario) return null;
  return {
    disclosure: scenario.disclosure ?? "Low-confidence external-evidence scenario · five-year horizon · 2026 USD · not a frozen assessment snapshot.",
    cards: [scientificCard(scenario), eansvCard(scenario), fitCard(scenario)],
  };
}

export function getStaticEvaluationPoints(problemId) {
  if (problemId === "Prob-000") {
    return STATIC_EXAMPLE_POINTS;
  }
  const scenario = SCENARIOS[problemId];
  if (!scenario) return null;
  const rawFit = calculateAutoresearchFit(scenario.fit.map(([id, score]) => ({ id, score })), 1);
  return {
    scientificDemand: calculateScientificDemand(scenario.scientific, scenario.scientific.digits),
    eansv: calculateEansv(scenario.eansv),
    autoresearchFit: scenario.fitDigits === 1 ? rawFit : Math.round(rawFit),
  };
}
