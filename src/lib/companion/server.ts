import { createHash, createHmac, randomUUID, timingSafeEqual } from "node:crypto";
import { createServer, type IncomingMessage, type Server as HttpServer, type ServerResponse } from "node:http";
import { realpath } from "node:fs/promises";
import path from "node:path";

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";
import * as z from "zod/v4";

import {
  CompanionInputError,
  CompanionNotFoundError,
  type CompanionContext,
} from "./context.js";
import { CompanionIdError } from "./ids.js";

export const COMPANION_MCP_INSTRUCTIONS = `QLab Companion is a read-only research context service.
Reviewed Knowledge is authoritative within this repository. Literature is external evidence. Problems are open research questions. Drafts are never exposed by this service.
Use search before fetch. Fetch a result before relying on its content. If no reviewed Knowledge match exists, say so explicitly and do not silently substitute Literature or Problems.
Never claim that this service modified files, drafts, experiments, builds, Zotero, or repository state.`;

export const DEFAULT_COMPANION_MCP_HOST = "127.0.0.1";
export const DEFAULT_COMPANION_MCP_PORT = 7_676;
export const DEFAULT_COMPANION_BODY_BYTE_LIMIT = 64 * 1_024;
export const DEFAULT_COMPANION_RESULT_BYTE_LIMIT = 1_024 * 1_024;
export const DEFAULT_COMPANION_SESSION_IDLE_MS = 15 * 60 * 1_000;

const MAX_URL_CHARS = 4_096;
const MAX_CONFIG_URL_CHARS = 2_048;
const MAX_ACCESS_TOKEN_BYTES = 4_096;
const MIN_ACCESS_TOKEN_BYTES = 32;
const READ_ONLY_ANNOTATIONS = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: false,
} as const;

const SearchResultSchema = z
  .object({
    id: z.string(),
    namespace: z.enum(["knowledge", "problem", "literature"]),
    authority: z.enum(["reviewed_knowledge", "open_problem", "external_evidence"]),
    title: z.string(),
    summary: z.string(),
    url: z.string().url(),
  })
  .strict();

const KnowledgeFileSchema = z
  .object({
    path: z.string(),
    content: z.string(),
    sha256: z.string(),
  })
  .strict();

const DocumentSchema = z
  .object({
    id: z.string(),
    namespace: z.enum(["knowledge", "problem", "literature"]),
    authority: z.enum(["reviewed_knowledge", "open_problem", "external_evidence"]),
    title: z.string(),
    url: z.string().url(),
    text: z.string(),
    metadata: z.record(z.string(), z.unknown()),
    files: z.array(KnowledgeFileSchema).optional(),
    provenance: z
      .object({
        repositoryRevision: z.string(),
        files: z.array(
          z
            .object({
              path: z.string(),
              sha256: z.string(),
            })
            .strict(),
        ),
      })
      .strict()
      .optional(),
  })
  .strict();

const ErrorSchema = z
  .object({
    code: z.enum(["invalid_input", "not_found", "result_too_large", "internal_error"]),
    message: z.string(),
  })
  .strict();

const SearchOutputSchema = z
  .object({
    status: z.enum(["ok", "error"]),
    results: z.array(SearchResultSchema).optional(),
    error: ErrorSchema.optional(),
  })
  .strict();

const FetchOutputSchema = z
  .object({
    status: z.enum(["ok", "error"]),
    document: DocumentSchema.optional(),
    error: ErrorSchema.optional(),
  })
  .strict();

type ToolPayload = z.infer<typeof SearchOutputSchema> | z.infer<typeof FetchOutputSchema>;

export interface CompanionMcpLogger {
  info(event: Readonly<Record<string, string | number | boolean>>): void;
  error(event: Readonly<Record<string, string | number | boolean>>): void;
}

export interface CreateCompanionMcpServerOptions {
  context: CompanionContext;
  accessToken: string;
  resultByteLimit?: number;
}

