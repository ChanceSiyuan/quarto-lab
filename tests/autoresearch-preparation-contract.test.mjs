import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const repoRoot = path.resolve(fileURLToPath(import.meta.url), "..", "..");
const schemaPath = path.join(repoRoot, "schemas", "autoresearch-preparation-output.schema.json");

async function readSchema() {
  return JSON.parse(await readFile(schemaPath, "utf8"));
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
