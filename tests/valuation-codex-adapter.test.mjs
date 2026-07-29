import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

import {
  checkValuationCodexPreflight,
  runValuationResearch,
} from "../lib/valuations/codex-research-adapter.mjs";

const schemaPath = new URL("../schemas/quantum-valuation-research.schema.json", import.meta.url);
const localSchemaPath = fileURLToPath(schemaPath);

function knownEvidence(id) {
  return {
    id,
    state: "known",
    interval: { low: 1, base: 2, high: 3 },
    unit: "hours",
    visibility: "public",
    evidenceState: "reported",
    evidenceTier: "primary",
    sourceIds: [`${id}-source`],
    sources: [{ id: `${id}-source`, url: "https://example.test/source", locator: "section 1", kind: "contract" }],
  };
}

function validResearchCandidate() {
  return {
    schemaVersion: 1,
    problemId: "Prob-007",
    scope: {
      status: "supported",
      domain: "quantum-computing",
      quantumArea: "hardware-and-control",
    },
    anchorCandidates: [{
      id: "anchor-1",
      persistentId: "doi:10.1000/example",
      title: "Relevant quantum evidence",
      relevanceRationale: "It measures the relevant hardware constraint.",
      sourceUrl: "https://doi.org/10.1000/example",
    }],
    paperInclusionRules: { include: ["Directly addresses the problem."], exclude: ["Unrelated platforms."] },
    technicalStages: [],
    classicalBaseline: { description: "A documented classical workflow.", sourceUrl: "https://example.test/baseline" },
    marketEvidence: [knownEvidence("market-1")],
    atomicInputs: [knownEvidence("input-1")],
    materialAssumptions: [{
      id: "assumption-1",
      question: "What is the deployment throughput?",
      proposedValue: { state: "unknown", reason: "No public measurement." },
      sensitivityRank: 1,
      confirmationRequired: true,
    }],
    warnings: [],
  };
}

function fakeSuccessfulCodex(calls, candidate, { stderr = "", eventType = "item.completed" } = {}) {
  return (command, args, options) => {
    calls.push({ command, args, options });
    const child = new EventEmitter();
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    child.kill = () => {};
    queueMicrotask(() => {
      child.stdout.emit("data", Buffer.from(`${JSON.stringify({
        type: eventType,
        item: { type: "agent_message", text: JSON.stringify(candidate) },
      })}\n`));
      if (stderr) child.stderr.emit("data", Buffer.from(stderr));
      child.emit("exit", 0, null);
      child.emit("close", 0, null);
    });
    return child;
  };
}

function walkSchema(node, visit) {
  if (node === null || typeof node !== "object") return;
  visit(node);
  for (const value of Object.values(node)) {
    if (Array.isArray(value)) value.forEach((item) => walkSchema(item, visit));
    else walkSchema(value, visit);
  }
}

test("valuation candidate schema is strict and Codex-compatible", async () => {
  const schema = JSON.parse(await readFile(schemaPath, "utf8"));
  assert.equal(schema.additionalProperties, false);
  assert.deepEqual(schema.required, [
    "schemaVersion", "problemId", "scope", "anchorCandidates", "paperInclusionRules",
    "technicalStages", "classicalBaseline", "marketEvidence", "atomicInputs",
    "materialAssumptions", "warnings",
  ]);
  assert.equal(schema.properties.anchorCandidates.minItems, 1);
  assert.equal(schema.properties.anchorCandidates.maxItems, 10);
  assert.deepEqual(schema.properties.anchorCandidates.items.required, [
    "id", "persistentId", "title", "relevanceRationale", "sourceUrl",
  ]);
  assert.deepEqual(schema.properties.materialAssumptions.items.required, [
    "id", "question", "proposedValue", "sensitivityRank", "confirmationRequired",
  ]);
  walkSchema(schema, (node) => {
    if (Object.hasOwn(node, "enum") || Object.hasOwn(node, "const")) {
      assert.equal(typeof node.type, "string", "every enum and const has an explicit type");
    }
    for (const unsupported of ["$ref", "allOf", "anyOf", "oneOf", "not", "if", "then", "else", "patternProperties", "dependentSchemas", "uniqueItems"]) {
      assert.equal(Object.hasOwn(node, unsupported), false, `${unsupported} is unsupported by Codex output schemas`);
    }
  });
});

test("valuation preflight checks Codex version and login status", async () => {
  const calls = [];
  const result = await checkValuationCodexPreflight({
    rootDir: "/repo",
    schemaPath: localSchemaPath,
    fileExists: async () => true,
    execFileFn(command, args, options, callback) {
      calls.push({ command, args, options });
      callback(null, args[0] === "--version" ? "codex 1.0\n" : "Logged in\n", "");
    },
  });
  assert.equal(result.ok, true, result.message);
  assert.deepEqual(calls.map((call) => call.args), [["--version"], ["login", "status"]]);
  assert.deepEqual(calls.map((call) => call.options.cwd), ["/repo", "/repo"]);
});

