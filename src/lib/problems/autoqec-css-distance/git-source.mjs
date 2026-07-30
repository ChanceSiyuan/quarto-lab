import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);

export async function git(sourceDir, args, options = {}) {
  const result = await execFileAsync("git", ["-C", sourceDir, ...args], {
    maxBuffer: options.maxBuffer ?? 50 * 1024 * 1024,
    encoding: options.encoding ?? "utf8",
  });
  return result.stdout;
}

export async function assertReadableGitRepository(sourceDir) {
  const inside = (await git(sourceDir, ["rev-parse", "--is-inside-work-tree"])).trim();
  if (inside !== "true") throw new Error(`AutoQEC source is not a Git work tree: ${sourceDir}`);
}

export async function discoverTrialRefs(sourceDir) {
  const output = await git(sourceDir, [
    "for-each-ref",
    "--format=%(refname:short)",
    "refs/heads/autoresearch/css-distance",
  ]);
  return output.split(/\r?\n/).filter(Boolean).filter((ref) =>
    /^autoresearch\/css-distance\/run(?:100|200)-proposal-\d{3}$/.test(ref));
}

export async function readGitText(sourceDir, ref, path) {
  return git(sourceDir, ["show", `${ref}:${path}`]);
}

export async function readGitBlob(sourceDir, ref, path) {
  return git(sourceDir, ["show", `${ref}:${path}`], { encoding: "buffer" });
}

export async function getCommitAndFirstParent(sourceDir, ref) {
  const line = (await git(sourceDir, ["rev-list", "--parents", "-n", "1", ref])).trim();
  const [commit, firstParent] = line.split(/\s+/);
  if (!commit || !firstParent) throw new Error(`Trial ref has no first parent: ${ref}`);
  return { commit, firstParent };
}

export async function listGitTree(sourceDir, ref) {
  const output = await git(sourceDir, ["ls-tree", "-r", "--name-only", ref]);
  return output.split(/\r?\n/).filter(Boolean);
}
