const SENSITIVE_FIELDS = new Set(["value", "interval", "currency", "derivation"]);

function isRecord(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function privateVisibility(value) {
  return isRecord(value) && value.visibility === "private";
}

function unsupportedVisibility(value) {
  return isRecord(value)
    && Object.hasOwn(value, "visibility")
    && value.visibility !== "public"
    && value.visibility !== "private";
}

function containsPrivate(value) {
  if (Array.isArray(value)) return value.some(containsPrivate);
  if (!isRecord(value)) return false;
  if (privateVisibility(value) || (Object.hasOwn(value, "visibility") && value.visibility !== "public")) return true;
  return Object.values(value).some(containsPrivate);
}

export function propagateVisibility(inputs) {
  if (!Array.isArray(inputs)) throw new TypeError("visibility inputs must be an array.");
  return inputs.some(containsPrivate) ? "private" : "public";
}

function redact(value, inheritedPrivate = false) {
  if (Array.isArray(value)) return value.map((item) => redact(item, inheritedPrivate));
  if (!isRecord(value)) return value;
  const isPrivate = inheritedPrivate || privateVisibility(value);
  const result = {};
  for (const [key, item] of Object.entries(value)) {
    if (isPrivate && SENSITIVE_FIELDS.has(key)) continue;
    result[key] = redact(item, isPrivate);
  }
  if (privateVisibility(value)) result.redacted = true;
  return result;
}

export function redactPrivate(value) {
  return redact(value);
}

function assertSafe(value, path, inheritedPrivate = false) {
  if (Array.isArray(value)) {
    value.forEach((item, index) => assertSafe(item, `${path}[${index}]`, inheritedPrivate));
    return;
  }
  if (!isRecord(value)) return;
  if (unsupportedVisibility(value)) throw new Error(`Unsupported visibility at ${path}.`);
  const isPrivate = inheritedPrivate || privateVisibility(value);
  if (isPrivate) {
    if (value.redacted !== true) throw new Error(`Unredacted private valuation at ${path}.`);
    for (const field of SENSITIVE_FIELDS) {
      if (Object.hasOwn(value, field)) throw new Error(`Private valuation leaks ${field} at ${path}.`);
    }
  }
  for (const [key, item] of Object.entries(value)) assertSafe(item, `${path}.${key}`, isPrivate);
}

export function assertPublicSafeValuation(value) {
  assertSafe(value, "$", false);
  return value;
}
