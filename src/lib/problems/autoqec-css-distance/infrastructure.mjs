import { AUTOQEC_INFRASTRUCTURE_RANGES } from "../research-schema.mjs";

export const CSS_DISTANCE_INFRASTRUCTURE_ENTRY_POINTS = [
  "containers/css-distance-autoresearch/candidate-entrypoint.py",
  "src/autoqec_search/css_distance_autoresearch.py",
  "src/autoqec_search/css_distance_autoresearch_batch.py",
];

export const CSS_DISTANCE_INFRASTRUCTURE_ALLOWLIST = [
  "campaigns/examples/css-distance-autoresearch/README.md",
  "campaigns/examples/css-distance-autoresearch/proposal-prompt.txt",
  "campaigns/examples/css-distance-autoresearch/research-brief.md",
  "campaigns/examples/css-distance-autoresearch/results.md",
  "campaigns/examples/css-distance-autoresearch/source.json",
  "containers/css-distance-autoresearch/evaluator.Dockerfile",
  "containers/css-distance-autoresearch/proposal.Dockerfile",
  "containers/css-distance-autoresearch/requirements.txt",
  "pyproject.toml",
  "results/css-distance-autoresearch-100/development-baseline-aggregate.json",
  "zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/hx.json",
  "zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/hz.json",
  "zoo/codes/rotated-surface-code/instances/rotated-surface-d3-example/instance.json",
];

