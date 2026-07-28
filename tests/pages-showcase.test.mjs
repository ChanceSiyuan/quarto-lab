import assert from "node:assert/strict";
import { access, readdir, readFile, stat } from "node:fs/promises";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const root = fileURLToPath(new URL("../", import.meta.url));
const out = join(root, "out");

async function fileExists(path) {
  try {
    await access(path);
    return true;
  } catch {
    return false;
  }
}

async function collectFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...await collectFiles(path));
    } else {
      files.push(path);
    }
  }
  return files;
}

test("pages showcase writes static route files", async () => {
  for (const routeFile of [
    "index.html",
    "problems/QMB-001/index.html",
    "problems/QMB-001/attempts/ATT-001/index.html",
    "problems/QMB-001/attempts/ATT-002/index.html",
    "problems/QMB-001/attempts/ATT-003/index.html",
    "problems/QMB-001/attempts/ATT-004/index.html",
    "problems/QMB-001/attempts/ATT-005/index.html",
    ".nojekyll",
  ]) {
    assert.equal(await fileExists(join(out, routeFile)), true, `${routeFile} should exist`);
  }
});

test("pages showcase rewrites links for the repository base path", async () => {
  const html = await readFile(join(out, "problems/QMB-001/index.html"), "utf8");
  assert.match(html, /Example data - synthetic results for interface demonstration only\./);
  assert.match(html, /href="\/research-loop\/problems\/QMB-001\/attempts\/ATT-001\/"/);
  assert.match(html, /href="\/research-loop\/problems\/QMB-001\/attempts\/ATT-005\/"/);
  assert.match(html, /href="\/research-loop\/assets\//);
  assert.doesNotMatch(html, /href="\/research-loop\/problems\/QMB-001\/attempts\/ATT-\d{3}"/);
  assert.doesNotMatch(html, /href="\/problems\/QMB-001\/attempts\//);
  assert.doesNotMatch(html, /<script\b/i);
});

test("pages showcase copies client assets", async () => {
  const assets = await stat(join(out, "assets"));
  assert.equal(assets.isDirectory(), true);
});

test("pages showcase artifact contains no local agent launcher content", async () => {
  const files = await collectFiles(out);
  assert.equal(files.some((file) => file.endsWith(".js")), false);

  const textFiles = files.filter((file) => /\.(?:html|css|svg|txt|json)$/.test(file));
  for (const file of textFiles) {
    const text = await readFile(file, "utf8");
    assert.doesNotMatch(text, /codex:\/\//i, file);
    assert.doesNotMatch(text, /\/Users\/nzy\//, file);
    assert.doesNotMatch(text, /localhost:3000/, file);
    assert.doesNotMatch(text, /Cannot open Codex/, file);
    assert.doesNotMatch(text, /\+ Add problem/, file);
    assert.doesNotMatch(text, /\b(?:href|src|data-rsc-css-href)="\/assets\//, file);
    assert.doesNotMatch(text, /url\(\/assets\//, file);
  }
});
