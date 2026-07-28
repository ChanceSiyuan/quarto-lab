import { existsSync, lstatSync, realpathSync, statSync } from "node:fs";
import { isAbsolute, relative, resolve } from "node:path";

import { INFRASTRUCTURE_ID_PATTERN, isProblemId } from "./ids.mjs";

function canonicalPath(value) {
  const absolute = resolve(value);
  let existing = absolute;
  while (!existsSync(existing)) {
    const parent = resolve(existing, "..");
    if (parent === existing) throw new Error(`No existing parent for ${value}`);
    existing = parent;
  }
  if (!statSync(existing).isDirectory()) throw new Error(`Path parent is not a directory: ${existing}`);
  return resolve(realpathSync.native(existing), relative(existing, absolute));
}

export function assertContained(path, root) {
  const lexicalRoot = resolve(root);
  const lexicalPath = resolve(path);
  const canonicalRoot = canonicalPath(root);
  const canonicalPathname = canonicalPath(path);
  const relation = relative(canonicalRoot, canonicalPathname);
  if (relation === ".." || relation.startsWith(`..${process.platform === "win32" ? "\\" : "/"}`) || isAbsolute(relation)) {
    throw new RangeError(`Path is outside root: ${path}`);
  }
  const lexicalRelation = relative(lexicalRoot, lexicalPath);
  if (lexicalRelation === ".." || lexicalRelation.startsWith(`..${process.platform === "win32" ? "\\" : "/"}`) || isAbsolute(lexicalRelation)) {
    throw new RangeError(`Path is outside root: ${path}`);
  }
  let current = lexicalRoot;
  if (existsSync(current) && lstatSync(current).isSymbolicLink()) throw new RangeError(`Path crosses a symlink: ${root}`);
  for (const part of lexicalRelation.split(/[\\/]/)) {
    if (!part) continue;
    current = resolve(current, part);
    if (existsSync(current) && lstatSync(current).isSymbolicLink()) throw new RangeError(`Path crosses a symlink: ${current}`);
  }
  return canonicalPathname;
}

export function createAutoresearchPaths(rootDir) {
  const root = resolve(rootDir);
  const jobsRoot = resolve(root, "jobs");
  const workspacesRoot = resolve(root, "workspaces");
  const problemRoot = (id) => {
    if (!isProblemId(id)) throw new TypeError("Invalid problem ID");
    return resolve(root, "problems", id);
  };
  const infrastructureRoot = (id) => resolve(problemRoot(id), "infrastructure");
  const revisionRoot = (id, revisionId) => {
    if (typeof revisionId !== "string" || !INFRASTRUCTURE_ID_PATTERN.test(revisionId)) {
      throw new TypeError("Invalid infrastructure ID");
    }
    return resolve(infrastructureRoot(id), revisionId);
  };

  return Object.freeze({ jobsRoot, workspacesRoot, problemRoot, infrastructureRoot, revisionRoot, assertContained });
}