export interface StartCompanionMcpHttpServerOptions extends CreateCompanionMcpServerOptions {
  repoRoot: string;
  endpointBaseUrl: string;
  publicBaseUrl: string;
  host?: string;
  port?: number;
  trustedTunnelMode?: boolean;
  unsafeAllowNonLoopbackDevelopment?: boolean;
  unsafeAllowWritableRepositoryRootForDevelopment?: boolean;
  isRepositoryRootReadOnly?: (repoRoot: string) => Promise<boolean>;
  bodyByteLimit?: number;
  sessionIdleMs?: number;
  logger?: CompanionMcpLogger;
}

export interface RunningCompanionMcpHttpServer {
  readonly localUrl: URL;
  readonly endpointUrl: URL;
  readonly capabilityPath: string;
  close(): Promise<void>;
}

interface SessionRecord {
  readonly transport: StreamableHTTPServerTransport;
  readonly mcp: McpServer;
  lastActive: number;
  closing: boolean;
}

class CompanionResultLimitError extends Error {}
class RequestBoundaryError extends Error {
  constructor(readonly status: number) {
    super("request rejected");
  }
}

const NULL_LOGGER: CompanionMcpLogger = {
  info() {},
  error() {},
};

function accessTokenBytes(accessToken: string): number {
  return Buffer.byteLength(accessToken, "utf8");
}

function assertAccessToken(accessToken: string): void {
  const bytes = typeof accessToken === "string" ? accessTokenBytes(accessToken) : 0;
  if (
    bytes < MIN_ACCESS_TOKEN_BYTES ||
    bytes > MAX_ACCESS_TOKEN_BYTES ||
    /[\u0000-\u001f\u007f]/u.test(accessToken)
  ) {
    throw new CompanionInputError("access token is invalid or shorter than 32 bytes");
  }
}

export function deriveCompanionCapabilityPath(accessToken: string): string {
  assertAccessToken(accessToken);
  const capability = createHmac("sha256", accessToken)
    .update("qlab-companion-mcp-capability-v1", "utf8")
    .digest("base64url");
  return `/mcp/${capability}`;
}

function validateHttpsOrigin(
  raw: string,
  label: string,
  accessToken: string,
): URL {
  if (typeof raw !== "string" || raw.length === 0 || raw.length > MAX_CONFIG_URL_CHARS) {
    throw new CompanionInputError(`${label} is invalid`);
  }
  let url: URL;
  try {
    url = new URL(raw);
  } catch {
    throw new CompanionInputError(`${label} is invalid`);
  }
  if (
    url.protocol !== "https:" ||
    url.username !== "" ||
    url.password !== "" ||
    url.pathname !== "/" ||
    url.search !== "" ||
    url.hash !== ""
  ) {
    throw new CompanionInputError(`${label} must be a credential-free HTTPS origin`);
  }
  const encoded = encodeURIComponent(accessToken);
  if (url.href.includes(accessToken) || url.href.includes(encoded)) {
    throw new CompanionInputError(`${label} must not contain access-token text`);
  }
  return url;
}

function assertPositiveInteger(value: number, label: string, maximum: number): void {
  if (!Number.isInteger(value) || value < 1 || value > maximum) {
    throw new CompanionInputError(`${label} is invalid`);
  }
}

function isLoopbackHost(host: string): boolean {
  return host === "127.0.0.1" || host === "::1" || host === "localhost";
}

function safePathMatches(candidate: string, expected: string): boolean {
  const candidateDigest = createHash("sha256").update(candidate, "utf8").digest();
  const expectedDigest = createHash("sha256").update(expected, "utf8").digest();
  return timingSafeEqual(candidateDigest, expectedDigest);
}

function jsonResponse(
  response: ServerResponse,
  status: number,
  body: Readonly<Record<string, string>>,
): void {
  const serialized = JSON.stringify(body);
  response.writeHead(status, {
    "cache-control": "no-store",
    "content-type": "application/json; charset=utf-8",
    "content-length": Buffer.byteLength(serialized, "utf8"),
  });
  response.end(serialized);
}

function notFound(response: ServerResponse): void {
  jsonResponse(response, 404, { error: "not_found" });
}

