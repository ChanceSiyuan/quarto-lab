import { INFRASTRUCTURE_ID_PATTERN, isProblemId } from "./ids.mjs";

const SHA256 = /^[a-f0-9]{64}$/;
const METRIC_ID = /^[a-z][a-z0-9-]{0,63}$/;

export class PreparationContractError extends Error {
  constructor(errors) {
    super(`Invalid preparation contract: ${errors.join("; ")}`);
    this.name = "PreparationContractError";
    this.code = "invalid-preparation-contract";
    this.errors = Object.freeze([...errors]);
  }
}

function deepFreeze(value) {
  if (value && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) deepFreeze(child);
    Object.freeze(value);
  }
  return value;
}

function cloneAndFreeze(value) {
  return deepFreeze(structuredClone(value));
}

function isObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function validateObject(value, location, fields, errors) {
  if (!isObject(value)) {
    errors.push(`${location} must be an object`);
    return false;
  }
  for (const key of Object.keys(value)) if (!fields.includes(key)) errors.push(`${location}.${key} is not allowed`);
  for (const key of fields) if (!(key in value)) errors.push(`${location}.${key} is required`);
  return true;
}

function nonEmptyString(value, location, errors) {
  if (typeof value !== "string" || value.length === 0) {
    errors.push(`${location} must be a non-empty string`);
    return false;
  }
  return true;
}

function safePath(value, location, errors) {
  if (!nonEmptyString(value, location, errors)) return false;
  if (value.includes("\0") || value.includes("\\") || value.startsWith("/") || value.split("/").some((part) => part === "" || part === "." || part === "..")) {
    errors.push(`${location} must be a safe relative path`);
    return false;
  }
  return true;
}

function positiveInteger(value, location, errors) {
  if (!Number.isInteger(value) || value <= 0) errors.push(`${location} must be a positive integer`);
}

function validateQuestion(question, errors) {
  if (!validateObject(question, "question", ["id", "prompt", "answerType", "choices"], errors)) return;
  if (typeof question.id !== "string" || !METRIC_ID.test(question.id)) errors.push("question.id must be a lowercase identifier");
  nonEmptyString(question.prompt, "question.prompt", errors);
  if (question.answerType !== "text" && question.answerType !== "choice") errors.push("question.answerType must be text or choice");
  if (!Array.isArray(question.choices)) errors.push("question.choices must be an array");
  else if (question.answerType === "text" && question.choices.length !== 0) errors.push("question.choices must be empty for text questions");
  else if (question.answerType === "choice" && (question.choices.length < 2 || question.choices.length > 8 || new Set(question.choices).size !== question.choices.length || question.choices.some((item) => typeof item !== "string" || item.length === 0))) errors.push("question.choices must contain 2 to 8 unique non-empty choices");
}

export function validatePreparationEnvelope(value) {
  const errors = [];
  if (!validateObject(value, "envelope", ["outcome", "summary", "manifestPath", "question"], errors)) throw new PreparationContractError(errors);
  nonEmptyString(value.summary, "summary", errors);
  if (value.outcome === "prepared") {
    if (value.manifestPath !== "infrastructure.json") errors.push("manifestPath must be infrastructure.json for prepared");
    if (value.question !== null) errors.push("question must be null for prepared");
  } else if (value.outcome === "needs_input") {
    if (value.manifestPath !== null) errors.push("manifestPath must be null for needs_input");
    validateQuestion(value.question, errors);
  } else errors.push("outcome must be prepared or needs_input");
  if (errors.length) throw new PreparationContractError(errors);
  return cloneAndFreeze(value);
}

function validateCommand(command, name, errors) {
  if (!Array.isArray(command) || command.length === 0) {
    errors.push(`commands.${name} must be a non-empty command array`);
    return;
  }
  for (const [index, argument] of command.entries()) {
    if (typeof argument !== "string" || argument.length === 0 || argument.includes("\0")) errors.push(`commands.${name}[${index}] must be a non-empty NUL-free string`);
  }
}

