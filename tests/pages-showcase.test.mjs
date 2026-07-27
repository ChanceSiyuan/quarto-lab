import assert from "node:assert/strict";
import { access, readFile, stat } from "node:fs/promises";
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
  assert.match(html, /href="\/research-loop\/problems\/QMB-001\/attempts\/ATT-005"/);
  assert.match(html, /href="\/research-loop\/assets\//);
  assert.doesNotMatch(html, /href="\/problems\/QMB-001\/attempts\//);
  assert.doesNotMatch(html, /<script\b/i);
});

test("pages showcase copies client assets", async () => {
  const assets = await stat(join(out, "assets"));
  assert.equal(assets.isDirectory(), true);
});
