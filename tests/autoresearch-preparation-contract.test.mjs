import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  PreparationContractError,
  validateInfrastructureManifest,
  validatePreparationEnvelope,
} from "../lib/autoresearch/preparation-contract.mjs";

const repoRoot = path.resolve(fileURLToPath(import.meta.url), "..", "..");
const schemaPath = path.join(repoRoot, "schemas", "autoresearch-preparation-output.schema.json");

async function readSchema() {
  return JSON.parse(await readFile(schemaPath, "utf8"));
}

function validManifest() {
  return {
    schemaVersion: 1,
    kind: "autoresearch-infrastructure",
    problemId: "Prob-007",
    id: "INF-001",
    status: "ready",
    candidate: { templatePath: "candidate-template/candidate.py", writablePaths: ["candidate.py"] },
    objective: { metricId: "normalized-quality", label: "Normalized quality", direction: "maximize", acceptanceThreshold: 0.7 },
    commands: {
      publicCheck: ["python3", "public/check.py"],
      containmentCheck: ["python3", "tests/containment.py"],
      evaluateDevelopment: ["python3", "evaluator/development.py"],
      reproduceBaseline: ["python3", "baselines/run.py"],
    },
    datasets: {
      public: { manifestPath: "datasets/public.json", digest: "a".repeat(64) },
      development: { manifestPath: "datasets/development.json", digest: "b".repeat(64) },
      blind: { manifestPath: "datasets/blind.json", digest: "c".repeat(64) },
    },
    resources: { attemptTimeoutSeconds: 300, terminationGraceSeconds: 5, memoryMb: 4096, network: "denied" },
    files: [{ path: "candidate-template/candidate.py", sha256: "d".repeat(64), size: 12, executable: false }],
    createdAt: "2026-07-28T08:00:00.000Z",
  };
}

function assertInvalid(action, expectedFragments) {
  assert.throws(action, (error) => {
    assert.ok(error instanceof PreparationContractError);
    assert.equal(error.code, "invalid-preparation-contract");
    for (const fragment of expectedFragments) {
      assert.ok(error.errors.some((message) => message.includes(fragment)), `missing diagnostic: ${fragment}`);
    }
    return true;
  });
}

function assertObjectSchemasRejectUnknownFields(schema, location = "$") {
  if (Array.isArray(schema)) {
    schema.forEach((value, index) => assertObjectSchemasRejectUnknownFields(value, `${location}[${index}]`));
    return;
  }
  if (schema === null || typeof schema !== "object") return;

  if (schema.type === "object") {
    assert.equal(schema.additionalProperties, false, `${location} must reject unknown fields`);
  }
  for (const [key, value] of Object.entries(schema)) {
    assertObjectSchemasRejectUnknownFields(value, `${location}.${key}`);
  }
}

test("preparation output schema has mutually exclusive prepared and needs_input envelopes", async () => {
  const schema = await readSchema();

  assert.equal(schema.$schema, "https://json-schema.org/draft/2020-12/schema");
  assert.equal(schema.oneOf.length, 2);
  assertObjectSchemasRejectUnknownFields(schema);

  const prepared = schema.oneOf.find((branch) => branch.properties.outcome.const === "prepared");
  const needsInput = schema.oneOf.find((branch) => branch.properties.outcome.const === "needs_input");
  assert.ok(prepared, "prepared outcome branch is required");
  assert.ok(needsInput, "needs_input outcome branch is required");

  for (const branch of [prepared, needsInput]) {
    assert.deepEqual(branch.required, ["outcome", "summary", "manifestPath", "question"]);
    assert.equal(branch.properties.summary.minLength, 1);
  }

  assert.equal(prepared.properties.manifestPath.const, "infrastructure.json");
  assert.equal(prepared.properties.question.const, null);
  assert.equal(needsInput.properties.manifestPath.const, null);

  const question = needsInput.properties.question;
  assert.equal(question.oneOf.length, 2);
  for (const branch of question.oneOf) {
    assert.deepEqual(branch.required, ["id", "prompt", "answerType", "choices"]);
    assert.equal(branch.properties.id.pattern, "^[a-z][a-z0-9-]{0,63}$");
    assert.equal(branch.properties.prompt.minLength, 1);
  }

  const textQuestion = question.oneOf.find((branch) => branch.properties.answerType.const === "text");
  const choiceQuestion = question.oneOf.find((branch) => branch.properties.answerType.const === "choice");
  assert.ok(textQuestion, "text question branch is required");
  assert.ok(choiceQuestion, "choice question branch is required");
  assert.deepEqual(textQuestion.properties.choices.const, []);
  assert.equal(choiceQuestion.properties.choices.minItems, 2);
  assert.equal(choiceQuestion.properties.choices.maxItems, 8);
  assert.equal(choiceQuestion.properties.choices.uniqueItems, true);
  assert.equal(choiceQuestion.properties.choices.items.minLength, 1);
});

