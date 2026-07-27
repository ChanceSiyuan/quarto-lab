import { cp, mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, relative } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = fileURLToPath(new URL("../", import.meta.url));
const outDir = join(root, "out");
const clientDir = join(root, "dist/client");
const basePath = process.env.PAGES_BASE_PATH ?? "/research-loop";

const routes = [
  "/",
  "/problems/QMB-001",
  "/problems/QMB-001/attempts/ATT-001",
  "/problems/QMB-001/attempts/ATT-002",
  "/problems/QMB-001/attempts/ATT-003",
  "/problems/QMB-001/attempts/ATT-004",
  "/problems/QMB-001/attempts/ATT-005",
];

function routeToOutputPath(route) {
  const routePath = route === "/" ? "index.html" : `${route.slice(1)}/index.html`;
  return join(outDir, routePath);
}

function rewriteHtml(html) {
  return html
    .replace(/<script\b[\s\S]*?<\/script>/gi, "")
    .replace(/\s+href="\/(assets\/[^"]*)"/g, ` href="${basePath}/$1"`)
    .replace(/\s+src="\/(assets\/[^"]*)"/g, ` src="${basePath}/$1"`)
    .replace(/\s+href="\/problems\/([^"]*)"/g, ` href="${basePath}/problems/$1"`)
    .replace(/\s+href="\/"/g, ` href="${basePath}/"`);
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

async function main() {
  await rm(outDir, { recursive: true, force: true });
  await mkdir(outDir, { recursive: true });
  await cp(clientDir, outDir, { recursive: true });
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
