import { execFile } from "node:child_process";
import { access, lstat, mkdir, readdir, rename, rm, symlink } from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { promisify } from "node:util";
import { randomUUID } from "node:crypto";

const execFileAsync = promisify(execFile);

export const SCI_BRAIN_REPOSITORY = "https://github.com/QuantumBFS/sci-brain.git";
export const SCI_BRAIN_REF = "v0.3.1";

async function pathExists(candidate) {
  try {
    await access(candidate);
    return true;
  } catch {
    return false;
  }
}

async function directoryEntryExists(candidate) {
  try {
    await lstat(candidate);
    return true;
  } catch (error) {
    if (error?.code === "ENOENT") return false;
    throw error;
  }
}

async function defaultCloneRepository({ repository, ref, destination }) {
  try {
    await execFileAsync("git", [
      "clone",
      "--depth",
      "1",
      "--branch",
      ref,
      "--single-branch",
      repository,
      destination,
    ]);
  } catch (error) {
    const detail = error?.stderr?.trim() || error?.message || String(error);
    throw new Error(`Unable to install sci-brain from ${repository}: ${detail}`, { cause: error });
  }
}

function defaultCodexHome() {
  return process.env.CODEX_HOME || path.join(os.homedir(), ".codex");
}

async function assertBrainstormSkill(checkoutDirectory) {
  const skillFile = path.join(checkoutDirectory, "skills", "brainstorm-ideas", "SKILL.md");
  if (!(await pathExists(skillFile))) {
    throw new Error(`The sci-brain checkout does not contain ${skillFile}`);
  }
  return skillFile;
}

async function prepareCheckout({ checkoutDirectory, cloneRepository }) {
  if (await pathExists(checkoutDirectory)) {
    await assertBrainstormSkill(checkoutDirectory);
    return;
  }

  const temporaryDirectory = `${checkoutDirectory}.installing-${randomUUID()}`;
  try {
    await cloneRepository({
      repository: SCI_BRAIN_REPOSITORY,
      ref: SCI_BRAIN_REF,
      destination: temporaryDirectory,
    });
    await assertBrainstormSkill(temporaryDirectory);

    try {
      await rename(temporaryDirectory, checkoutDirectory);
    } catch (error) {
      if (error?.code !== "EEXIST" && error?.code !== "ENOTEMPTY") throw error;
      await assertBrainstormSkill(checkoutDirectory);
    }
  } finally {
    await rm(temporaryDirectory, { recursive: true, force: true });
  }
}

export async function ensureSciBrain({
  codexHome = defaultCodexHome(),
  cloneRepository = defaultCloneRepository,
} = {}) {
  const skillsDirectory = path.join(codexHome, "skills");
  const installedBrainstormFile = path.join(skillsDirectory, "brainstorm-ideas", "SKILL.md");

  if (await pathExists(installedBrainstormFile)) {
    return { status: "available", skillFile: installedBrainstormFile };
  }

  await mkdir(codexHome, { recursive: true });
  const checkoutDirectory = path.join(codexHome, "sci-brain");
  await prepareCheckout({ checkoutDirectory, cloneRepository });

  const sourceSkillsDirectory = path.join(checkoutDirectory, "skills");
  const entries = await readdir(sourceSkillsDirectory, { withFileTypes: true });
  const skillNames = [];
  for (const entry of entries) {
    if (!entry.isDirectory() && !entry.isSymbolicLink()) continue;
    const skillFile = path.join(sourceSkillsDirectory, entry.name, "SKILL.md");
    if (await pathExists(skillFile)) skillNames.push(entry.name);
  }
  skillNames.sort();

  await mkdir(skillsDirectory, { recursive: true });
  const installedSkills = [];
  const preservedSkills = [];
  for (const skillName of skillNames) {
    const source = path.join(sourceSkillsDirectory, skillName);
    const destination = path.join(skillsDirectory, skillName);
    if (await directoryEntryExists(destination)) {
      preservedSkills.push(skillName);
      continue;
    }

    try {
      await symlink(source, destination, process.platform === "win32" ? "junction" : "dir");
      installedSkills.push(skillName);
    } catch (error) {
      if (error?.code !== "EEXIST") throw error;
      preservedSkills.push(skillName);
    }
  }

  if (!(await pathExists(installedBrainstormFile))) {
    throw new Error(
      `sci-brain was downloaded, but ${installedBrainstormFile} could not be installed; ` +
        "remove or repair the conflicting path and retry.",
    );
  }

  return {
    status: "installed",
    skillFile: installedBrainstormFile,
    checkoutDirectory,
    installedSkills,
    preservedSkills,
  };
}
