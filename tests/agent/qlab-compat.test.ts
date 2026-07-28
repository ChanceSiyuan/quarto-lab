import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { spawnSync } from "node:child_process";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..");

test("qlab exposes the Zotero metadata and materialization commands", () => {
  const result = spawnSync(path.join(ROOT, "qlab"), ["literature", "--help"], {
    cwd: ROOT,
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr);
  for (const command of ["connect", "import", "materialize", "verify", "index", "fetch", "sync"]) {
    assert.match(result.stdout, new RegExp(`\\b${command}\\b`));
  }
});

test("the Zotero import snapshot is separate from the reviewed bibliography", async () => {
  const script = await readFile(path.join(ROOT, "scripts", "qlab.ts"), "utf8");
  assert.match(script, /zotero\.bib/);
  assert.doesNotMatch(script, /writeFile\([^\n]*ref\.bib/);
});

test("drafts-preview is a local no-execute compatibility surface", async () => {
  const makefile = await readFile(path.join(ROOT, "Makefile"), "utf8");
  assert.match(makefile, /^drafts-preview:/m);
  assert.match(makefile, /quarto preview drafts --no-execute/);
  const gitignore = await readFile(path.join(ROOT, ".gitignore"), "utf8");
  assert.match(gitignore, /^\/drafts\/\.preview\/$/m);
  const config = await readFile(path.join(ROOT, "drafts", "_quarto.yml"), "utf8");
  assert.match(config, /render:\s*\n\s*- "\*\*\/\*\.qmd"/);
  assert.doesNotMatch(config, /\*\*\/\*\.md/);
});
