import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";
import { join } from "node:path";

const root = process.cwd();

test("the repository root exposes user content and packs implementation details", () => {
  for (const path of [
    "drafts",
    "integrations",
    "knowledge",
    "literature",
    "public",
    "skills",
    "src/app",
    "src/lib",
    "src/worker",
    ".research-loop/docs",
    ".research-loop/fixtures/showcase",
    ".research-loop/tests",
    ".research-loop/tooling/scripts",
    ".research-loop/tooling/sites",
  ]) {
    assert.equal(existsSync(join(root, path)), true, `${path} should exist`);
  }

  for (const legacy of [
    "app",
    "build",
    "db",
    "docs",
    "drizzle",
    "examples",
    "lib",
    "scripts",
    "tests",
    "worker",
    ".superpowers",
    "drizzle.config.ts",
  ]) {
    assert.equal(existsSync(join(root, legacy)), false, `${legacy} should not remain at the root`);
  }
});

test("the stable qlab launcher points at packed tooling", () => {
  const launcher = readFileSync(join(root, "qlab"), "utf8");
  assert.match(launcher, /\.research-loop\/tooling\/scripts\/qlab\.ts/);
});
