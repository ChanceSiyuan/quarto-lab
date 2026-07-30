import assert from "node:assert/strict";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";

import { checkDraft } from "../../../src/lib/drafts/check.js";

async function fixture(t: TestContext, source: string): Promise<{ repoRoot: string; draft: string }> {
  const repoRoot = await mkdtemp(path.join(tmpdir(), "research-loop-draft-check-"));
  t.after(() => rm(repoRoot, { recursive: true, force: true }));
  await mkdir(path.join(repoRoot, "drafts", "topic"), { recursive: true });
  await mkdir(path.join(repoRoot, "literature"), { recursive: true });
  await writeFile(path.join(repoRoot, "literature", "ref.bib"), [
    "@article{paper,",
    "  title = {A Paper},",
    "  author = {Ada Author},",
    "  year = {2026},",
    "  keywords = {theory}",
    "}",
    "",
  ].join("\n"));
  const draft = "drafts/topic/note.qmd";
  await writeFile(path.join(repoRoot, draft), source);
  return { repoRoot, draft };
}

test("a promotion-ready draft passes its single-file review gate", async (t) => {
  const { repoRoot, draft } = await fixture(t, [
    "---",
    "title: A useful result",
    "description: A concise explanation of the result.",
    "categories:",
    "  - theory",
    "---",
    "",
    "The evidence is discussed in @paper.",
    "",
    "::: {#lem-example}",
    "A lemma remains valid Quarto content.",
    ":::",
    "",
  ].join("\n"));

  assert.deepEqual(await checkDraft({ repoRoot, requestedFile: draft }), {
    ok: true,
    relativePath: draft,
    diagnostics: [],
  });
});

test("a promotion-ready draft may include aliases after the required fields", async (t) => {
  const { repoRoot, draft } = await fixture(t, [
    "---",
    "title: A useful result",
    "description: A concise explanation of the result.",
    "categories: [theory]",
    "aliases: [useful theorem, alternate result]",
    "---",
    "",
    "The evidence is discussed in @paper.",
    "",
  ].join("\n"));

  assert.deepEqual(await checkDraft({ repoRoot, requestedFile: draft }), {
    ok: true,
    relativePath: draft,
    diagnostics: [],
  });
});

test("the gate reports frontmatter, category, and citation problems together", async (t) => {
  const { repoRoot, draft } = await fixture(t, [
    "---",
    "title: Broken note",
    "date: 2026-07-30",
    "categories: [misc]",
    "---",
    "",
    "Unsupported evidence @missing.",
    "",
  ].join("\n"));

  const result = await checkDraft({ repoRoot, requestedFile: draft });
  assert.equal(result.ok, false);
  assert.ok(result.diagnostics.some(({ code }) => code === "DRAFT_FRONTMATTER_FIELDS"));
  assert.ok(result.diagnostics.some(({ code }) => code === "DESCRIPTION_REQUIRED"));
  assert.ok(result.diagnostics.some(({ code }) => code === "CATEGORY_INVALID"));
  assert.ok(result.diagnostics.some(({ code }) => code === "CITATION_MISSING"));
});

test("the gate catches raw active content before promotion", async (t) => {
  const { repoRoot, draft } = await fixture(t, [
    "---",
    "title: Unsafe note",
    "description: This should not be promoted yet.",
    "categories: [codes]",
    "---",
    "",
    "<script>alert('no')</script>",
    "",
  ].join("\n"));

  const result = await checkDraft({ repoRoot, requestedFile: draft });
  assert.ok(result.diagnostics.some(({ code }) => code === "SCRIPT_FORBIDDEN"));
});

test("the gate refuses files outside drafts", async (t) => {
  const { repoRoot } = await fixture(t, "---\ntitle: Draft\n---\n");
  await assert.rejects(
    () => checkDraft({ repoRoot, requestedFile: "knowledge/note.qmd" }),
    /outside `drafts\/`/,
  );
});