async function readBoundedJson(request: IncomingMessage, byteLimit: number): Promise<unknown> {
  const declared = Number(request.headers["content-length"] ?? "0");
  if (Number.isFinite(declared) && declared > byteLimit) {
    request.resume();
    throw new RequestBoundaryError(413);
  }
  let bytes = 0;
  const chunks: Buffer[] = [];
  for await (const chunk of request) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    bytes += buffer.length;
    if (bytes > byteLimit) throw new RequestBoundaryError(413);
    chunks.push(buffer);
  }
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    throw new RequestBoundaryError(400);
  }
}

function safeToolError(error: unknown): ToolPayload {
  if (error instanceof CompanionInputError || error instanceof CompanionIdError) {
    return {
      status: "error",
      error: { code: "invalid_input", message: "The request input is invalid." },
    };
  }
  if (error instanceof CompanionNotFoundError) {
    return {
      status: "error",
      error: { code: "not_found", message: "The requested document was not found." },
    };
  }
  if (error instanceof CompanionResultLimitError) {
    return {
      status: "error",
      error: { code: "result_too_large", message: "The result exceeded the safe response limit." },
    };
  }
  return {
    status: "error",
    error: { code: "internal_error", message: "The read-only context request failed safely." },
  };
}

function toolResult(
  payload: ToolPayload,
  accessToken: string,
  resultByteLimit: number,
  isError = false,
) {
  const text = JSON.stringify(payload);
  if (
    Buffer.byteLength(text, "utf8") > resultByteLimit ||
    text.includes(accessToken) ||
    text.includes(encodeURIComponent(accessToken))
  ) {
    throw new CompanionResultLimitError();
  }
  return {
    content: [{ type: "text" as const, text }],
    structuredContent: JSON.parse(text) as Record<string, unknown>,
    ...(isError ? { isError: true as const } : {}),
  };
}

function safeToolResult(error: unknown) {
  const payload = safeToolError(error);
  const text = JSON.stringify(payload);
  return {
    content: [{ type: "text" as const, text }],
    structuredContent: JSON.parse(text) as Record<string, unknown>,
    isError: true as const,
  };
}

export function createCompanionMcpServer(options: CreateCompanionMcpServerOptions): McpServer {
  assertAccessToken(options.accessToken);
  const resultByteLimit = options.resultByteLimit ?? DEFAULT_COMPANION_RESULT_BYTE_LIMIT;
  if (!Number.isInteger(resultByteLimit) || resultByteLimit < 256 || resultByteLimit > 16 * 1_024 * 1_024) {
    throw new CompanionInputError("result byte limit is invalid");
  }

  const server = new McpServer(
    { name: "qlab-companion", version: "1.0.0" },
    { instructions: COMPANION_MCP_INSTRUCTIONS },
  );

  server.registerTool(
    "search",
    {
      description:
        "Search reviewed Knowledge first, then visible open Problems and external Literature. Drafts are never searched.",
      inputSchema: z.object({ query: z.string().min(1).max(2_048) }).strict(),
      outputSchema: SearchOutputSchema,
      annotations: READ_ONLY_ANNOTATIONS,
    },
    async ({ query }) => {
      try {
        const payload = { status: "ok" as const, results: await options.context.search(query) };
        return toolResult(payload, options.accessToken, resultByteLimit);
      } catch (error) {
        try {
          return toolResult(safeToolError(error), options.accessToken, resultByteLimit, true);
        } catch (resultError) {
          return safeToolResult(resultError);
        }
      }
    },
  );

  server.registerTool(
    "fetch",
    {
      description:
        "Fetch one opaque search result with its trust label and live provenance. The ID is not a repository path.",
      inputSchema: z.object({ id: z.string().min(1).max(4_096) }).strict(),
      outputSchema: FetchOutputSchema,
      annotations: READ_ONLY_ANNOTATIONS,
    },
    async ({ id }) => {
      try {
        const payload = { status: "ok" as const, document: await options.context.fetch(id) };
        return toolResult(payload, options.accessToken, resultByteLimit);
      } catch (error) {
        try {
          return toolResult(safeToolError(error), options.accessToken, resultByteLimit, true);
        } catch (resultError) {
          return safeToolResult(resultError);
        }
      }
    },
  );

  return server;
}

