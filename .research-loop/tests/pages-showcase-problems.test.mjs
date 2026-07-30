import assert from "node:assert/strict";
import { mkdtemp, mkdir, readFile, readdir, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  PAGES_CHALLENGE_IDS,
  PAGES_CHALLENGES,
} from "../../src/lib/pages-showcase/challenge-catalog.mjs";

const stagingModule = await import("../tooling/scripts/pages-showcase-problems.mjs").catch(() => ({}));
const {
  PAGES_PUBLIC_PROBLEM_IDS,
  createPagesShowcaseRoutes,
  stagePagesShowcaseProblems,
} = stagingModule;

const OFFICIAL_IDS = ["Prob-124", "Prob-125", "Prob-126", "Prob-127", "Prob-128"];

async function writeDisplayFiles(root, id) {
  const dir = join(root, id);
  await mkdir(join(dir, "generation"), { recursive: true });
  await writeFile(join(dir, "problem.json"), `${JSON.stringify({ id })}\n`);
  await writeFile(join(dir, "problem.md"), `# ${id}\n`);
  await writeFile(join(dir, "generation", "private.json"), "do not copy\n");
}

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), "pages-showcase-problems-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const fixtureProblemsDir = join(root, "fixture");
  const officialProblemsDir = join(root, "official");
  const stageProblemsDir = join(root, "stage");
  await writeDisplayFiles(fixtureProblemsDir, "Prob-000");
  for (const id of OFFICIAL_IDS) await writeDisplayFiles(officialProblemsDir, id);
  return { fixtureProblemsDir, officialProblemsDir, stageProblemsDir };
}

test("declares all open challenge IDs and derives their detail routes", () => {
  assert.equal(typeof createPagesShowcaseRoutes, "function");
  assert.deepEqual(PAGES_PUBLIC_PROBLEM_IDS, PAGES_CHALLENGE_IDS);
  assert.equal(PAGES_PUBLIC_PROBLEM_IDS.length, 77);
  assert.deepEqual(createPagesShowcaseRoutes(), [
    "/",
    "/problems/Prob-000",
    ...PAGES_CHALLENGE_IDS.map((id) => `/problems/${id}`),
    "/problems/Prob-000/autoresearch",
    "/problems/Prob-000/attempts/ATT-001",
    "/problems/Prob-000/attempts/ATT-002",
    "/problems/Prob-000/attempts/ATT-003",
    "/problems/Prob-000/attempts/ATT-004",
    "/problems/Prob-000/attempts/ATT-005",
  ]);
});

test("stages only display files for all allowlisted public challenges", async (t) => {
  assert.equal(typeof stagePagesShowcaseProblems, "function");
  const paths = await fixture(t);
  const result = await stagePagesShowcaseProblems(paths);
  assert.deepEqual(result.problemIds, ["Prob-000", ...PAGES_CHALLENGE_IDS]);
  assert.deepEqual((await readdir(result.problemsDir)).sort(), ["Prob-000", ...PAGES_CHALLENGE_IDS].sort());
  for (const id of PAGES_CHALLENGE_IDS) {
    assert.deepEqual((await readdir(join(result.problemsDir, id))).sort(), ["problem.json", "problem.md"]);
  }
  for (const id of OFFICIAL_IDS) {
    assert.equal(await readFile(join(result.problemsDir, id, "problem.md"), "utf8"), `# ${id}\n`);
  }
  const first = PAGES_CHALLENGES[0];
  const manifest = JSON.parse(await readFile(join(result.problemsDir, first.id, "problem.json"), "utf8"));
  assert.equal(manifest.status, "archived");
  assert.equal(manifest.title, first.title);
  assert.match(await readFile(join(result.problemsDir, first.id, "problem.md"), "utf8"), new RegExp(first.sourceUrl));
});

test("fails with the allowlisted ID and file when a public display source is missing", async (t) => {
  const paths = await fixture(t);
  await rm(join(paths.officialProblemsDir, "Prob-127", "problem.md"));
  await assert.rejects(
    stagePagesShowcaseProblems(paths),
    /Pages showcase source missing: problems\/Prob-127\/problem\.md/,
  );
});