test("valuation research runs Codex read-only with a strict schema", async () => {
  const calls = [];
  const result = await runValuationResearch({
    rootDir: "/repo",
    problem: { id: "Prob-007", title: "Fixture", summary: "Summary" },
    problemMarkdown: "Candidate question.",
    quantumScope: { status: "supported", domain: "quantum-computing", quantumArea: "hardware-and-control" },
    currentInputs: { note: "Existing public input." },
    priorSnapshotSummary: { snapshotId: "20260729T000000Z-abcdef123456" },
    schemaPath: localSchemaPath,
    spawnFn: fakeSuccessfulCodex(calls, validResearchCandidate(), { stderr: "public-source warning\n" }),
  });
  assert.equal(result.ok, true, result.message);
  assert.deepEqual(result.candidate, validResearchCandidate());
  assert.equal(result.stderr, "public-source warning\n");
  assert.match(calls[0].args.join(" "), /exec --sandbox read-only/);
  assert.equal(calls[0].args.includes("--output-last-message"), false);
  assert.equal(calls[0].options.cwd, "/repo");
  assert.equal(calls[0].options.shell, false);
  assert.match(calls[0].args.at(-1), /do not write files/i);
  assert.match(calls[0].args.at(-1), /do not claim external evidence is trusted knowledge/i);
  assert.match(calls[0].args.at(-1), /do not use company valuation or raw TAM as the problem value/i);
  assert.match(result.eventsText, /item\.completed/);
});

test("valuation research rejects a JSONL candidate that violates the schema contract", async () => {
  const result = await runValuationResearch({
    rootDir: "/repo",
    problem: { id: "Prob-007", title: "Fixture", summary: "Summary" },
    problemMarkdown: "Candidate question.",
    quantumScope: { status: "supported", domain: "quantum-computing", quantumArea: "hardware-and-control" },
    schemaPath: localSchemaPath,
    spawnFn: fakeSuccessfulCodex([], { ...validResearchCandidate(), unexpected: true }),
  });
  assert.equal(result.ok, false);
  assert.equal(result.code, "INVALID_FINAL");
  assert.match(result.message, /unsupported field: unexpected/i);
  assert.equal(result.stderr, "");
});

test("valuation research rejects nested fields forbidden by its output schema", async () => {
  const result = await runValuationResearch({
    rootDir: "/repo",
    problem: { id: "Prob-007", title: "Fixture", summary: "Summary" },
    problemMarkdown: "Candidate question.",
    quantumScope: { status: "supported", domain: "quantum-computing", quantumArea: "hardware-and-control" },
    schemaPath: localSchemaPath,
    spawnFn: fakeSuccessfulCodex([], {
      ...validResearchCandidate(),
      scope: { ...validResearchCandidate().scope, extra: true },
    }),
  });
  assert.equal(result.ok, false);
  assert.equal(result.code, "INVALID_FINAL");
  assert.match(result.message, /scope.*unsupported field/i);
});

test("valuation research ignores an agent message until its JSONL item is completed", async () => {
  const result = await runValuationResearch({
    rootDir: "/repo",
    problem: { id: "Prob-007", title: "Fixture", summary: "Summary" },
    problemMarkdown: "Candidate question.",
    quantumScope: { status: "supported", domain: "quantum-computing", quantumArea: "hardware-and-control" },
    schemaPath: localSchemaPath,
    spawnFn: fakeSuccessfulCodex([], validResearchCandidate(), { eventType: "item.updated" }),
  });
  assert.equal(result.ok, false);
  assert.equal(result.code, "INVALID_FINAL");
  assert.match(result.message, /final message/i);
});

test("valuation research terminates a timed-out child and retains stderr", async () => {
  const kills = [];
  function spawnFn() {
    const child = new EventEmitter();
    child.stdout = new EventEmitter();
    child.stderr = new EventEmitter();
    child.kill = (signal) => {
      kills.push(signal);
      child.stderr.emit("data", Buffer.from("timed out after source lookup\n"));
      child.emit("close", 1, signal);
    };
    return child;
  }
  const result = await runValuationResearch({
    rootDir: "/repo",
    problem: { id: "Prob-007", title: "Fixture", summary: "Summary" },
    problemMarkdown: "Candidate question.",
    quantumScope: { status: "supported", domain: "quantum-computing", quantumArea: "hardware-and-control" },
    schemaPath: localSchemaPath,
    spawnFn,
    timeoutMs: 5,
  });
  assert.equal(result.ok, false);
  assert.equal(result.code, "CODEX_TIMEOUT");
  assert.deepEqual(kills, ["SIGTERM"]);
  assert.equal(result.stderr, "timed out after source lookup\n");
});
