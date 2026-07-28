import { execFile } from "node:child_process";
import { cp, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { basename, dirname, extname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { promisify } from "node:util";

const root = fileURLToPath(new URL("../", import.meta.url));
const outDir = join(root, "out");
const clientDir = join(root, "dist/client");
const execFileAsync = promisify(execFile);
const vinextBin = fileURLToPath(new URL("../node_modules/.bin/vinext", import.meta.url));
const basePath = process.env.PAGES_BASE_PATH ?? "/research-loop";
const siteOrigin = process.env.PAGES_SITE_ORIGIN ?? "https://nzy1997.github.io";
const siteUrl = `${siteOrigin}${basePath}`;

const routes = [
  "/",
  "/problems/Prob-000",
  "/problems/Prob-000/attempts/ATT-001",
  "/problems/Prob-000/attempts/ATT-002",
  "/problems/Prob-000/attempts/ATT-003",
  "/problems/Prob-000/attempts/ATT-004",
  "/problems/Prob-000/attempts/ATT-005",
];

function routeToOutputPath(route) {
  const routePath = route === "/" ? "index.html" : `${route.slice(1)}/index.html`;
  return join(outDir, routePath);
}

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function canonicalizeStaticRouteLinks(html) {
  const escapedBasePath = escapeRegExp(basePath);
  return html.replace(
    new RegExp(`href="(${escapedBasePath}/problems/[^"#?]+)"`, "g"),
    (match, href) => href.endsWith("/") ? match : `href="${href}/"`,
  );
}

function rewriteHtml(html) {
  return canonicalizeStaticRouteLinks(html
    .replace(/<script\b[\s\S]*?<\/script>/gi, "")
    .replace(/<link\b[^>]*rel="modulepreload"[^>]*>/gi, "")
    .replace(/<section class="console-toolbar"[\s\S]*?<\/section>/, "")
    .replace(/<details class="codex-fallback"[\s\S]*?<\/details>/g, "")
    .replace(
      /<div class="mode-indicator">[\s\S]*?<\/div>(?=<div class="index-health)/,
      '<div class="mode-indicator"><span>Static showcase</span><code>GitHub Pages</code></div>',
    )
    .replace(/http:\/\/localhost:3000\/([^"]*)/g, `${siteUrl}/$1`)
    .replace(/="\/assets\//g, `="${basePath}/assets/`)
    .replace(/url\(\/assets\//g, `url(${basePath}/assets/`)
    .replace(/\s+href="\/problems\/([^"]*)"/g, ` href="${basePath}/problems/$1"`)
    .replace(/\s+href="\/"/g, ` href="${basePath}/"`));
}

async function listClientFiles(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...await listClientFiles(path));
    } else {
      files.push(path);
    }
  }
  return files;
}

function shouldCopyClientAsset(path) {
  const name = basename(path);
  return [".css", ".woff2", ".svg", ".png", ".ico"].includes(extname(path))
    || name === "_headers"
    || name === ".assetsignore";
}

async function copyStaticClientAssets() {
  const files = await listClientFiles(clientDir);
  for (const source of files) {
    if (!shouldCopyClientAsset(source)) {
      continue;
    }

    const target = join(outDir, relative(clientDir, source));
    await mkdir(dirname(target), { recursive: true });
    if (extname(source) === ".css") {
      const css = await readFile(source, "utf8");
      await writeFile(target, css.replace(/url\(\/assets\//g, `url(${basePath}/assets/`));
    } else {
      await cp(source, target);
    }
  }
}

async function renderRoute(worker, route) {
  const response = await worker.fetch(
    new Request(`http://localhost${route}`, {
      headers: { accept: "text/html" },
    }),
    {
      ASSETS: {
        fetch: async () => new Response("Not found", { status: 404 }),
      },
    },
    {
      waitUntil() {},
      passThroughOnException() {},
    },
  );

  if (response.status !== 200) {
    throw new Error(`Cannot snapshot ${route}: HTTP ${response.status}`);
  }

  return rewriteHtml(await response.text());
}

async function buildShowcaseApp() {
  await execFileAsync(
    process.execPath,
    [
      "scripts/build-problem-index.mjs",
      "--problems-dir", "examples/showcase/problems",
    ],
    { cwd: root, maxBuffer: 10 * 1024 * 1024 },
  );
  await execFileAsync(vinextBin, ["build"], {
    cwd: root,
    env: { ...process.env, WRANGLER_LOG_PATH: ".wrangler/wrangler.log" },
    maxBuffer: 10 * 1024 * 1024,
  });
}

async function main() {
  await buildShowcaseApp();
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });
  await copyStaticClientAssets();
  await writeFile(join(outDir, ".nojekyll"), "");

  const workerUrl = pathToFileURL(join(root, "dist/server/index.js"));
  workerUrl.searchParams.set("pages", `${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  for (const route of routes) {
    const outputPath = routeToOutputPath(route);
    await mkdir(dirname(outputPath), { recursive: true });
    await writeFile(outputPath, await renderRoute(worker, route));
    console.log(`pages showcase: wrote ${relative(root, outputPath)}`);
  }
}

await main();
