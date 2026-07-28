function parseMarkdownTable(sectionText) {
  const rows = new Map();
  for (const line of sectionText.split(/\r?\n/)) {
    const match = line.match(/^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$/);
    if (!match || /^-+$/.test(match[1].trim())) continue;
    rows.set(match[1].trim().toLowerCase(), match[2].trim().replace(/^`|`$/g, ""));
  }
  return rows;
}

function section(text, heading) {
  const match = text.match(new RegExp(`(?:^|\\r?\\n)## ${heading}\\s*(?:\\r?\\n|$)([\\s\\S]*?)(?=\\r?\\n## |\\s*$)`));
  return match?.[1] ?? "";
}

function inlineValue(text, label) {
  const match = text.match(new RegExp(`^- ${label}:\\s*\`([^\`]+)\`\\s*$`, "mi"));
  return match?.[1] ?? null;
}

function numericValue(rows, key) {
  const value = rows.get(key);
  return value === undefined ? null : Number(value);
}

function methodDescription(text) {
  const match = section(text, "Method").match(/was \*\*([^*]+)\*\*/i);
  return match?.[1] ?? null;
}

function publicContract(text) {
  const publicContractRows = parseMarkdownTable(section(text, "Public Contract"));
  const tableValue = publicContractRows.get("public contract status");
  if (tableValue) return tableValue;
  return section(text, "Public Contract Check").match(/Status:\s*\*\*([^*]+)\*\*/i)?.[1] ?? null;
}

export function buildTrialRef(proposalNumber) {
  const padded = String(proposalNumber).padStart(3, "0");
  const runTotal = proposalNumber <= 100 ? "run100" : "run200";
  return `autoresearch/css-distance/${runTotal}-proposal-${padded}`;
}

export function parseAutoqecReport(text, { proposalNumber }) {
  const overview = section(text, "Overview");
  const publicContractSection = section(text, "Public Contract");
  const screening = parseMarkdownTable(section(text, "Blinded Development Screening"));
  const hasRecordedTiming = ["average seconds", "median seconds", "p95 seconds"]
    .every((key) => screening.has(key));
  const notRun = hasRecordedTiming && ["average seconds", "median seconds", "p95 seconds"]
    .some((key) => screening.get(key).toLowerCase() === "not run");

  return {
    branch: parseMarkdownTable(publicContractSection).get("branch")
      ?? inlineValue(overview, "Branch")
      ?? buildTrialRef(proposalNumber),
    candidateSourcePath: inlineValue(overview, "Candidate"),
    publicContract: publicContract(text),
    methodDescription: methodDescription(text),
    metrics: {
      decision: screening.get("decision") ?? null,
      runs: numericValue(screening, "runs"),
      verifiedWitnesses: numericValue(screening, "verified witnesses"),
      targetHits: numericValue(screening, "target hits"),
      timeouts: numericValue(screening, "timeouts"),
      crashes: numericValue(screening, "crashes"),
      invalidClaims: numericValue(screening, "invalid claims"),
      weightedTargetHits: numericValue(screening, "weighted target hits"),
      normalizedQuality: numericValue(screening, "normalized quality"),
      runtimeSeconds: notRun ? null : numericValue(screening, "runtime seconds"),
      averageSeconds: hasRecordedTiming && !notRun ? numericValue(screening, "average seconds") : null,
      medianSeconds: hasRecordedTiming && !notRun ? numericValue(screening, "median seconds") : null,
      p95Seconds: hasRecordedTiming && !notRun ? numericValue(screening, "p95 seconds") : null,
      timingStatus: notRun ? "not-run" : hasRecordedTiming ? "recorded" : "legacy-not-recorded",
      speedup: null,
    },
  };
}
