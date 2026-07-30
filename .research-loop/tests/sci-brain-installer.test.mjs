import assert from "node:assert/strict";
import {
  lstat,
  mkdir,
  mkdtemp,
  readFile,
  readlink,
  rm,
  writeFile,
} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";

import {
  SCI_BRAIN_REF,
  SCI_BRAIN_REPOSITORY,
  ensureSciBrain,
} from "../../src/lib/skills/sci-brain.mjs";

async function writeSkill(root, name, body = `# ${name}\n`) {
  const skillDirectory = path.join(root, "skills", name);
  await mkdir(skillDirectory, { recursive: true });
  await writeFile(path.join(skillDirectory, "SKILL.md"), body);
}

test("does nothing when brainstorm-ideas is already available", async (t) => {
  const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "research-loop-sci-brain-"));
  t.after(() => rm(temporaryRoot, { recursive: true, force: true }));

  const codexHome = path.join(temporaryRoot, "codex");
  await writeSkill(codexHome, "brainstorm-ideas", "# existing\n");

  const result = await ensureSciBrain({
    codexHome,
    cloneRepository: async () => assert.fail("the repository should not be cloned"),
  });

  assert.equal(result.status, "available");
  assert.equal(result.skillFile, path.join(codexHome, "skills", "brainstorm-ideas", "SKILL.md"));
});

test("installs every sci-brain skill without replacing an existing skill", async (t) => {
  const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "research-loop-sci-brain-"));
  t.after(() => rm(temporaryRoot, { recursive: true, force: true }));

  const codexHome = path.join(temporaryRoot, "codex");
  const existingSurvey = path.join(codexHome, "skills", "survey");
  await mkdir(existingSurvey, { recursive: true });
  await writeFile(path.join(existingSurvey, "SKILL.md"), "# keep me\n");

  const cloneCalls = [];
  const result = await ensureSciBrain({
    codexHome,
    cloneRepository: async ({ repository, ref, destination }) => {
      cloneCalls.push({ repository, ref });
      await writeSkill(destination, "brainstorm-ideas");
      await writeSkill(destination, "survey", "# upstream survey\n");
      await mkdir(path.join(destination, "skills", "_shared"), { recursive: true });
    },
  });

  assert.deepEqual(cloneCalls, [{ repository: SCI_BRAIN_REPOSITORY, ref: SCI_BRAIN_REF }]);
  assert.equal(result.status, "installed");
  assert.deepEqual(result.installedSkills, ["brainstorm-ideas"]);
  assert.deepEqual(result.preservedSkills, ["survey"]);

  const brainstormDirectory = path.join(codexHome, "skills", "brainstorm-ideas");
  assert.equal((await lstat(brainstormDirectory)).isSymbolicLink(), true);
  assert.equal(
    await readlink(brainstormDirectory),
    path.join(codexHome, "sci-brain", "skills", "brainstorm-ideas"),
  );
  assert.equal(await readFile(path.join(existingSurvey, "SKILL.md"), "utf8"), "# keep me\n");

  const secondResult = await ensureSciBrain({
    codexHome,
    cloneRepository: async () => assert.fail("a second run should not clone"),
  });
  assert.equal(secondResult.status, "available");
});

test("rejects an installation that does not contain brainstorm-ideas", async (t) => {
  const temporaryRoot = await mkdtemp(path.join(os.tmpdir(), "research-loop-sci-brain-"));
  t.after(() => rm(temporaryRoot, { recursive: true, force: true }));

  await assert.rejects(
    ensureSciBrain({
      codexHome: path.join(temporaryRoot, "codex"),
      cloneRepository: async ({ destination }) => writeSkill(destination, "survey"),
    }),
    /brainstorm-ideas\/SKILL\.md/,
  );
});
