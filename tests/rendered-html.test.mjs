/**
 * What the built Worker actually serves at `/`.
 *
 * The dashboard under `app/` is preserved verbatim from the starter and may not
 * be edited by this project, so these assertions are a fence around it rather
 * than a description of it: if a knowledge-system change ever makes the Worker
 * stop server-rendering the research dashboard, this test says so before a
 * browser does.
 *
 * The real `dist/server/index.js` is imported — not a re-render of `app/` — so
 * the build, the Worker entry point, and the route are all covered. Assertions
 * read the server-rendered body with `<script>` blocks removed, because the RSC
 * payload repeats the same strings and matching them there would pass even if
 * nothing had been rendered into the document at all.
 */

import assert from "node:assert/strict";
import test from "node:test";

/** The four pipeline stages the dashboard renders, in order. */
const stages = [
  { number: "01", name: "Discover", detail: "Mine gaps in the literature" },
  { number: "02", name: "Verify", detail: "Freeze an executable gate" },
  { number: "03", name: "Solve", detail: "Run agents and learn" },
  { number: "04", name: "Publish", detail: "Prepare external review" },
];

/** Fetches one path from the real built Worker. */
async function request(pathname) {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);

  return worker.fetch(
    new Request(`http://localhost${pathname}`, {
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
}

/** The document body with scripts removed: what the server actually rendered. */
function renderedBody(html) {
  const match = /<body\b[^>]*>([\s\S]*)<\/body>/i.exec(html);
  assert.ok(match, "the response has a <body>");
  return match[1].replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, " ");
}

/** Rendered markup as one line of visible text. */
function visibleText(markup) {
  return markup
    .replace(/<!--[\s\S]*?-->/g, "")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

test("serves the research dashboard as HTML at /", async () => {
  const response = await request("/");

  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /<title>Research Loop — Automata<\/title>/i);
});

test("server-renders the pipeline, the hero, and the current candidate", async () => {
  const html = await (await request("/")).text();
  const body = renderedBody(html);
  const text = visibleText(body);

  assert.match(body, /<span>Research Loop<\/span>/);
  assert.match(text, /Research Loop/);
  assert.match(text, /Turn open literature into verifiable research\./);
  assert.match(
    text,
    /One auditable loop to discover meaningful problems, freeze their success criteria, solve them, and prepare the results for review\./,
  );

  for (const stage of stages) {
    assert.match(body, new RegExp(`<h3>${stage.name}</h3>`), `stage ${stage.name} is rendered`);
    assert.match(text, new RegExp(`${stage.number} .*${stage.name} ${stage.detail}`));
  }

  // The dashboard starts on Verify, which is what the browser tests then drive.
  assert.match(body, /<article class="stage-card active">[\s\S]*?<h3>Verify<\/h3>/);
  assert.match(body, /<article class="stage-card complete">[\s\S]*?<h3>Discover<\/h3>/);

  assert.match(text, /CURRENT CANDIDATE QMB-001/);
  assert.match(text, /Certified timestep bounds for 1D lattice dynamics/);
  assert.match(
    text,
    /Find a tighter, machine-checkable error bound for product-formula simulation of local Hamiltonians on fresh benchmark instances\./,
  );
  assert.match(text, /NEXT ACTION/);
  assert.match(text, /Launch solver run/);
  assert.match(text, /AUDIT TRAIL Recent activity/);
  assert.match(text, /Research Loop · Automata/);
});

test("no longer serves the starter placeholder", async () => {
  const html = await (await request("/")).text();

  assert.doesNotMatch(html, /Your site is taking shape/i);
  assert.doesNotMatch(html, /Building your site/i);
  assert.doesNotMatch(html, /react-loading-skeleton/i);
  assert.doesNotMatch(html, /_sites-preview/i);
  assert.doesNotMatch(html, /codex-preview/i);
});
