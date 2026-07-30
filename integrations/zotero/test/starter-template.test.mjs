import { execFile } from "node:child_process";
import { mkdtemp, mkdir, readFile, rm, stat, writeFile } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";

import { afterEach, describe, expect, it } from "vitest";
import {
  STARTER_COPY_PATHS,
  stageStarterTemplate,
} from "../scripts/starter-template.mjs";

const run = promisify(execFile);
const temporaryDirectories = [];

afterEach(async () => {
  await Promise.all(temporaryDirectories.splice(0).map((directory) =>
    rm(directory, { recursive: true, force: true })));
});

async function temporaryDirectory(name) {
  const directory = await mkdtemp(path.join(os.tmpdir(), `${name}-`));
  temporaryDirectories.push(directory);
  return directory;
}

describe("bundled Research Loop starter", () => {
  it("contains application infrastructure and a renderable theorem-block Draft, but no generated Knowledge", async () => {
    const researchLoopRoot = path.resolve(process.cwd(), "..", "..");
    const target = await temporaryDirectory("research-loop-starter");
    await stageStarterTemplate(researchLoopRoot, target);

    expect(STARTER_COPY_PATHS).not.toContain("knowledge");
    expect(STARTER_COPY_PATHS).not.toContain("drafts");
    await expect(stat(path.join(target, "src", "app", "page.tsx"))).resolves.toBeTruthy();
    await expect(stat(path.join(target, ".openai", "hosting.json"))).resolves.toBeTruthy();
    await expect(stat(path.join(target, "knowledge", "index.qmd"))).resolves.toBeTruthy();
    await expect(stat(path.join(target, "public", "knowledge"))).rejects.toThrow();

    const example = await readFile(
      path.join(target, "drafts", "examples", "theorem-blocks.qmd"),
      "utf8",
    );
    expect(example).toContain("{#def-vector-space");
    expect(example).toContain("{#lem-zero-unique");
    expect(example).toContain("{#thm-linear-map-zero");
    expect(example).toContain('collapse="true"');
    expect(example).toContain("categories: [theory]");
    expect(JSON.parse(await readFile(path.join(target, ".openai", "hosting.json"), "utf8")))
      .toEqual({ project_id: null, d1: null, r2: null });
  });

  it("never overwrites pre-existing Knowledge, Draft, or Literature files during initialization", async () => {
    const researchLoopRoot = path.resolve(process.cwd(), "..", "..");
    const staged = await temporaryDirectory("research-loop-staged");
    const destination = await temporaryDirectory("research-loop-user");
    const archive = path.join(await temporaryDirectory("research-loop-archive"), "starter.zip");
    await stageStarterTemplate(researchLoopRoot, staged);
    await run("/usr/bin/zip", ["-X", "-q", "-r", archive, "."], { cwd: staged });

    const privateKnowledge = "---\ntitle: Private\n---\n\nUser knowledge must survive byte-for-byte.\n";
    const privateDraft = "User's existing theorem example.\n";
    const privateBibliography = "@article{private, title={Private}}\n";
    await mkdir(path.join(destination, "knowledge"), { recursive: true });
    await mkdir(path.join(destination, "drafts", "examples"), { recursive: true });
    await mkdir(path.join(destination, "literature"), { recursive: true });
    await writeFile(path.join(destination, "knowledge", "private.qmd"), privateKnowledge);
    await writeFile(path.join(destination, "drafts", "examples", "theorem-blocks.qmd"), privateDraft);
    await writeFile(path.join(destination, "literature", "ref.bib"), privateBibliography);

    await run("/usr/bin/unzip", ["-n", "-q", archive, "-d", destination]);

    expect(await readFile(path.join(destination, "knowledge", "private.qmd"), "utf8"))
      .toBe(privateKnowledge);
    expect(await readFile(path.join(destination, "drafts", "examples", "theorem-blocks.qmd"), "utf8"))
      .toBe(privateDraft);
    expect(await readFile(path.join(destination, "literature", "ref.bib"), "utf8"))
      .toBe(privateBibliography);
    await expect(stat(path.join(destination, "src", "app", "page.tsx"))).resolves.toBeTruthy();
  });
});
