export const EVIDENCE_TIERS = Object.freeze(["primary", "authoritative-secondary", "vendor-or-news", "assumption"]);
export const EVIDENCE_STATES = Object.freeze(["reported", "inferred"]);
export const VISIBILITIES = Object.freeze(["public", "private"]);
export const VALUE_STATES = Object.freeze(["known", "unknown"]);
export const SUPPORTED_CURRENCIES = Object.freeze(["USD", "CNY", "EUR", "GBP", "JPY"]);

export function unknownValue(reason) {
  return { state: "unknown", reason };
}

export function knownInterval({ low, base, high, unit, visibility = "public", sourceIds = [] }) {
  return { state: "known", interval: { low, base, high }, unit, visibility, sourceIds };
}
