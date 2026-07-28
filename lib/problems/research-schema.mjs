export const RESEARCH_DISCLAIMER = "Imported experimental record - not reviewed knowledge.";
export const ATTEMPT_ID_PATTERN = /^ATT-(\d{3})$/;
export const TIMING_STATUSES = ["recorded", "legacy-not-recorded", "not-run"];
export const GATE_VALUES = ["passed", "failed", "not-recorded"];
export const CANDIDATE_STATUSES = ["present", "not-generated"];
export const AUTOQEC_INFRASTRUCTURE_RANGES = [
  { first: 1, last: 1, cohort: "cohort-001-100", commit: "c4533f982ece376c5f299a13edfabff0f489182c" },
  { first: 2, last: 100, cohort: "cohort-001-100", commit: "3e61f5ac8143e4848e5e814188c83683c74dfe4c" },
  { first: 101, last: 104, cohort: "cohort-101-200", commit: "12a8f794f68d63f07303df0cc38fa244c1ab1248" },
  { first: 105, last: 107, cohort: "cohort-101-200", commit: "87f0972ca2551074546c723cf48053d569b9bf59" },
  { first: 108, last: 108, cohort: "cohort-101-200", commit: "3f30f39a2f9be8ceead3821706aae77acdd980aa" },
  { first: 109, last: 200, cohort: "cohort-101-200", commit: "b6a0e03c05a653b4e85160a703c0be4eef06b619" },
];

const SHA256_PATTERN = /^[a-f0-9]{64}$/;
const COMMIT_PATTERN = /^[a-f0-9]{40}$/;
const SAFE_RELATIVE_PATH_PATTERN = /^(?!\/)(?!\.)(?!.*(?:^|\/)\.\.(?:\/|$))(?!.*\/\/)[A-Za-z0-9][A-Za-z0-9._/@+-]*(?:\/[A-Za-z0-9][A-Za-z0-9._@+-]*)*$/;

function diagnostic(relativePath, field, message) {
  return { relativePath, field, message };
}

