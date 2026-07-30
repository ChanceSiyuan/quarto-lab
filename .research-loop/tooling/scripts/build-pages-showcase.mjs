import { execFile } from "node:child_process";
import { cp, mkdir, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { basename, dirname, extname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { promisify } from "node:util";
import {
  createPagesShowcaseRoutes,
  stagePagesShowcaseProblems,
} from "./pages-showcase-problems.mjs";

const root = fileURLToPath(new URL("../../../", import.meta.url));
const outDir = join(root, "out");
const clientDir = join(root, "dist/client");
const knowledgeDir = join(root, "public/knowledge");
const execFileAsync = promisify(execFile);
const vinextBin = fileURLToPath(new URL("../../../node_modules/.bin/vinext", import.meta.url));
const basePath = process.env.PAGES_BASE_PATH ?? "/research-loop";
const siteOrigin = process.env.PAGES_SITE_ORIGIN ?? "https://nzy1997.github.io";
const siteUrl = `${siteOrigin}${basePath}`;
const knowledgeTextExtensions = new Set([".css", ".html", ".js", ".json", ".svg", ".txt", ".xml"]);

const routes = createPagesShowcaseRoutes();

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

function rewriteKnowledgeBasePath(text) {
  return text
    .replace(/href="\/"(?=[^>]*aria-label="Back to Research Loop home")/g, `href="${basePath}/"`)
    .replace(/([("'=])\/knowledge\//g, `$1${basePath}/knowledge/`)
    .replace(/\burl\(\/knowledge\//g, `url(${basePath}/knowledge/`);
}

function rewriteHtml(html) {
  return canonicalizeStaticRouteLinks(rewriteKnowledgeBasePath(html
    .replace(/<script\b[\s\S]*?<\/script>/gi, "")
    .replace(/<link\b[^>]*rel="modulepreload"[^>]*>/gi, "")
    .replace(
      /<a class="primary-action" href="codex:[^"]*">\+ Add problem<\/a>/g,
      '<span class="primary-action static-disabled" aria-disabled="true">+ Add problem</span>',
    )
    .replace(
      /<a class="state-action" href="codex:[^"]*">\+ Add first problem<\/a>/g,
      '<span class="state-action static-disabled" aria-disabled="true">+ Add first problem</span>',
    )
    .replace(
      /<a class="state-action" href="codex:[^"]*">Discuss in Codex<\/a>/g,
      '<span class="state-action static-disabled" aria-disabled="true">Discuss in Codex</span>',
    )
    .replace(/<details class="codex-fallback"[\s\S]*?<\/details>/g, "")
    .replace(
      /<div class="mode-indicator">[\s\S]*?<\/div>(?=<div class="index-health)/,
      '<div class="mode-indicator"><span>Static showcase</span><code>GitHub Pages</code></div>',
    )
    .replace(/http:\/\/localhost:3000\/([^"]*)/g, `${siteUrl}/$1`)
    .replace(/="\/assets\//g, `="${basePath}/assets/`)
    .replace(/url\(\/assets\//g, `url(${basePath}/assets/`)
    .replace(/\s+href="\/problems\/([^"]*)"/g, ` href="${basePath}/problems/$1"`)
    .replace(/\s+href="\/"/g, ` href="${basePath}/"`)));
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

async function rewriteCopiedKnowledgeAssets(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  for (const entry of entries) {
    const target = join(dir, entry.name);
    if (entry.isDirectory()) {
      await rewriteCopiedKnowledgeAssets(target);
      continue;
    }

    if (!knowledgeTextExtensions.has(extname(target))) {
      continue;
    }

    await writeFile(target, rewriteKnowledgeBasePath(await readFile(target, "utf8")));
  }
}

async function copyKnowledgeSite() {
  await cp(knowledgeDir, join(outDir, "knowledge"), { recursive: true });
  await rewriteCopiedKnowledgeAssets(join(outDir, "knowledge"));
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
  const { problemsDir } = await stagePagesShowcaseProblems({
    fixtureProblemsDir: join(root, ".research-loop/fixtures/showcase/problems"),
    officialProblemsDir: join(root, "problems"),
    stageProblemsDir: join(root, ".generated/pages-showcase/problems"),
  });
  await execFileAsync(
    process.execPath,
    [
      ".research-loop/tooling/scripts/build-problem-index.mjs",
      "--public",
      "--problems-dir", relative(root, problemsDir),
    ],
    { cwd: root, maxBuffer: 10 * 1024 * 1024 },
  );
  await execFileAsync(
    process.execPath,
    ["--import", "tsx", ".research-loop/tooling/scripts/knowledge.ts", "build"],
    { cwd: root, maxBuffer: 10 * 1024 * 1024 },
  );
  await execFileAsync(vinextBin, ["build"], {
    cwd: root,
    env: { ...process.env, WRANGLER_LOG_PATH: ".wrangler/wrangler.log", PAGES_STATIC_SHOWCASE: "1" },
    maxBuffer: 10 * 1024 * 1024,
  });
}

async function main() {
  await buildShowcaseApp();
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });
  await copyStaticClientAssets();
  await copyKnowledgeSite();
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