const LOCAL_PACKAGE_ROOTS = new Map([
  ["autoqec_search", "src/autoqec_search"],
]);
const FROM_IMPORT_PATTERN = /^\s*from\s+([A-Za-z0-9_.]+|\.+[A-Za-z0-9_.]*)\s+import\s+(.+?)(?:\s*#.*)?$/;
const IMPORT_PATTERN = /^\s*import\s+(.+?)(?:\s*#.*)?$/;

export function expectedInfrastructureForAttempt(sequence, ranges = AUTOQEC_INFRASTRUCTURE_RANGES) {
  const range = ranges.find((item) => sequence >= item.first && sequence <= item.last);
  if (!range) throw new Error(`No infrastructure range for ATT-${String(sequence).padStart(3, "0")}`);
  return range;
}

export function buildCohortManifests(ranges = AUTOQEC_INFRASTRUCTURE_RANGES) {
  return ["cohort-001-100", "cohort-101-200"].map((cohort) => ({
    schemaVersion: 1,
    kind: "autoqec-css-distance-cohort",
    id: cohort,
    problemId: "Prob-001",
    attempts: ranges
      .filter((range) => range.cohort === cohort)
      .map((range) => ({
        first: range.first,
        last: range.last,
        sourceInfrastructureCommit: range.commit,
      })),
  }));
}

export async function buildInfrastructurePlan(trials, { ranges = AUTOQEC_INFRASTRUCTURE_RANGES } = {}) {
  return trials.map((trial) => {
    const range = expectedInfrastructureForAttempt(trial.sequence, ranges);
    if (trial.firstParent !== range.commit) {
      throw new Error(`infrastructure commit mismatch for ATT-${String(trial.sequence).padStart(3, "0")}: expected ${range.commit}, got ${trial.firstParent}`);
    }
    return {
      ...trial,
      sourceCommit: trial.sourceCommit ?? trial.commit,
      commit: range.commit,
      cohort: range.cohort,
      range,
    };
  });
}

export async function selectCssDistanceInfrastructurePaths({ paths, readText }) {
  const available = new Set(paths);
  const selected = new Set();
  const queue = [];
  const visited = new Set();
  const entryPoints = CSS_DISTANCE_INFRASTRUCTURE_ENTRY_POINTS.filter((path) => available.has(path));
  if (entryPoints.length === 0) {
    throw new Error("Infrastructure snapshot has no approved CSS-distance entry point");
  }

  for (const path of CSS_DISTANCE_INFRASTRUCTURE_ALLOWLIST) {
    if (available.has(path)) selected.add(path);
  }
  for (const path of entryPoints) addPythonPath(path, available, selected, queue);

  while (queue.length > 0) {
    const path = queue.shift();
    if (visited.has(path)) continue;
    visited.add(path);
    const text = await readText(path);
    for (const request of parseLocalPythonImportRequests(text, path)) {
      const resolved = resolveLocalPythonModule(request.moduleName, available);
      if (resolved.length === 0) {
        throw new Error(`Unresolved local Python import ${request.moduleName} in ${path}`);
      }
      for (const resolvedPath of resolved) addPythonPath(resolvedPath, available, selected, queue);
      for (const importedName of request.importedNames) {
        const childModule = `${request.moduleName}.${importedName}`;
        for (const childPath of resolveLocalPythonModule(childModule, available)) {
          addPythonPath(childPath, available, selected, queue);
        }
      }
    }
  }

  return {
    paths: [...selected].sort((left, right) => left.localeCompare(right)),
    entryPoints,
  };
}

function addPythonPath(path, available, selected, queue) {
  if (!available.has(path)) return;
  addPackageInitPaths(path, available, selected, queue);
  if (!selected.has(path)) {
    selected.add(path);
    if (path.endsWith(".py")) queue.push(path);
  }
}

function addPackageInitPaths(path, available, selected, queue) {
  for (const root of LOCAL_PACKAGE_ROOTS.values()) {
    if (!path.startsWith(`${root}/`)) continue;
    const rootInit = `${root}/__init__.py`;
    if (available.has(rootInit) && !selected.has(rootInit)) {
      selected.add(rootInit);
      queue.push(rootInit);
    }
    const directoryParts = path.slice(root.length + 1).split("/").slice(0, -1);
    for (let index = 1; index <= directoryParts.length; index += 1) {
      const initPath = `${root}/${directoryParts.slice(0, index).join("/")}/__init__.py`;
      if (available.has(initPath) && !selected.has(initPath)) {
        selected.add(initPath);
        queue.push(initPath);
      }
    }
  }
}

function parseLocalPythonImportRequests(text, path) {
  const requests = [];
  for (const line of text.split(/\r?\n/)) {
    const importMatch = line.match(IMPORT_PATTERN);
    if (importMatch) {
      for (const moduleName of splitImportTargets(importMatch[1])) {
        if (isLocalModule(moduleName)) requests.push({ moduleName, importedNames: [] });
      }
      continue;
    }

    const fromMatch = line.match(FROM_IMPORT_PATTERN);
    if (!fromMatch) continue;
    const moduleName = fromMatch[1].startsWith(".")
      ? resolveRelativeModule(path, fromMatch[1])
      : fromMatch[1];
    if (!isLocalModule(moduleName)) continue;
    requests.push({
      moduleName,
      importedNames: importedModuleNames(fromMatch[2]),
    });
  }
  return requests;
}

function splitImportTargets(targets) {
  return targets
    .split(",")
    .map((target) => target.trim().split(/\s+as\s+/)[0]?.trim())
    .filter(Boolean);
}

function importedModuleNames(targets) {
  if (targets.trim().startsWith("(")) return [];
  return splitImportTargets(targets).filter((name) => /^[A-Za-z_]\w*$/.test(name));
}

function isLocalModule(moduleName) {
  return [...LOCAL_PACKAGE_ROOTS.keys()].some((packageName) => moduleName === packageName || moduleName.startsWith(`${packageName}.`));
}

function resolveLocalPythonModule(moduleName, available) {
  const [packageName, ...moduleParts] = moduleName.split(".");
  const root = LOCAL_PACKAGE_ROOTS.get(packageName);
  if (!root) return [];
  const modulePath = [root, ...moduleParts].join("/");
  const candidates = moduleParts.length === 0
    ? [`${root}/__init__.py`]
    : [`${modulePath}.py`, `${modulePath}/__init__.py`];
  return candidates.filter((candidate) => available.has(candidate));
}

function resolveRelativeModule(path, moduleName) {
  const dotCount = moduleName.match(/^\.+/)?.[0].length ?? 0;
  const suffix = moduleName.slice(dotCount);
  const currentParts = pythonModuleParts(path);
  if (currentParts.length === 0) return moduleName;
  const packageParts = path.endsWith("/__init__.py") ? currentParts : currentParts.slice(0, -1);
  const base = packageParts.slice(0, packageParts.length - dotCount + 1);
  return [...base, ...suffix.split(".").filter(Boolean)].join(".");
}

function pythonModuleParts(path) {
  for (const [packageName, root] of LOCAL_PACKAGE_ROOTS) {
    if (!path.startsWith(`${root}/`)) continue;
    const suffix = path.slice(root.length + 1).replace(/\.py$/, "");
    if (suffix === "__init__") return [packageName];
    const parts = suffix.split("/");
    if (parts.at(-1) === "__init__") parts.pop();
    return [packageName, ...parts];
  }
  return [];
}