function finish(value, errors) {
  return errors.length === 0 ? { ok: true, value } : { ok: false, errors };
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function isNonEmptyString(value) {
  return typeof value === "string" && value.trim().length > 0;
}

function isNonNegativeInteger(value) {
  return Number.isInteger(value) && value >= 0;
}

function isFinitePositiveNumber(value) {
  return Number.isFinite(value) && value > 0;
}

function isValidTimestamp(value) {
  return typeof value === "string" && Number.isFinite(Date.parse(value));
}

function validatorContext(context, fallback) {
  const errors = [];
  const relativePath = context.relativePath ?? fallback;
  return {
    errors,
    relativePath,
    add(field, message) {
      errors.push(diagnostic(relativePath, field, message));
    },
  };
}

function requireExactFields(value, fields, add, name) {
  if (!isObject(value)) {
    add(name, `${name} must be an object.`);
    return false;
  }
  const allowed = new Set(fields);
  for (const field of Object.keys(value)) {
    if (!allowed.has(field)) add(`${name}.${field}`, `Unknown field: ${field}.`);
  }
  for (const field of fields) {
    if (!(field in value)) add(`${name}.${field}`, "Required field is missing.");
  }
  return true;
}

function requireTopLevelFields(value, fields, add) {
  if (!isObject(value)) {
    add("manifest", "Manifest must be an object.");
    return false;
  }
  const allowed = new Set(fields);
  for (const field of Object.keys(value)) {
    if (!allowed.has(field)) add(field, `Unknown top-level field: ${field}.`);
  }
  for (const field of fields) {
    if (!(field in value)) add(field, "Required top-level field is missing.");
  }
  return true;
}

function isSafeRelativePath(value) {
  return typeof value === "string" && SAFE_RELATIVE_PATH_PATTERN.test(value);
}

function expectedRange(sequence) {
  return AUTOQEC_INFRASTRUCTURE_RANGES.find((range) => sequence >= range.first && sequence <= range.last);
}

function rangesAreContiguous(ranges) {
  return ranges.every((range, index) => isObject(range)
    && Number.isInteger(range.first)
    && Number.isInteger(range.last)
    && range.first >= 1
    && range.last >= range.first
    && (index === 0 || (isObject(ranges[index - 1]) && range.first === ranges[index - 1].last + 1)));
}

function isValidRange(range, requiredCommit = false) {
  return isObject(range)
    && Number.isInteger(range.first)
    && range.first >= 1
    && Number.isInteger(range.last)
    && range.last >= range.first
    && (!requiredCommit || COMMIT_PATTERN.test(range.sourceInfrastructureCommit));
}

function validateRange(range, field, add, requiredCommit = false) {
  const fields = requiredCommit
    ? ["first", "last", "sourceInfrastructureCommit"]
    : ["first", "last"];
  if (!requireExactFields(range, fields, add, field)) return;
  if (!Number.isInteger(range.first) || range.first < 1) add(`${field}.first`, "first must be a positive integer.");
  if (!Number.isInteger(range.last) || range.last < range.first) add(`${field}.last`, "last must be an integer at least first.");
  if (requiredCommit && (!COMMIT_PATTERN.test(range.sourceInfrastructureCommit))) {
    add(`${field}.sourceInfrastructureCommit`, "sourceInfrastructureCommit must be a 40-character lowercase commit hash.");
  }
}

function validateFile(file, field, add, { sourcePath, generated, executable } = {}) {
  const fields = ["path", "sha256", "size"];
  if (sourcePath) fields.push("sourcePath");
  if (generated) fields.push("generated");
  if (executable) fields.push("executable");
  if (!requireExactFields(file, fields, add, field)) return;
  if (!isSafeRelativePath(file.path)) add(`${field}.path`, "path must be a safe relative path.");
  if (!SHA256_PATTERN.test(file.sha256)) add(`${field}.sha256`, "sha256 must be a 64-character lowercase hash.");
  if (!isNonNegativeInteger(file.size)) add(`${field}.size`, "size must be a non-negative integer.");
  if (sourcePath && file.sourcePath !== null && !isSafeRelativePath(file.sourcePath)) {
    add(`${field}.sourcePath`, "sourcePath must be null or a safe relative path.");
  }
  if (generated && typeof file.generated !== "boolean") add(`${field}.generated`, "generated must be a boolean.");
  if (executable && typeof file.executable !== "boolean") add(`${field}.executable`, "executable must be a boolean.");
}

export function validateResearchManifest(manifest, context = {}) {
  const state = validatorContext(context, "research.json");
  const fields = ["schemaVersion", "kind", "problemId", "attemptCount", "attemptIdRange", "disclaimer", "cohorts"];
  if (!requireTopLevelFields(manifest, fields, state.add)) return finish(manifest, state.errors);

  if (manifest.schemaVersion !== 1) state.add("schemaVersion", "schemaVersion must be 1.");
  if (manifest.kind !== "imported-research-record") state.add("kind", "kind must be imported-research-record.");
  if (manifest.problemId !== "Prob-001") state.add("problemId", "problemId must be Prob-001.");
  if (manifest.attemptCount !== 200) state.add("attemptCount", "attemptCount must be 200.");
  if (!Array.isArray(manifest.attemptIdRange) || manifest.attemptIdRange.length !== 2 || manifest.attemptIdRange[0] !== "ATT-001" || manifest.attemptIdRange[1] !== "ATT-200") {
    state.add("attemptIdRange", "attemptIdRange must be [ATT-001, ATT-200].");
  }
  if (manifest.disclaimer !== RESEARCH_DISCLAIMER) state.add("disclaimer", "disclaimer must use the imported research disclaimer.");
  if (!Array.isArray(manifest.cohorts) || manifest.cohorts.length !== 2) {
    state.add("cohorts", "cohorts must contain the two imported cohorts.");
  } else {
    const expected = [
      { id: "cohort-001-100", first: 1, last: 100 },
      { id: "cohort-101-200", first: 101, last: 200 },
    ];
    manifest.cohorts.forEach((cohort, index) => {
      const field = `cohorts[${index}]`;
      if (!requireExactFields(cohort, ["id", "first", "last"], state.add, field)) return;
      if (cohort.id !== expected[index].id || cohort.first !== expected[index].first || cohort.last !== expected[index].last) {
        state.add(field, "cohort does not match the required imported cohort range.");
      }
    });
    if (!rangesAreContiguous(manifest.cohorts)) state.add("cohorts", "cohort ranges must be contiguous.");
  }
  return finish(manifest, state.errors);
}

export function validateResearchAttempt(attempt, context = {}) {
  const state = validatorContext(context, "attempt.json");
  const fields = ["schemaVersion", "problemId", "id", "sequence", "cohort", "title", "summary", "stage", "decision", "gate", "method", "metrics", "provenance", "candidate", "artifacts"];
  if (!requireTopLevelFields(attempt, fields, state.add)) return finish(attempt, state.errors);

  if (attempt.schemaVersion !== 1) state.add("schemaVersion", "schemaVersion must be 1.");
  if (attempt.problemId !== "Prob-001") state.add("problemId", "problemId must be Prob-001.");
  if (!Number.isInteger(attempt.sequence) || !expectedRange(attempt.sequence)) state.add("sequence", "sequence must be within the imported range.");
  if (!ATTEMPT_ID_PATTERN.test(attempt.id) || attempt.id !== `ATT-${String(attempt.sequence).padStart(3, "0")}`) state.add("id", "id must match sequence as ATT-###.");
  if (!isNonEmptyString(attempt.cohort) || attempt.cohort !== expectedRange(attempt.sequence)?.cohort) state.add("cohort", "cohort must match the infrastructure range.");
  for (const field of ["title", "summary", "stage", "decision"]) if (!isNonEmptyString(attempt[field])) state.add(field, `${field} must be a non-empty string.`);

  if (requireExactFields(attempt.gate, ["containment", "publicContract", "development"], state.add, "gate")) {
    for (const field of ["containment", "publicContract", "development"]) {
      if (!GATE_VALUES.includes(attempt.gate[field])) state.add(`gate.${field}`, "gate value must be known.");
    }
  }
  if (requireExactFields(attempt.method, ["description", "learnedFrom"], state.add, "method")) {
    if (!isNonEmptyString(attempt.method.description)) state.add("method.description", "description must be a non-empty string.");
    if (attempt.method.learnedFrom !== null && !isSafeRelativePath(attempt.method.learnedFrom)) state.add("method.learnedFrom", "learnedFrom must be null or a safe relative path.");
  }
  validateAttemptMetrics(attempt.metrics, state.add);
  validateAttemptProvenance(attempt.provenance, attempt.sequence, attempt.cohort, state.add);
  validateCandidate(attempt.candidate, attempt.artifacts, attempt.gate, attempt.metrics, state.add);

  if (!Array.isArray(attempt.artifacts) || attempt.artifacts.length === 0) state.add("artifacts", "artifacts must be a non-empty array.");
  else attempt.artifacts.forEach((artifact, index) => validateArtifact(artifact, `artifacts[${index}]`, state.add));
  return finish(attempt, state.errors);
}

function validateAttemptMetrics(metrics, add) {
  const fields = ["runs", "verifiedWitnesses", "targetHits", "timeouts", "crashes", "invalidClaims", "weightedTargetHits", "normalizedQuality", "runtimeSeconds", "averageSeconds", "medianSeconds", "p95Seconds", "timingStatus", "speedup"];
  if (!requireExactFields(metrics, fields, add, "metrics")) return;
  for (const field of ["runs", "verifiedWitnesses", "targetHits", "timeouts", "crashes", "invalidClaims", "weightedTargetHits"]) {
    if (!isNonNegativeInteger(metrics[field])) add(`metrics.${field}`, `${field} must be a non-negative integer.`);
  }
  if (!Number.isFinite(metrics.normalizedQuality) || metrics.normalizedQuality < 0) add("metrics.normalizedQuality", "normalizedQuality must be a non-negative finite number.");
  if (!TIMING_STATUSES.includes(metrics.timingStatus)) add("metrics.timingStatus", "timingStatus must be known.");
  const timings = ["runtimeSeconds", "averageSeconds", "medianSeconds", "p95Seconds"];
  if (metrics.timingStatus === "recorded") {
    for (const field of timings) if (!isFinitePositiveNumber(metrics[field])) add(`metrics.${field}`, `${field} must be a finite positive number when timing is recorded.`);
    if (metrics.speedup !== null && !isFinitePositiveNumber(metrics.speedup)) add("metrics.speedup", "speedup must be null or a finite positive number.");
  } else if (metrics.timingStatus === "legacy-not-recorded") {
    for (const field of ["averageSeconds", "medianSeconds", "p95Seconds", "speedup"]) if (metrics[field] !== null) add(`metrics.${field}`, `${field} must be null when timing is legacy-not-recorded.`);
  } else if (metrics.timingStatus === "not-run") {
    if (metrics.runs !== 0) add("metrics.runs", "runs must be 0 when timing is not-run.");
    for (const field of [...timings, "speedup"]) if (metrics[field] !== null) add(`metrics.${field}`, `${field} must be null when timing is not-run.`);
  }
}

function validateAttemptProvenance(provenance, sequence, cohort, add) {
  const fields = ["sourceRepository", "sourceBranch", "sourceCommit", "sourceInfrastructureCommit", "sourceCohort", "model"];
  if (!requireExactFields(provenance, fields, add, "provenance")) return;
  if (provenance.sourceRepository !== "AutoQEC") add("provenance.sourceRepository", "sourceRepository must be AutoQEC.");
  if (!isNonEmptyString(provenance.sourceBranch)) add("provenance.sourceBranch", "sourceBranch must be a non-empty string.");
  for (const field of ["sourceCommit", "sourceInfrastructureCommit"]) if (!COMMIT_PATTERN.test(provenance[field])) add(`provenance.${field}`, `${field} must be a 40-character lowercase commit hash.`);
  if (provenance.sourceCohort !== cohort) add("provenance.sourceCohort", "sourceCohort must match cohort.");
  if (provenance.model !== null && !isNonEmptyString(provenance.model)) add("provenance.model", "model must be null or a non-empty string.");
  const range = expectedRange(sequence);
  if (range && provenance.sourceInfrastructureCommit !== range.commit) add("provenance.sourceInfrastructureCommit", "sourceInfrastructureCommit must match the infrastructure range.");
}

function validateCandidate(candidate, artifacts, gate, metrics, add) {
  const isPresent = candidate?.status === "present";
  const fields = isPresent ? ["status", "path"] : ["status"];
  if (!requireExactFields(candidate, fields, add, "candidate")) return;
  if (!CANDIDATE_STATUSES.includes(candidate.status)) add("candidate.status", "candidate status must be known.");
  if (isPresent) {
    if (candidate.path !== "candidate.py") add("candidate.path", "present candidate path must be candidate.py.");
    if (!Array.isArray(artifacts) || !artifacts.some((artifact) => artifact?.path === "candidate.py")) add("artifacts", "present candidate requires a candidate.py artifact.");
  } else if (candidate.status === "not-generated" && gate?.publicContract !== "failed" && metrics?.runs !== 0) {
    add("candidate.status", "not-generated candidates require a failed public contract or zero runs.");
  }
}

function validateArtifact(artifact, field, add) {
  if (!requireExactFields(artifact, ["path", "sha256", "sourcePath"], add, field)) return;
  if (!isSafeRelativePath(artifact.path)) add(`${field}.path`, "path must be a safe relative path.");
  if (!SHA256_PATTERN.test(artifact.sha256)) add(`${field}.sha256`, "sha256 must be a 64-character lowercase hash.");
  if (!isSafeRelativePath(artifact.sourcePath)) add(`${field}.sourcePath`, "sourcePath must be a safe relative path.");
}

export function validateCohortManifest(manifest, context = {}) {
  const state = validatorContext(context, "cohort.json");
  const fields = ["schemaVersion", "kind", "id", "problemId", "attempts"];
  if (!requireTopLevelFields(manifest, fields, state.add)) return finish(manifest, state.errors);
  if (manifest.schemaVersion !== 1) state.add("schemaVersion", "schemaVersion must be 1.");
  if (manifest.kind !== "autoqec-css-distance-cohort") state.add("kind", "kind must be autoqec-css-distance-cohort.");
  if (!["cohort-001-100", "cohort-101-200"].includes(manifest.id)) state.add("id", "id must be a known cohort ID.");
  if (manifest.problemId !== "Prob-001") state.add("problemId", "problemId must be Prob-001.");
  if (!Array.isArray(manifest.attempts) || manifest.attempts.length === 0) state.add("attempts", "attempts must be a non-empty array.");
  else {
    manifest.attempts.forEach((range, index) => validateRange(range, `attempts[${index}]`, state.add, true));
    if (manifest.attempts.every((range) => isValidRange(range, true))) {
      if (!rangesAreContiguous(manifest.attempts)) state.add("attempts", "attempt ranges must be contiguous.");
      const expected = AUTOQEC_INFRASTRUCTURE_RANGES.filter((range) => range.cohort === manifest.id);
      if (manifest.attempts.length !== expected.length || manifest.attempts.some((range, index) => range.first !== expected[index]?.first || range.last !== expected[index]?.last || range.sourceInfrastructureCommit !== expected[index]?.commit)) {
        state.add("attempts", "attempt ranges must match the infrastructure range map.");
      }
    }
  }
  return finish(manifest, state.errors);
}

export function validateSourceManifest(manifest, context = {}) {
  const state = validatorContext(context, "source.json");
  const fields = ["schemaVersion", "kind", "problemId", "sourceRepository", "sourceCommit", "attemptRanges", "entryPoints", "excludedPathClasses", "files", "blindDatasetReproducible"];
  if (!requireTopLevelFields(manifest, fields, state.add)) return finish(manifest, state.errors);
  if (manifest.schemaVersion !== 1) state.add("schemaVersion", "schemaVersion must be 1.");
  if (manifest.kind !== "autoqec-css-distance-source-snapshot") state.add("kind", "kind must be autoqec-css-distance-source-snapshot.");
  if (manifest.problemId !== "Prob-001") state.add("problemId", "problemId must be Prob-001.");
  if (manifest.sourceRepository !== "AutoQEC") state.add("sourceRepository", "sourceRepository must be AutoQEC.");
  if (!COMMIT_PATTERN.test(manifest.sourceCommit)) state.add("sourceCommit", "sourceCommit must be a 40-character lowercase commit hash.");
  validateSourceRanges(manifest.attemptRanges, manifest.sourceCommit, state.add);
  validateStringPaths(manifest.entryPoints, "entryPoints", state.add);
  if (!Array.isArray(manifest.excludedPathClasses) || manifest.excludedPathClasses.some((value) => !isNonEmptyString(value))) state.add("excludedPathClasses", "excludedPathClasses must be an array of non-empty strings.");
  if (!Array.isArray(manifest.files) || manifest.files.length === 0) state.add("files", "files must be a non-empty array.");
  else manifest.files.forEach((file, index) => validateFile(file, `files[${index}]`, state.add, { executable: true }));
  if (typeof manifest.blindDatasetReproducible !== "boolean") state.add("blindDatasetReproducible", "blindDatasetReproducible must be a boolean.");
  return finish(manifest, state.errors);
}

function validateSourceRanges(ranges, sourceCommit, add) {
  if (!Array.isArray(ranges) || ranges.length === 0) {
    add("attemptRanges", "attemptRanges must be a non-empty array.");
    return;
  }
  ranges.forEach((range, index) => validateRange(range, `attemptRanges[${index}]`, add));
  if (!ranges.every((range) => isValidRange(range))) return;
  if (!rangesAreContiguous(ranges)) add("attemptRanges", "attempt ranges must be contiguous.");
  const expected = AUTOQEC_INFRASTRUCTURE_RANGES.find((range) => range.commit === sourceCommit);
  if (ranges.length !== 1 || !expected || ranges[0].first !== expected.first || ranges[0].last !== expected.last) {
    add("attemptRanges", "attemptRanges must equal the exact infrastructure snapshot for sourceCommit.");
  }
}

function validateStringPaths(values, field, add) {
  if (!Array.isArray(values) || values.length === 0 || values.some((value) => !isSafeRelativePath(value))) add(field, `${field} must be a non-empty array of safe relative paths.`);
}

export function validateImportManifest(manifest, context = {}) {
  const state = validatorContext(context, "import.json");
  const fields = ["schemaVersion", "kind", "problemId", "sourceRepository", "importedAt", "attempts", "files"];
  if (!requireTopLevelFields(manifest, fields, state.add)) return finish(manifest, state.errors);
  if (manifest.schemaVersion !== 1) state.add("schemaVersion", "schemaVersion must be 1.");
  if (manifest.kind !== "autoqec-css-distance-import") state.add("kind", "kind must be autoqec-css-distance-import.");
  if (manifest.problemId !== "Prob-001") state.add("problemId", "problemId must be Prob-001.");
  if (manifest.sourceRepository !== "AutoQEC") state.add("sourceRepository", "sourceRepository must be AutoQEC.");
  if (!isValidTimestamp(manifest.importedAt)) state.add("importedAt", "importedAt must be a valid timestamp.");
  if (manifest.attempts !== 200) state.add("attempts", "attempts must be 200.");
  if (!Array.isArray(manifest.files) || manifest.files.length === 0) state.add("files", "files must be a non-empty array.");
  else manifest.files.forEach((file, index) => validateFile(file, `files[${index}]`, state.add, { sourcePath: true, generated: true }));
  return finish(manifest, state.errors);
}
