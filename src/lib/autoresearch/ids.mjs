export const JOB_ID_PATTERN = /^ARJ-\d{8}T\d{6}Z-[a-f0-9]{8}$/;
export const INFRASTRUCTURE_ID_PATTERN = /^INF-(\d{3})$/;
export const PROBLEM_ID_PATTERN = /^Prob-\d{3}$/;

export function isProblemId(value) {
  return typeof value === "string" && PROBLEM_ID_PATTERN.test(value);
}

export function nextInfrastructureId(existingNames) {
  let highest = 0;
  for (const name of existingNames) {
    const match = typeof name === "string" ? INFRASTRUCTURE_ID_PATTERN.exec(name) : null;
    if (match) highest = Math.max(highest, Number(match[1]));
  }
  if (highest >= 999) throw new RangeError("Infrastructure ID space is exhausted");
  return `INF-${String(highest + 1).padStart(3, "0")}`;
}
