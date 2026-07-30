import { calculateExpectedAttributableNetSocialValue } from "../valuations/formulas.mjs";

const money = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function formatHeadline(result, metadata) {
  const roundedThousands = Math.round(result.eansv / 10000) * 10;
  const sign = roundedThousands >= 0 ? "+" : "-";
  return `${sign}$${Math.abs(roundedThousands)}K ${metadata.currency} ${metadata.constantDollarYear}`;
}

export function buildStaticExampleEansvCard(example) {
  if (!example?.model || !example?.metadata) {
    throw new TypeError("Static EANSV example model and metadata are required.");
  }
  const result = calculateExpectedAttributableNetSocialValue(example.model);
  const [full, partial, negative] = result.outcomes;
  return {
    label: example.metadata.label,
    value: formatHeadline(result, example.metadata),
    formula: [
      `Full success: ${(full.probability * 100).toFixed(0)}% x PV $${money.format(full.presentValue)} = $${money.format(full.expectedPresentValue)}`,
      `Partial success: ${(partial.probability * 100).toFixed(0)}% x PV $${money.format(partial.presentValue)} = $${money.format(partial.expectedPresentValue)}`,
      `Useful negative result: ${(negative.probability * 100).toFixed(0)}% x PV $${money.format(negative.presentValue)} = $${money.format(negative.expectedPresentValue)}`,
      "",
      `With-research expected PV = $${money.format(result.withResearchPresentValue)}`,
      `Less without-research counterfactual PV = $${money.format(result.withoutResearchCounterfactualPresentValue)}`,
      `Less research cost PV = $${money.format(result.researchCostPresentValue)}`,
      `EANSV = $${money.format(result.eansv)}`,
    ],
    reason:
      "This is a worked scenario, not a whole-industry valuation. Compute cost uses an external price anchor; adoption, run volume, productivity, probabilities, benefit duration, the counterfactual, and research cost are explicit scenario assumptions.",
  };
}
