export const DEFAULT_STALE_WINDOWS = Object.freeze({
  citation: 90,
  hardware: 90,
  classicalBaseline: 90,
  market: 180,
  contract: 180,
  adoption: 180,
});

function dateFrom(value, fallback) {
  const candidate = typeof value === "string" ? value : value?.date ?? fallback;
  const date = new Date(candidate);
  return Number.isNaN(date.valueOf()) ? null : date;
}

function isPrivate(value) {
  return value !== null && typeof value === "object" && value.visibility === "private";
}

export function evaluateValuationFreshness(snapshot, now = new Date()) {
  const checkedAt = new Date(now);
  if (Number.isNaN(checkedAt.valueOf())) throw new TypeError("now must be a valid date.");
  const evidenceDates = snapshot?.evidenceDates ?? {};
  const fallback = snapshot?.manifest?.createdAt;
  const staleClasses = [];
  const details = {};

  for (const [evidenceClass, evidence] of Object.entries(evidenceDates)) {
    if (isPrivate(evidence)) {
      details[evidenceClass] = { stale: false, reason: "private-no-automatic-expiry" };
      continue;
    }
    const nextPublicationAt = evidence?.government ? dateFrom(evidence.nextPublicationAt) : null;
    if (nextPublicationAt && checkedAt < nextPublicationAt) {
      details[evidenceClass] = { stale: false, reason: "next-publication-pending", nextPublicationAt: nextPublicationAt.toISOString() };
      continue;
    }
    const observedAt = dateFrom(evidence, fallback);
    const windowDays = DEFAULT_STALE_WINDOWS[evidenceClass];
    if (!observedAt || windowDays === undefined) {
      details[evidenceClass] = { stale: false, reason: "no-policy-window" };
      continue;
    }
    const expiresAt = new Date(observedAt.valueOf() + windowDays * 24 * 60 * 60 * 1000);
    const stale = checkedAt > expiresAt;
    details[evidenceClass] = { stale, observedAt: observedAt.toISOString(), expiresAt: expiresAt.toISOString() };
    if (stale) staleClasses.push(evidenceClass);
  }

  return { advisory: true, checkedAt: checkedAt.toISOString(), staleClasses, details };
}