async function closeHttpServer(server: HttpServer): Promise<void> {
  if (!server.listening) return;
  await new Promise<void>((resolve, reject) => {
    server.close((error) => (error === undefined ? resolve() : reject(error)));
  });
}

function localOrigin(host: string, port: number): string {
  return `http://${host.includes(":") ? `[${host}]` : host}:${port}`;
}

export async function startCompanionMcpHttpServer(
  options: StartCompanionMcpHttpServerOptions,
): Promise<RunningCompanionMcpHttpServer> {
  assertAccessToken(options.accessToken);
  if (!path.isAbsolute(options.repoRoot)) {
    throw new CompanionInputError("repoRoot must be an absolute path");
  }
  const repoRoot = await realpath(options.repoRoot);
  const endpointBase = validateHttpsOrigin(
    options.endpointBaseUrl,
    "endpoint base URL",
    options.accessToken,
  );
  const publicBase = validateHttpsOrigin(
    options.publicBaseUrl,
    "public content base URL",
    options.accessToken,
  );
  if (endpointBase.href === publicBase.href) {
    throw new CompanionInputError("endpoint and public content base URLs must be distinct");
  }

  const host = options.host ?? DEFAULT_COMPANION_MCP_HOST;
  if (options.trustedTunnelMode && !isLoopbackHost(host)) {
    throw new CompanionInputError("trusted-tunnel origin must remain loopback-only");
  }
  if (!isLoopbackHost(host) && !options.unsafeAllowNonLoopbackDevelopment) {
    throw new CompanionInputError("non-loopback bind requires the unsafe development acknowledgement");
  }
  if (
    !options.unsafeAllowWritableRepositoryRootForDevelopment &&
    options.isRepositoryRootReadOnly === undefined
  ) {
    throw new CompanionInputError("an OS-level repository read-only check is required");
  }
  if (
    !options.unsafeAllowWritableRepositoryRootForDevelopment &&
    !(await options.isRepositoryRootReadOnly?.(repoRoot))
  ) {
    throw new CompanionInputError("repository root is not mounted read-only");
  }

  const port = options.port ?? DEFAULT_COMPANION_MCP_PORT;
  const bodyByteLimit = options.bodyByteLimit ?? DEFAULT_COMPANION_BODY_BYTE_LIMIT;
  const resultByteLimit = options.resultByteLimit ?? DEFAULT_COMPANION_RESULT_BYTE_LIMIT;
  const sessionIdleMs = options.sessionIdleMs ?? DEFAULT_COMPANION_SESSION_IDLE_MS;
  if (!Number.isInteger(port) || port < 0 || port > 65_535) {
    throw new CompanionInputError("port is invalid");
  }
  assertPositiveInteger(bodyByteLimit, "body byte limit", 4 * 1_024 * 1_024);
  if (!Number.isInteger(resultByteLimit) || resultByteLimit < 256 || resultByteLimit > 16 * 1_024 * 1_024) {
    throw new CompanionInputError("result byte limit is invalid");
  }
  assertPositiveInteger(sessionIdleMs, "session idle limit", 24 * 60 * 60 * 1_000);

  const capabilityPath = deriveCompanionCapabilityPath(options.accessToken);
  const endpointUrl = new URL(capabilityPath.slice(1), endpointBase);
  const logger = options.logger ?? NULL_LOGGER;
  const sessions = new Map<string, SessionRecord>();
  let closing = false;

  const closeSession = async (session: SessionRecord, expired: boolean): Promise<void> => {
    if (session.closing) return;
    session.closing = true;
    if (session.transport.sessionId !== undefined) sessions.delete(session.transport.sessionId);
    try {
      await session.mcp.close();
    } catch {
      logger.error({ event: "companion_mcp_session_close_failed" });
    }
    if (expired) logger.info({ event: "companion_mcp_session_expired" });
  };

  const handleMcpRequest = async (
    request: IncomingMessage,
    response: ServerResponse,
    parsedBody?: unknown,
  ): Promise<void> => {
    const sessionHeader = request.headers["mcp-session-id"];
    const sessionId = Array.isArray(sessionHeader) ? undefined : sessionHeader;
    const existing = sessionId === undefined ? undefined : sessions.get(sessionId);
    if (existing !== undefined) {
      existing.lastActive = Date.now();
      await existing.transport.handleRequest(request, response, parsedBody);
      existing.lastActive = Date.now();
      return;
    }
    if (request.method !== "POST" || sessionId !== undefined || !isInitializeRequest(parsedBody)) {
      notFound(response);
      return;
    }

    const holder: { record?: SessionRecord } = {};
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: randomUUID,
      enableJsonResponse: true,
      onsessioninitialized(initializedId) {
        if (holder.record !== undefined) sessions.set(initializedId, holder.record);
      },
      onsessionclosed(closedId) {
        sessions.delete(closedId);
      },
    });
    const mcp = createCompanionMcpServer({
      context: options.context,
      accessToken: options.accessToken,
      resultByteLimit,
    });
    const record: SessionRecord = { transport, mcp, lastActive: Date.now(), closing: false };
    holder.record = record;
    transport.onclose = () => {
      if (transport.sessionId !== undefined) sessions.delete(transport.sessionId);
    };
    try {
      await mcp.connect(transport);
      await transport.handleRequest(request, response, parsedBody);
      record.lastActive = Date.now();
    } catch {
      await closeSession(record, false);
      if (!response.headersSent) {
        jsonResponse(response, 500, { error: "request_failed" });
      }
    }
  };

  const httpServer = createServer((request, response) => {
    void (async () => {
      const target = request.url ?? "";
      if (
        closing ||
        target.length === 0 ||
        target.length > MAX_URL_CHARS ||
        !safePathMatches(target, capabilityPath) ||
        !["GET", "POST", "DELETE"].includes(request.method ?? "")
      ) {
        notFound(response);
        return;
      }
      if (request.method === "POST") {
        const contentType = request.headers["content-type"] ?? "";
        if (!/^application\/json(?:\s*;|$)/iu.test(contentType)) {
          jsonResponse(response, 415, { error: "unsupported_media_type" });
          return;
        }
        const body = await readBoundedJson(request, bodyByteLimit);
        await handleMcpRequest(request, response, body);
        return;
      }
      await handleMcpRequest(request, response);
    })().catch((error: unknown) => {
      if (response.headersSent) return;
      if (error instanceof RequestBoundaryError) {
        jsonResponse(response, error.status, {
          error: error.status === 413 ? "payload_too_large" : "invalid_request",
        });
        return;
      }
      logger.error({ event: "companion_mcp_request_failed" });
      jsonResponse(response, 500, { error: "request_failed" });
    });
  });

  await new Promise<void>((resolve, reject) => {
    const onError = (error: Error) => {
      httpServer.off("listening", onListening);
      reject(error);
    };
    const onListening = () => {
      httpServer.off("error", onError);
      resolve();
    };
    httpServer.once("error", onError);
    httpServer.once("listening", onListening);
    httpServer.listen(port, host);
  });

  const address = httpServer.address();
  if (address === null || typeof address === "string") {
    await closeHttpServer(httpServer);
    throw new CompanionInputError("could not determine the MCP loopback address");
  }
  const localUrl = new URL(capabilityPath, localOrigin(host, address.port));
  logger.info({
    event: "companion_mcp_started",
    host,
    port: address.port,
    trustedTunnelMode: options.trustedTunnelMode === true,
  });

  const cleanupTimer = setInterval(() => {
    const cutoff = Date.now() - sessionIdleMs;
    for (const session of sessions.values()) {
      if (session.lastActive < cutoff) void closeSession(session, true);
    }
  }, Math.max(10, Math.floor(sessionIdleMs / 2)));
  cleanupTimer.unref();

  let closePromise: Promise<void> | undefined;
  return {
    localUrl,
    endpointUrl,
    capabilityPath,
    close() {
      closePromise ??= (async () => {
        closing = true;
        clearInterval(cleanupTimer);
        await Promise.all([...sessions.values()].map((session) => closeSession(session, false)));
        await closeHttpServer(httpServer);
        logger.info({ event: "companion_mcp_stopped" });
      })();
      return closePromise;
    },
  };
}
