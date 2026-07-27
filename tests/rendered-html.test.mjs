import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const generatedIndex = JSON.parse(
  await readFile(new URL("../.generated/problem-index.json", import.meta.url), "utf8"),
);

async function render(pathname = "/") {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}-${pathname}`);
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

test("server-renders the problem console shell", async () => {
  const response = await render();
  assert.equal(response.status, 200);
  assert.match(response.headers.get("content-type") ?? "", /^text\/html\b/i);

  const html = await response.text();
  assert.match(html, /Research Loop/);
  assert.match(html, /问题/);
  assert.match(html, /增加问题/);
  assert.match(html, /Cannot open Codex\?/);
  assert.match(html, /codex:\/\/threads\/new/);
  assert.match(html, /Accepted/);
  assert.match(html, /Solved/);
  assert.match(html, /Published/);
  for (const [label, key] of [
    ["Accepted", "accepted"],
    ["Solved", "solved"],
    ["Published", "published"],
  ]) {
    assert.match(
      html,
      new RegExp(`<dt>${label}</dt><dd>${generatedIndex.summary[key]} / ${generatedIndex.summary.target}</dd>`),
    );
  }
  assert.match(
    html,
    /<th scope="col">Problem<\/th><th scope="col">Status<\/th><th scope="col">Executable gate<\/th><th scope="col">Provenance<\/th><th scope="col">Recent activity<\/th><th scope="col">Updated<\/th><th scope="col">Open<\/th>/,
  );
  assert.doesNotMatch(html, /Turn open literature into/);
  assert.doesNotMatch(html, /Reset demo/);
  assert.doesNotMatch(html, /localStorage/);
});
