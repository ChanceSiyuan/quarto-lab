const SORT_FIELDS = Object.freeze({
  combined: "combinedPriority",
  "research-value": "researchValue",
  "autoresearch-fit": "autoresearchFit",
  verdict: "verdict",
  "scientific-attention": "scientificAttention",
});

function numericEstimate(value) {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value?.estimate === "number" && Number.isFinite(value.estimate)) return value.estimate;
  if (typeof value?.interval?.base === "number" && Number.isFinite(value.interval.base)) return value.interval.base;
  return null;
}

function compareValues(left, right, sort) {
  if (sort === "verdict") {
    const leftValue = typeof left === "string" ? left : null;
    const rightValue = typeof right === "string" ? right : null;
    if (leftValue === null || rightValue === null) return leftValue === rightValue ? 0 : leftValue === null ? 1 : -1;
    return leftValue.localeCompare(rightValue);
  }
  const leftValue = numericEstimate(left);
  const rightValue = numericEstimate(right);
  if (leftValue === null || rightValue === null) return leftValue === rightValue ? 0 : leftValue === null ? 1 : -1;
  return rightValue - leftValue;
}

export function sortPortfolioRows(rows, sort = "combined") {
  const field = SORT_FIELDS[sort];
  if (!field) throw new RangeError(`Unsupported portfolio sort: ${sort}`);
  return [...rows].sort((left, right) => {
    const comparison = compareValues(left[field], right[field], sort);
    return comparison || left.problemId.localeCompare(right.problemId);
  });
}
