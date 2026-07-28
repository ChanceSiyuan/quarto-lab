import assert from "node:assert/strict";
import { access, readFile, stat } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const REPO_ROOT = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..");
const PLUGIN_ROOT = path.join(REPO_ROOT, "integrations", "zotero");

async function text(relative: string): Promise<string> {
  return readFile(path.join(REPO_ROOT, relative), "utf8");
}

test("the copied Zotero plugin has Research Loop branding and keeps its identity", async () => {
  const packageJson = JSON.parse(await text("integrations/zotero/package.json"));
  const manifest = JSON.parse(await text("integrations/zotero/manifest.json"));
  const platform = await text("integrations/zotero/src/platform.ts");

  assert.equal(packageJson.name, "research-loop-zotero-plugin");
  assert.equal(manifest.name, "Research Loop — Local Codex for Zotero");
  assert.equal(manifest.applications.zotero.id, "qlab-zotero@quarto-lab.local");
  assert.match(platform, /PLUGIN_ID = "qlab-zotero@quarto-lab\.local"/);
  assert.equal(packageJson.scripts.verify, "npm run check && npm test && npm run build");
});

test("the unchanged QLab workflow can select this repository", async () => {
  for (const required of ["AGENTS.md", "qlab", "literature", "drafts", "knowledge"]) {
    await access(path.join(REPO_ROOT, required));
  }
  assert.notEqual((await stat(path.join(REPO_ROOT, "qlab"))).mode & 0o111, 0);

  const workspace = await text("integrations/zotero/src/qlab-workspace.ts");
  const commands = await text("integrations/zotero/src/qlab-commands.ts");
  assert.match(
    workspace,
    /REQUIRED_ENTRIES = \["AGENTS\.md", "qlab", "literature", "drafts", "knowledge"\]/,
  );
  for (const command of [
    "qlab_get_paper",
    "qlab_search_literature",
    "qlab_propose_patch",
    "qlab_propose_promotion",
    "qlab_validate",
    "qlab_preview",
  ]) {
    assert.match(commands, new RegExp(`"${command}"`));
  }
});

test("the root exposes stable Zotero plugin build commands", async () => {
  const makefile = await text("Makefile");
  assert.match(makefile, /^zotero-plugin-test:/m);
  assert.match(makefile, /^zotero-plugin:/m);
  assert.match(await text(".gitignore"), /^integrations\/zotero\/(?:build|dist)\/$/m);
  await access(PLUGIN_ROOT);
});
