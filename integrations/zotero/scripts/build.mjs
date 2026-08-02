import { build } from "esbuild";
import { execFileSync } from "node:child_process";
import { cp, mkdir, readFile, rm, writeFile } from "node:fs/promises";
import { createHash } from "node:crypto";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { stageStarterTemplate } from "./starter-template.mjs";
import { createZipArchive } from "./archive-tools.mjs";

const repo = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const buildDir = path.join(repo, "build");
const root = path.join(buildDir, "xpi-root");
const content = path.join(root, "chrome", "content");
const dist = path.join(repo, "dist");
const researchLoopRoot = path.resolve(repo, "..", "..");
const REMOTE_HELPER_VERSION = "1.0.0";
const REMOTE_HELPER_TUPLES = [
  "linux-x86_64-static",
  "linux-aarch64-static",
];

async function copy(source, target) {
  await mkdir(path.dirname(target), { recursive: true });
  await cp(source, target, { recursive: true });
}

function buildNativeHelper() {
  const source = path.join(repo, "native", "dist", "zoterochat-helper");
  // Packaging must never trust a pre-existing dist binary. The universal
  // target is phony and compiles both architectures directly from the C
  // source on every invocation before the helper is copied into the XPI.
  execFileSync("make", ["-C", path.join(repo, "native"), "universal"], {
    stdio: "inherit"
  });
  return source;
}

function buildRemoteHelpers() {
  execFileSync("make", ["-C", path.join(repo, "native"), "linux-static"], {
    stdio: "inherit"
  });
  return REMOTE_HELPER_TUPLES.map((tuple) => ({
    tuple,
    source: path.join(repo, "native", "dist", "remote", tuple, "qlab-remote"),
    packaged: path.join(root, "remote", tuple, "qlab-remote"),
  }));
}

await rm(root, { recursive: true, force: true });
await mkdir(content, { recursive: true });
await mkdir(dist, { recursive: true });

const starterRoot = path.join(buildDir, "starter-root");
const starterArchive = path.join(buildDir, "research-loop-starter.zip");
await rm(starterRoot, { recursive: true, force: true });
await rm(starterArchive, { force: true });
await stageStarterTemplate(researchLoopRoot, starterRoot);
createZipArchive(starterRoot, starterArchive);
const starterBytes = await readFile(starterArchive);
const starterDigest = createHash("sha256").update(starterBytes).digest("hex");
await mkdir(path.join(root, "starter"), { recursive: true });

await build({
  entryPoints: [path.join(repo, "src", "index.ts")],
  outfile: path.join(content, "zoterochat.js"),
  bundle: true,
  platform: "browser",
  format: "iife",
  globalName: "ZoteroChatBundle",
  target: ["firefox140"],
  sourcemap: false,
  minify: false,
  legalComments: "none",
  assetNames: "fonts/[name]-[hash]",
  loader: {
    ".svg": "dataurl",
    ".woff2": "file",
    ".woff": "file",
    ".ttf": "file"
  }
});

const helper = buildNativeHelper();
const remoteHelpers = buildRemoteHelpers();
await Promise.all([
  copy(path.join(repo, "manifest.json"), path.join(root, "manifest.json")),
  copy(path.join(repo, "THIRD_PARTY_NOTICES.txt"), path.join(root, "THIRD_PARTY_NOTICES.txt")),
  copy(path.join(repo, "bootstrap.js"), path.join(root, "bootstrap.js")),
  copy(path.join(repo, "prefs.js"), path.join(root, "prefs.js")),
  copy(path.join(repo, "assets"), path.join(content, "icons")),
  copy(path.join(repo, "standalone-workbench.xhtml"), path.join(content, "standalone-workbench.xhtml")),
  copy(path.join(repo, "locale"), path.join(root, "locale")),
  copy(helper, path.join(root, "native", "zoterochat-helper")),
  copy(starterArchive, path.join(root, "starter", "research-loop-starter.zip")),
  writeFile(path.join(root, "starter", "research-loop-starter.sha256"), `${starterDigest}\n`),
  ...remoteHelpers.map(({ source, packaged }) => copy(source, packaged)),
]);

const helperBytes = await readFile(helper);
const integrity = {
  algorithm: "sha256",
  digest: createHash("sha256").update(helperBytes).digest("hex")
};
await writeFile(
  path.join(root, "native", "integrity.json"),
  JSON.stringify(integrity, null, 2) + "\n"
);

const remoteManifest = {
  schemaVersion: 1,
  helperVersion: REMOTE_HELPER_VERSION,
  artifacts: await Promise.all(remoteHelpers.map(async ({ tuple, source }) => {
    const bytes = await readFile(source);
    const digest = createHash("sha256").update(bytes).digest("hex");
    return {
      tuple,
      path: `remote/${tuple}/qlab-remote`,
      archiveSha256: digest,
      executableSha256: digest,
    };
  })),
};
await writeFile(
  path.join(root, "remote", "remote-helper-manifest.json"),
  JSON.stringify(remoteManifest, null, 2) + "\n",
);

const manifest = JSON.parse(await readFile(path.join(repo, "manifest.json"), "utf8"));
const xpiName = `Research-Loop-Zotero-${manifest.version}.xpi`;
const xpiPath = path.join(dist, xpiName);
await rm(xpiPath, { force: true });
createZipArchive(root, xpiPath);

const xpiBytes = await readFile(xpiPath);
const sha256 = createHash("sha256").update(xpiBytes).digest("hex");
await writeFile(path.join(dist, `${xpiName}.sha256`), `${sha256}  ${xpiName}\n`);
process.stdout.write(`${xpiPath}\nSHA-256 ${sha256}\n`);