test("preparation envelope accepts only one complete prepared or needs_input outcome", () => {
  const prepared = validatePreparationEnvelope({ outcome: "prepared", summary: "Ready", manifestPath: "infrastructure.json", question: null });
  assert.equal(prepared.outcome, "prepared");
  assert.equal(Object.isFrozen(prepared), true);

  const needsInput = validatePreparationEnvelope({
    outcome: "needs_input", summary: "Choose a metric", manifestPath: null,
    question: { id: "metric-choice", prompt: "Which metric?", answerType: "choice", choices: ["accuracy", "f1"] },
  });
  assert.equal(needsInput.question.choices[1], "f1");
  assert.equal(Object.isFrozen(needsInput.question), true);

  assertInvalid(() => validatePreparationEnvelope({ outcome: "prepared", summary: "Ready", manifestPath: null, question: null, extra: true }), ["manifestPath", "extra"]);
  assertInvalid(() => validatePreparationEnvelope({ outcome: "needs_input", summary: "Need input", manifestPath: null, question: { id: "Bad", prompt: "", answerType: "choice", choices: ["one"] } }), ["question.id", "question.prompt", "question.choices"]);
});

test("preparation envelope requires own fields rather than accepting inherited values", () => {
  const inheritedEnvelope = Object.create({
    outcome: "prepared",
    summary: "Ready",
    manifestPath: "infrastructure.json",
    question: null,
  });

  assertInvalid(() => validatePreparationEnvelope(inheritedEnvelope), ["envelope.outcome", "envelope.summary", "envelope.manifestPath", "envelope.question"]);
});

test("infrastructure manifest returns a frozen normalized clone only when its complete host contract is valid", () => {
  const manifest = validManifest();
  const result = validateInfrastructureManifest(manifest, { problemId: "Prob-007", infrastructureId: "INF-001" });

  assert.notEqual(result, manifest);
  assert.equal(Object.isFrozen(result), true);
  assert.equal(Object.isFrozen(result.candidate.writablePaths), true);
  assert.equal(result.files.length, 1);
});

test("infrastructure manifest aggregates strict field, path, command, resource, and context diagnostics", () => {
  const manifest = validManifest();
  manifest.unexpected = true;
  manifest.problemId = "Prob-008";
  manifest.id = "INF-002";
  manifest.candidate.templatePath = "../candidate.py";
  manifest.candidate.writablePaths = ["../escape.py", "candidate.py", "candidate.py"];
  manifest.objective.metricId = "Invalid metric";
  manifest.objective.direction = "sideways";
  manifest.objective.acceptanceThreshold = Infinity;
  manifest.commands.publicCheck = [];
  manifest.commands.containmentCheck = ["python3", "bad\u0000arg"];
  manifest.datasets.public.digest = "not-a-digest";
  manifest.resources.attemptTimeoutSeconds = 0;
  manifest.resources.network = "open";
  manifest.files = [manifest.files[0], { ...manifest.files[0] }];

  assertInvalid(
    () => validateInfrastructureManifest(manifest, { problemId: "Prob-007", infrastructureId: "INF-001" }),
    ["unexpected", "problemId", "id", "templatePath", "writablePaths", "metricId", "direction", "acceptanceThreshold", "publicCheck", "containmentCheck", "datasets.public.digest", "attemptTimeoutSeconds", "network", "files", "missing file entry"],
  );
});