export function validateInfrastructureManifest(value, context = {}) {
  const errors = [];
  const entrypoints = [];
  if (!validateObject(value, "manifest", ["schemaVersion", "kind", "problemId", "id", "status", "candidate", "objective", "commands", "datasets", "resources", "files", "createdAt"], errors)) throw new PreparationContractError(errors);
  if (value.schemaVersion !== 1) errors.push("schemaVersion must be 1");
  if (value.kind !== "autoresearch-infrastructure") errors.push("kind must be autoresearch-infrastructure");
  if (!isProblemId(value.problemId)) errors.push("problemId must be a valid problem ID");
  if (typeof value.id !== "string" || !INFRASTRUCTURE_ID_PATTERN.test(value.id)) errors.push("id must be a valid infrastructure ID");
  if (value.status !== "ready") errors.push("status must be ready");
  if (context.problemId !== undefined && value.problemId !== context.problemId) errors.push("problemId disagrees with context");
  if (context.infrastructureId !== undefined && value.id !== context.infrastructureId) errors.push("id disagrees with context");

  if (validateObject(value.candidate, "candidate", ["templatePath", "writablePaths"], errors)) {
    const templateValid = safePath(value.candidate.templatePath, "candidate.templatePath", errors);
    const workspace = templateValid ? value.candidate.templatePath.slice(0, value.candidate.templatePath.lastIndexOf("/")) : "";
    if (!Array.isArray(value.candidate.writablePaths) || value.candidate.writablePaths.length === 0) errors.push("candidate.writablePaths must be a non-empty array");
    else {
      const seen = new Set();
      for (const [index, writable] of value.candidate.writablePaths.entries()) {
        const location = `candidate.writablePaths[${index}]`;
        if (!safePath(writable, location, errors)) continue;
        if (seen.has(writable)) errors.push("candidate.writablePaths must not contain duplicates");
        seen.add(writable);
        if (!workspace || writable.includes("/")) errors.push(`${location} must stay within the candidate workspace`);
      }
    }
  }

  if (validateObject(value.objective, "objective", ["metricId", "label", "direction", "acceptanceThreshold"], errors)) {
    if (typeof value.objective.metricId !== "string" || !METRIC_ID.test(value.objective.metricId)) errors.push("objective.metricId must be a lowercase identifier");
    nonEmptyString(value.objective.label, "objective.label", errors);
    if (!["maximize", "minimize"].includes(value.objective.direction)) errors.push("objective.direction must be maximize or minimize");
    if (!Number.isFinite(value.objective.acceptanceThreshold)) errors.push("objective.acceptanceThreshold must be finite");
  }

  const commandNames = ["publicCheck", "containmentCheck", "evaluateDevelopment", "reproduceBaseline"];
  if (validateObject(value.commands, "commands", commandNames, errors)) {
    for (const name of commandNames) {
      validateCommand(value.commands[name], name, errors);
    }
  }

  const datasetNames = ["public", "development", "blind"];
  if (validateObject(value.datasets, "datasets", datasetNames, errors)) {
    for (const name of datasetNames) {
      const dataset = value.datasets[name];
      if (validateObject(dataset, `datasets.${name}`, ["manifestPath", "digest"], errors)) {
        safePath(dataset.manifestPath, `datasets.${name}.manifestPath`, errors);
        if (typeof dataset.digest !== "string" || !SHA256.test(dataset.digest)) errors.push(`datasets.${name}.digest must be a lowercase SHA-256 digest`);
      }
    }
  }

  if (validateObject(value.resources, "resources", ["attemptTimeoutSeconds", "terminationGraceSeconds", "memoryMb", "network"], errors)) {
    positiveInteger(value.resources.attemptTimeoutSeconds, "resources.attemptTimeoutSeconds", errors);
    positiveInteger(value.resources.terminationGraceSeconds, "resources.terminationGraceSeconds", errors);
    positiveInteger(value.resources.memoryMb, "resources.memoryMb", errors);
    if (!["denied", "restricted"].includes(value.resources.network)) errors.push("resources.network must be denied or restricted");
  }

  const filePaths = new Set();
  if (!Array.isArray(value.files) || value.files.length === 0) errors.push("files must be a non-empty array");
  else for (const [index, file] of value.files.entries()) {
    const location = `files[${index}]`;
    if (!validateObject(file, location, ["path", "sha256", "size", "executable"], errors)) continue;
    if (safePath(file.path, `${location}.path`, errors)) {
      if (filePaths.has(file.path)) errors.push("files must not contain duplicate paths");
      filePaths.add(file.path);
    }
    if (typeof file.sha256 !== "string" || !SHA256.test(file.sha256)) errors.push(`${location}.sha256 must be a lowercase SHA-256 digest`);
    positiveInteger(file.size, `${location}.size`, errors);
    if (typeof file.executable !== "boolean") errors.push(`${location}.executable must be boolean`);
  }
  if (value.candidate && typeof value.candidate.templatePath === "string") entrypoints.push(value.candidate.templatePath);
  for (const entrypoint of entrypoints) if (!filePaths.has(entrypoint)) errors.push(`missing file entry for ${entrypoint}`);

  if (typeof value.createdAt !== "string" || Number.isNaN(Date.parse(value.createdAt)) || new Date(value.createdAt).toISOString() !== value.createdAt) errors.push("createdAt must be an ISO timestamp");
  if (errors.length) throw new PreparationContractError(errors);
  return cloneAndFreeze(value);
}
