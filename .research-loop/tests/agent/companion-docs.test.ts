import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";

const root = process.cwd();

async function text(relativePath: string): Promise<string> {
  return readFile(path.join(root, relativePath), "utf8");
}

test("ChatGPT Companion documentation states the handoff and product boundary", async () => {
  const companion = await text("docs/chatgpt-companion.md");
  const flattened = companion.replace(/\s+/gu, " ");

  for (const pattern of [
    /Ask in ChatGPT ↗/,
    /paste/i,
    /explicit.*clipboard import/i,
    /no.*cookie/i,
    /no.*DOM automation/i,
    /no.*response-stream scraping/i,
    /signed out/i,
    /no Codex request or turn/i,
    /Developer Mode/i,
    /QLab app/i,
    /https:\/\/<host>\/<capability-path>/,
    /enable.*app.*destination chat/i,
    /localhost.*not.*direct/i,
    /Secure MCP Tunnel/i,
    /authenticated HTTPS reverse tunnel/i,
  ]) {
    assert.match(flattened, pattern);
  }

  assert.doesNotMatch(companion, /this repository (?:deploys|provides) a public endpoint/i);
  assert.match(flattened, /availability.*may change/i);
});

test("operator documentation specifies the deploy-time security boundary", async () => {
  const companion = await text("docs/chatgpt-companion.md");
  const flattened = companion.replace(/\s+/gu, " ");

  for (const literal of [
    "QLAB_COMPANION_ENDPOINT_BASE_URL",
    "QLAB_COMPANION_PUBLIC_BASE_URL",
    "QLAB_COMPANION_ACCESS_TOKEN",
    "npm run companion:mcp",
  ]) {
    assert.ok(companion.includes(literal), `missing ${literal}`);
  }
  for (const pattern of [
    /credential-free public-content base/i,
    /token material.*never.*citations.*copied prompts.*logs/i,
    /HTTPS/i,
    /at least 32 bytes/i,
    /rotat/i,
    /request-target.*redact/i,
    /trusted-tunnel/i,
    /reverse prox/i,
    /loopback/i,
    /read-only (?:mirror|mount)/i,
    /writable.*refus/i,
  ]) {
    assert.match(flattened, pattern);
  }
});

test("documentation preserves trust, freshness, and platform boundaries", async () => {
  const companion = await text("docs/chatgpt-companion.md");
  const flattened = companion.replace(/\s+/gu, " ");
  const zotero = await text("integrations/zotero/README.md");
  const rootReadme = await text("README.md");

  for (const pattern of [
    /reviewed knowledge.*≠.*literature.*≠.*problem.*≠.*draft/i,
    /Draft.*never.*MCP search/i,
    /frozen Zotero capsule/i,
    /live Knowledge retrieval/i,
    /repository revision/i,
    /per-file hashes/i,
    /current-session overlay/i,
    /never.*Codex history/i,
    /Linux.*complete/i,
    /macOS.*deferred/i,
    /Troubleshooting/i,
  ]) {
    assert.match(flattened, pattern);
  }
  assert.match(zotero, /Ask in ChatGPT ↗/);
  assert.match(zotero, /ChatGPT Companion/);
  assert.match(rootReadme, /docs\/chatgpt-companion\.md/);
});

test("Zotero package metadata uses one feature version", async () => {
  const packageJson = JSON.parse(await text("integrations/zotero/package.json"));
  const lock = JSON.parse(await text("integrations/zotero/package-lock.json"));
  const manifest = JSON.parse(await text("integrations/zotero/manifest.json"));

  assert.equal(packageJson.version, "0.12.0");
  assert.equal(lock.version, "0.12.0");
  assert.equal(lock.packages[""].version, "0.12.0");
  assert.equal(manifest.version, "0.12.0");
});
