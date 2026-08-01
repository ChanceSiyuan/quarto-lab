import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdir, mkdtemp, readFile, readdir, realpath, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import test, { type TestContext } from "node:test";

import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StreamableHTTPClientTransport } from "@modelcontextprotocol/sdk/client/streamableHttp.js";
import { InMemoryTransport } from "@modelcontextprotocol/sdk/inMemory.js";

import type {
  CompanionContext,
  CompanionDocument,
  CompanionSearchResult,
} from "../../../src/lib/companion/context.js";
import {
  COMPANION_MCP_INSTRUCTIONS,
  createCompanionMcpServer,
  deriveCompanionCapabilityPath,
  startCompanionMcpHttpServer,
} from "../../../src/lib/companion/server.js";

const ACCESS_TOKEN = "0123456789abcdef0123456789abcdef";
const ENDPOINT_BASE_URL = "https://companion.example.test/";
const PUBLIC_BASE_URL = "https://knowledge.example.test/";

const searchResult: CompanionSearchResult = {
  id: "problem:Prob-001",
  namespace: "problem",
  authority: "open_problem",
  title: "Visible problem",
  summary: "A bounded public summary.",
  url: `${PUBLIC_BASE_URL}problems/Prob-001`,
};

const document: CompanionDocument = {
  id: searchResult.id,
  namespace: searchResult.namespace,
  authority: searchResult.authority,
  title: searchResult.title,
  url: searchResult.url,
  text: searchResult.summary,
  metadata: { status: "draft" },
};

function context(overrides: Partial<CompanionContext> = {}): CompanionContext {
  return {
    async search() {
      return [structuredClone(searchResult)];
    },
    async fetch() {
      return structuredClone(document);
    },
    ...overrides,
  };
}

async function treeHash(root: string): Promise<string> {
  const hash = createHash("sha256");
  const walk = async (directory: string): Promise<void> => {
    const entries = await readdir(directory, { withFileTypes: true });
    entries.sort((left, right) => left.name.localeCompare(right.name));
    for (const entry of entries) {
      const absolute = path.join(directory, entry.name);
      hash.update(`${entry.isDirectory() ? "d" : "f"}:${path.relative(root, absolute)}\0`);
      if (entry.isDirectory()) await walk(absolute);
      else hash.update(await readFile(absolute));
    }
  };
  await walk(root);
  return hash.digest("hex");
}

