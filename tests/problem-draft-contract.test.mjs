import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import {
  DRAFT_PROBLEM_MD_HEADINGS,
  DraftStageError,
  validateStagedDraft,
} from "../lib/problems/draft-contract.mjs";
import { markdownHasHeading } from "../lib/problems/schema.mjs";

const DRAFT_MARKDOWN = [
  "Candidate Question",
  "Motivation and Context",
  "Discussion Summary",
  "Evidence Mentioned",
  "Open Qualification Questions",
].map((heading) => `## ${heading}\nConcrete draft content.`).join("\n\n");

async function makeStage({ id = "Prob-001", manifest = {}, markdown = DRAFT_MARKDOWN } = {}) {
  const rootDir = await mkdtemp(join(tmpdir(), "research-loop-draft-contract-"));
  const stageDir = join(rootDir, ".generated", "problem-staging", "run-001", id);
  await mkdir(join(stageDir, "generation"), { recursive: true });
  const now = "2026-07-28T08:00:00.000Z";
  const value = {
    schemaVersion: 1,
    id,
    title: "Candidate title",
    summary: "Candidate summary",
    status: "draft",
    gate: { type: "unspecified", readiness: "missing" },
    provenance: { sourceCount: 0 },
    lastActivity: { summary: "Draft registered from brainstorming.", at: now },
    createdAt: now,
    updatedAt: now,
    ...manifest,
  };
  await writeFile(join(stageDir, "problem.json"), `${JSON.stringify(value, null, 2)}\n`);
  await writeFile(join(stageDir, "problem.md"), `${markdown}\n`);
  await writeFile(join(stageDir, "generation", "initial-prompt.md"), "Short launch prompt.\n");
  await writeFile(join(stageDir, "generation", "transcript.md"), "## User\nCandidate discussion.\n");
  await writeFile(join(stageDir, "generation", "decision.md"), "Registered as draft after confirmation.\n");
  return { rootDir, stageDir, manifest: value };
}

test("exports the fenced-code-aware heading matcher for staged draft validation", () => {
  assert.equal(markdownHasHeading("## Candidate Question\nText", "Candidate Question"), true);
  assert.equal(markdownHasHeading("```md\n## Candidate Question\n```", "Candidate Question"), false);
});

test("validates one complete draft staged under the repository staging root", async () => {
  const fixture = await makeStage();
  const result = await validateStagedDraft({
    rootDir: fixture.rootDir,
    stageDir: fixture.stageDir,
    expectedId: "Prob-001",
  });
  assert.equal(result.manifest.id, "Prob-001");
  assert.deepEqual(DRAFT_PROBLEM_MD_HEADINGS, [
    "Candidate Question",
    "Motivation and Context",
    "Discussion Summary",
    "Evidence Mentioned",
    "Open Qualification Questions",
  ]);
});

const invalidManifests = [
  ["accepted status", { status: "accepted", gate: { type: "python", readiness: "executable" } }, /Status must be draft/],
  ["rejected status", { status: "rejected", rejection: { kind: "human", reason: "No." } }, /Status must be draft/],
  ["executable readiness", { gate: { type: "python", readiness: "executable" } }, /readiness must be missing or specified/],
  ["passed readiness", { gate: { type: "python", readiness: "passed" } }, /readiness must be missing or specified/],
  ["rejection details", { rejection: { kind: "human", reason: "No." } }, /must not contain rejection/],
];

for (const [label, manifest, pattern] of invalidManifests) {
  test(`refuses ${label}`, async () => {
    const fixture = await makeStage({ manifest });
    await assert.rejects(
      validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
      (error) => error instanceof DraftStageError && pattern.test(error.errors.join("\n")),
    );
  });
}

test("refuses a draft with a required heading missing", async () => {
  const fixture = await makeStage({ markdown: DRAFT_MARKDOWN.replace("## Evidence Mentioned\nConcrete draft content.\n\n", "") });

  await assert.rejects(
    validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
    (error) => error instanceof DraftStageError && /problem\.md is missing: Evidence Mentioned/.test(error.errors.join("\n")),
  );
});

test("does not accept a draft heading that appears only in a fenced code block", async () => {
  const markdown = DRAFT_MARKDOWN
    .replace("## Evidence Mentioned\nConcrete draft content.", "```md\n## Evidence Mentioned\nConcrete draft content.\n```");
  const fixture = await makeStage({ markdown });

  await assert.rejects(
    validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
    (error) => error instanceof DraftStageError && /problem\.md is missing: Evidence Mentioned/.test(error.errors.join("\n")),
  );
});

test("refuses an empty generation record", async () => {
  const fixture = await makeStage();
  await writeFile(join(fixture.stageDir, "generation", "transcript.md"), "\n");

  await assert.rejects(
    validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
    (error) => error instanceof DraftStageError && /transcript\.md must be non-empty/.test(error.errors.join("\n")),
  );
});

test("refuses an extra root file", async () => {
  const fixture = await makeStage();
  await writeFile(join(fixture.stageDir, "unexpected.md"), "Unexpected.\n");

  await assert.rejects(
    validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
    (error) => error instanceof DraftStageError && /stage must contain exactly/.test(error.errors.join("\n")),
  );
});

test("refuses a manifest whose ID does not match the requested ID", async () => {
  const fixture = await makeStage({ manifest: { id: "Prob-002" } });

  await assert.rejects(
    validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
    (error) => error instanceof DraftStageError && /Manifest ID must match requested ID/.test(error.errors.join("\n")),
  );
});

test("refuses mismatched registration timestamps", async () => {
  const fixture = await makeStage({ manifest: { updatedAt: "2026-07-28T08:01:00.000Z" } });

  await assert.rejects(
    validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
    (error) => error instanceof DraftStageError && /Draft registration timestamps must match/.test(error.errors.join("\n")),
  );
});

test("refuses a stage path outside the repository staging root", async () => {
  const fixture = await makeStage();
  const outsideStage = join(fixture.rootDir, "outside-stage");
  await mkdir(outsideStage);

  await assert.rejects(
    validateStagedDraft({ rootDir: fixture.rootDir, stageDir: outsideStage, expectedId: "Prob-001" }),
    (error) => error instanceof DraftStageError && /STAGE must resolve inside/.test(error.errors.join("\n")),
  );
});

test("refuses a staged file symlink that resolves outside the staging root", async () => {
  const fixture = await makeStage();
  const outsideFile = join(fixture.rootDir, "outside.md");
  await writeFile(outsideFile, DRAFT_MARKDOWN);
  await rm(join(fixture.stageDir, "problem.md"));
  await symlink(outsideFile, join(fixture.stageDir, "problem.md"));

  await assert.rejects(
    validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
    (error) => error instanceof DraftStageError && /markdown must be a regular file/.test(error.errors.join("\n")),
  );
});

test("collects manifest schema errors when problem markdown cannot be read", async () => {
  const fixture = await makeStage({ manifest: { title: "" } });
  const markdownPath = join(fixture.stageDir, "problem.md");
  await rm(markdownPath);
  await mkdir(markdownPath);

  await assert.rejects(
    validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
    (error) => error instanceof DraftStageError
      && /markdown must be a regular file/.test(error.errors.join("\n"))
      && /problem\.md cannot be read/.test(error.errors.join("\n"))
      && /title: title must be a non-empty string/.test(error.errors.join("\n")),
  );
});

test("collects schema errors when problem JSON parses to null", async () => {
  const fixture = await makeStage();
  await writeFile(join(fixture.stageDir, "problem.json"), "null\n");

  await assert.rejects(
    validateStagedDraft({ rootDir: fixture.rootDir, stageDir: fixture.stageDir, expectedId: "Prob-001" }),
    (error) => error instanceof DraftStageError
      && /manifest: Manifest must be an object/.test(error.errors.join("\n")),
  );
});