async function makeRepository(t: TestContext): Promise<string> {
  const root = await mkdtemp(path.join(await realpath(tmpdir()), "companion-mcp-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  await mkdir(path.join(root, "knowledge"));
  await writeFile(path.join(root, "knowledge", "index.qmd"), "# Trusted fixture\n");
  return root;
}

async function connectInMemory(server = createCompanionMcpServer({
  context: context(),
  accessToken: ACCESS_TOKEN,
})) {
  const [clientTransport, serverTransport] = InMemoryTransport.createLinkedPair();
  const client = new Client({ name: "companion-test", version: "1.0.0" });
  await server.connect(serverTransport);
  await client.connect(clientTransport);
  return { client, server };
}

test("in-memory MCP advertises only exact read-only search/fetch contracts", async (t) => {
  const { client, server } = await connectInMemory();
  t.after(async () => {
    await client.close();
    await server.close();
  });

  assert.equal(client.getInstructions(), COMPANION_MCP_INSTRUCTIONS);
  assert.match(client.getInstructions() ?? "", /read-only/i);
  assert.match(client.getInstructions() ?? "", /reviewed Knowledge/i);
  assert.match(client.getInstructions() ?? "", /Drafts are never exposed/i);

  const listed = await client.listTools();
  assert.deepEqual(listed.tools.map((tool) => tool.name), ["search", "fetch"]);
  for (const tool of listed.tools) {
    assert.deepEqual(tool.annotations, {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false,
    });
    assert.equal(tool.inputSchema.type, "object");
    assert.equal(tool.inputSchema.additionalProperties, false);
    assert.ok(tool.outputSchema);
    assert.equal(tool.outputSchema.type, "object");
  }
  assert.deepEqual(listed.tools[0]?.inputSchema.required, ["query"]);
  assert.deepEqual(listed.tools[1]?.inputSchema.required, ["id"]);

  const searched = await client.callTool({ name: "search", arguments: { query: "Ising" } });
  assert.equal(searched.isError, undefined);
  assert.deepEqual(searched.structuredContent, { status: "ok", results: [searchResult] });
  assert.equal(searched.content[0]?.type, "text");
  assert.equal(
    searched.content[0]?.type === "text" ? searched.content[0].text : "",
    JSON.stringify(searched.structuredContent),
  );

  const fetched = await client.callTool({ name: "fetch", arguments: { id: searchResult.id } });
  assert.deepEqual(fetched.structuredContent, { status: "ok", document });
  assert.equal(
    fetched.content[0]?.type === "text" ? fetched.content[0].text : "",
    JSON.stringify(fetched.structuredContent),
  );
});

test("tool failures are bounded, safe, and identical in structured and text output", async (t) => {
  const server = createCompanionMcpServer({
    context: context({
      async search() {
        throw new Error(`backend leaked ${ACCESS_TOKEN}`);
      },
      async fetch() {
        throw new Error("missing private path /home/user/repository/drafts/private.qmd");
      },
    }),
    accessToken: ACCESS_TOKEN,
  });
  const { client } = await connectInMemory(server);
  t.after(async () => {
    await client.close();
    await server.close();
  });

  for (const call of [
    { name: "search", arguments: { query: "secret" } },
    { name: "fetch", arguments: { id: "problem:Prob-999" } },
  ]) {
    const result = await client.callTool(call);
    assert.equal(result.isError, true);
    assert.equal(result.content[0]?.type, "text");
    const text = result.content[0]?.type === "text" ? result.content[0].text : "";
    assert.deepEqual(JSON.parse(text), result.structuredContent);
    assert.match(text, /internal_error/);
    assert.doesNotMatch(text, /012345|\/home\/user|private\.qmd/);
  }
});

async function startFixture(t: TestContext, overrides: Record<string, unknown> = {}) {
  const repoRoot = await makeRepository(t);
  const loggerEvents: unknown[] = [];
  const running = await startCompanionMcpHttpServer({
    context: context(),
    repoRoot,
    endpointBaseUrl: ENDPOINT_BASE_URL,
    publicBaseUrl: PUBLIC_BASE_URL,
    accessToken: ACCESS_TOKEN,
    port: 0,
    isRepositoryRootReadOnly: async () => true,
    logger: {
      info(event) {
        loggerEvents.push(event);
      },
      error(event) {
        loggerEvents.push(event);
      },
    },
    ...overrides,
  });
  t.after(() => running.close());
  return { repoRoot, loggerEvents, running };
}

test("authenticated loopback endpoint initializes and calls both tools with the SDK client", async (t) => {
  const { repoRoot, loggerEvents, running } = await startFixture(t, {
    trustedTunnelMode: true,
  });
  const before = await treeHash(repoRoot);
  const client = new Client({ name: "remote-simulation", version: "1.0.0" });
  const transport = new StreamableHTTPClientTransport(running.localUrl);
  t.after(() => client.close());

  await client.connect(transport);
  assert.deepEqual((await client.listTools()).tools.map((tool) => tool.name), ["search", "fetch"]);
  const searched = await client.callTool({ name: "search", arguments: { query: "Ising" } });
  assert.deepEqual(searched.structuredContent, { status: "ok", results: [searchResult] });
  const fetched = await client.callTool({ name: "fetch", arguments: { id: searchResult.id } });
  assert.deepEqual(fetched.structuredContent, { status: "ok", document });
  assert.equal(await treeHash(repoRoot), before);

  const serializedLogs = JSON.stringify(loggerEvents);
  assert.doesNotMatch(serializedLogs, new RegExp(ACCESS_TOKEN));
  assert.doesNotMatch(serializedLogs, new RegExp(running.capabilityPath.replaceAll("/", "\\/")));
});

test("wrong capability, missing capability, and unknown paths are indistinguishable", async (t) => {
  const { running } = await startFixture(t);
  const wrongPath = deriveCompanionCapabilityPath("fedcba9876543210fedcba9876543210");
  const responses = await Promise.all([
    fetch(new URL("/", running.localUrl)),
    fetch(new URL(wrongPath, running.localUrl)),
    fetch(new URL("/does-not-exist", running.localUrl)),
    fetch(new URL(`${running.capabilityPath}?token=${ACCESS_TOKEN}`, running.localUrl)),
  ]);
  const bodies = await Promise.all(responses.map((response) => response.text()));
  assert.deepEqual(responses.map((response) => response.status), [404, 404, 404, 404]);
  assert.equal(new Set(bodies).size, 1);
  assert.equal(bodies[0], '{"error":"not_found"}');
});

test("startup validates configuration, loopback policy, and read-only root policy", async (t) => {
  const repoRoot = await makeRepository(t);
  const valid = {
    context: context(),
    repoRoot,
    endpointBaseUrl: ENDPOINT_BASE_URL,
    publicBaseUrl: PUBLIC_BASE_URL,
    accessToken: ACCESS_TOKEN,
    port: 0,
    isRepositoryRootReadOnly: async () => true,
  };

  const invalid = [
    { accessToken: "too-short" },
    { endpointBaseUrl: "http://companion.example.test/" },
    { endpointBaseUrl: `https://companion.example.test/?token=${ACCESS_TOKEN}` },
    { endpointBaseUrl: `https://companion.example.test/${ACCESS_TOKEN}/` },
    { publicBaseUrl: "http://knowledge.example.test/" },
    { publicBaseUrl: `https://knowledge.example.test/#${ACCESS_TOKEN}` },
    { publicBaseUrl: ENDPOINT_BASE_URL },
    { resultByteLimit: 128 },
    { host: "0.0.0.0" },
    { trustedTunnelMode: true, host: "0.0.0.0", unsafeAllowNonLoopbackDevelopment: true },
  ];
  for (const change of invalid) {
    await assert.rejects(
      startCompanionMcpHttpServer({ ...valid, ...change }),
      /invalid|loopback|distinct|credential-free/i,
    );
  }

  await assert.rejects(
    startCompanionMcpHttpServer({ ...valid, isRepositoryRootReadOnly: undefined }),
    /read-only check/i,
  );
  await assert.rejects(
    startCompanionMcpHttpServer({
      ...valid,
      isRepositoryRootReadOnly: async () => false,
    }),
    /read-only/i,
  );
  const development = await startCompanionMcpHttpServer({
    ...valid,
    isRepositoryRootReadOnly: async () => false,
    unsafeAllowWritableRepositoryRootForDevelopment: true,
  });
  await development.close();

  const nonLoopbackDevelopment = await startCompanionMcpHttpServer({
    ...valid,
    host: "0.0.0.0",
    unsafeAllowNonLoopbackDevelopment: true,
  });
  await nonLoopbackDevelopment.close();
});

test("HTTP boundary enforces methods, content type, body, query, and result limits", async (t) => {
  const { running } = await startFixture(t, {
    bodyByteLimit: 256,
    resultByteLimit: 256,
    context: context({
      async search(query) {
        if (query === "large") {
          return [{ ...searchResult, summary: "x".repeat(512) }];
        }
        return [searchResult];
      },
    }),
  });

  const endpoint = running.localUrl;
  const unsupported = await fetch(endpoint, { method: "PUT" });
  assert.equal(unsupported.status, 404);
  assert.equal(await unsupported.text(), '{"error":"not_found"}');

  const wrongType = await fetch(endpoint, { method: "POST", body: "{}" });
  assert.equal(wrongType.status, 415);
  assert.doesNotMatch(await wrongType.text(), /tool|session|knowledge/i);

  const tooLarge = await fetch(endpoint, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ value: "x".repeat(512) }),
  });
  assert.equal(tooLarge.status, 413);

  const client = new Client({ name: "limit-test", version: "1.0.0" });
  t.after(() => client.close());
  await client.connect(new StreamableHTTPClientTransport(endpoint));
  const result = await client.callTool({ name: "search", arguments: { query: "large" } });
  assert.equal(result.isError, true);
  const text = result.content[0]?.type === "text" ? result.content[0].text : "";
  assert.match(text, /result_too_large/);
  assert.doesNotMatch(text, /x{100}/);
});

test("graceful close and idle-session cleanup release transports without logging secrets", async (t) => {
  const { loggerEvents, running } = await startFixture(t, { sessionIdleMs: 30 });
  const client = new Client({ name: "idle-test", version: "1.0.0" });
  await client.connect(new StreamableHTTPClientTransport(running.localUrl));
  await new Promise((resolve) => setTimeout(resolve, 90));
  assert.match(JSON.stringify(loggerEvents), /session_expired/);
  assert.doesNotMatch(JSON.stringify(loggerEvents), /mcp\/[A-Za-z0-9_-]+/);
  await assert.rejects(client.listTools());
  await running.close();
  await running.close();
});
