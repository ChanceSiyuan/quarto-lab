/**
 * Talks to arXiv.
 *
 * This is the repository's only outbound HTTP client, and it is written for a
 * service that is free, shared, and run by a library. Every request therefore
 * says who is calling (`research-loop/<version>`), asks for exactly one thing,
 * and gives up after a minute rather than holding a connection open on someone
 * else's machine.
 *
 * It is also written for a response nobody controls:
 *
 * - **a download is bounded twice.** `Content-Length` is checked before the
 *   body is touched, so an honest server saying "200 MiB" costs one round trip;
 *   the stream is then counted as it arrives, because a `Content-Length` is a
 *   claim and the bytes are the fact;
 * - **the deadline covers the whole exchange.** The abort signal is armed
 *   before the request and disarmed after the last chunk, so a server that
 *   sends one byte a minute is abandoned exactly like one that never answers;
 * - **a version is read, never guessed.** The Atom feed's entry ID is the only
 *   thing consulted, it must name the identifier that was asked for, and it
 *   must carry an explicit `vN`. Anything else is refused rather than defaulted
 *   to `v1`, because a wrong pin is a wrong paper.
 *
 * The `id` in a URL is not escaped, and that is deliberate: an arXiv identifier
 * is either `YYMM.NNNNN` or `archive.SC/YYMMNNN`, both validated here against
 * the same pattern the bibliography uses, and the `/` of the archival form is a
 * real path separator in `e-print/cond-mat/9803107v1`.
 */

import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

/** Where source archives come from. arXiv asks automated clients to use it. */
export const ARXIV_SOURCE_URL_BASE = "https://export.arxiv.org/e-print/";

/** Where the typeset PDF comes from. */
export const ARXIV_PDF_URL_BASE = "https://arxiv.org/pdf/";

/** The Atom API, used only to learn the current version of an identifier. */
export const ARXIV_API_URL = "https://export.arxiv.org/api/query";

/** How long any single request may take, from connect to last byte. */
export const REQUEST_TIMEOUT_MS = 60_000;

/**
 * A bare arXiv identifier with an optional explicit version, the same shape
 * `bibliography.ts` normalizes an `eprint` field to.
 */
const ARXIV_ID_PATTERN =
  /^(?:\d{4}\.\d{4,5}|[a-z]+(?:-[a-z]+)*(?:\.[A-Za-z]{2})?\/\d{7})$/;

const VERSION_PATTERN = /^v[1-9]\d*$/;

export type ArxivErrorCode =
  | "unusable-identifier"
  | "http"
  | "timeout"
  | "too-large"
  | "unusable-response";

/** Thrown for anything arXiv did, or failed to do. */
export class ArxivError extends Error {
  readonly code: ArxivErrorCode;

  constructor(code: ArxivErrorCode, message: string, options?: { cause?: unknown }) {
    super(message, options);
    this.name = "ArxivError";
    this.code = code;
  }
}

/** An identifier that has been resolved to one immutable version. */
export interface PinnedArxivId {
  /** The bare identifier, with no version. */
  id: string;
  /** The version, including its `v`: `v1`, `v2`, ... */
  version: string;
}

/** Splits a bibliography `eprint` value into its identifier and version. */
export function splitArxivIdentifier(raw: string): { id: string; version?: string } {
  const match = /^(.*?)(v[1-9]\d*)?$/.exec(raw.trim());
  const id = match?.[1] ?? "";
  const version = match?.[2];
  if (!ARXIV_ID_PATTERN.test(id)) {
    throw new ArxivError(
      "unusable-identifier",
      `"${raw}" is not an arXiv identifier this fetcher can use`,
    );
  }
  return version === undefined ? { id } : { id, version };
}

function requirePin(pin: PinnedArxivId): PinnedArxivId {
  if (!ARXIV_ID_PATTERN.test(pin.id)) {
    throw new ArxivError("unusable-identifier", `"${pin.id}" is not an arXiv identifier`);
  }
  if (!VERSION_PATTERN.test(pin.version)) {
    throw new ArxivError(
      "unusable-identifier",
      `"${pin.version}" is not an arXiv version; a pin looks like "v2"`,
    );
  }
  return pin;
}

/** The source archive URL of one pinned version. */
export function arxivSourceUrl(pin: PinnedArxivId): string {
  const { id, version } = requirePin(pin);
  return `${ARXIV_SOURCE_URL_BASE}${id}${version}`;
}

/** The PDF URL of one pinned version. */
export function arxivPdfUrl(pin: PinnedArxivId): string {
  const { id, version } = requirePin(pin);
  return `${ARXIV_PDF_URL_BASE}${id}${version}`;
}

const PACKAGE_JSON = path.resolve(
  fileURLToPath(import.meta.url),
  "..",
  "..",
  "..",
  "package.json",
);

let cachedUserAgent: string | undefined;

/**
 * The `User-Agent` every request carries.
 *
 * arXiv asks automated clients to identify themselves so that a misbehaving one
 * can be told apart from a browser and contacted rather than simply blocked.
 * The version comes from `package.json` so it cannot drift from the release.
 */
export async function arxivUserAgent(): Promise<string> {
  if (cachedUserAgent === undefined) {
    const { version } = JSON.parse(await readFile(PACKAGE_JSON, "utf8")) as {
      version?: string;
    };
    cachedUserAgent = `research-loop/${version ?? "0.0.0"} (literature source fetcher)`;
  }
  return cachedUserAgent;
}

export interface DownloadOptions {
  url: string;
  /** Refuse anything longer than this, declared or delivered. */
  maxBytes: number;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
  /** Sent as `Accept`; arXiv is content-negotiated for some endpoints. */
  accept?: string;
}

function isAbort(error: unknown): boolean {
  return (
    error instanceof Error && (error.name === "AbortError" || error.name === "TimeoutError")
  );
}

/**
 * Fetches a URL into memory, refusing anything over `maxBytes`.
 *
 * Returns the body exactly as it arrived: no decoding, no parsing, nothing that
 * would make the stored bytes differ from the bytes whose digest is recorded.
 */
export async function downloadBounded(options: DownloadOptions): Promise<Buffer> {
  const fetchImpl = options.fetchImpl ?? fetch;
  const timeoutMs = options.timeoutMs ?? REQUEST_TIMEOUT_MS;
  const controller = new AbortController();
  const deadline = setTimeout(() => {
    controller.abort(new Error(`no answer within ${timeoutMs} ms`));
  }, timeoutMs);

  try {
    let response: Response;
    try {
      response = await fetchImpl(options.url, {
        method: "GET",
        // arXiv answers an e-print request with a redirect to a mirror.
        redirect: "follow",
        signal: controller.signal,
        headers: {
          "user-agent": await arxivUserAgent(),
          accept: options.accept ?? "*/*",
        },
      });
    } catch (error) {
      if (isAbort(error) || controller.signal.aborted) {
        throw new ArxivError(
          "timeout",
          `"${options.url}" did not answer within ${timeoutMs} ms`,
          { cause: error },
        );
      }
      throw new ArxivError(
        "http",
        `"${options.url}" could not be reached: ${error instanceof Error ? error.message : String(error)}`,
        { cause: error },
      );
    }

    if (!response.ok) {
      throw new ArxivError(
        "http",
        `"${options.url}" answered ${response.status} ${response.statusText}`,
      );
    }

    const declared = response.headers.get("content-length");
    if (declared !== null && /^\d+$/.test(declared) && Number(declared) > options.maxBytes) {
      throw new ArxivError(
        "too-large",
        `"${options.url}" declares ${declared} bytes, over the ${options.maxBytes}-byte ceiling`,
      );
    }

    const body = response.body;
    if (body === null) {
      throw new ArxivError("unusable-response", `"${options.url}" answered with no body`);
    }

    const chunks: Buffer[] = [];
    let total = 0;
    try {
      for await (const chunk of body as unknown as AsyncIterable<Uint8Array>) {
        total += chunk.byteLength;
        if (total > options.maxBytes) {
          throw new ArxivError(
            "too-large",
            `"${options.url}" sent more than the ${options.maxBytes}-byte ceiling`,
          );
        }
        chunks.push(Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength));
      }
    } catch (error) {
      if (error instanceof ArxivError) {
        throw error;
      }
      if (isAbort(error) || controller.signal.aborted) {
        throw new ArxivError(
          "timeout",
          `"${options.url}" stopped sending before it finished, after ${timeoutMs} ms`,
          { cause: error },
        );
      }
      throw new ArxivError(
        "unusable-response",
        `"${options.url}" could not be read: ${error instanceof Error ? error.message : String(error)}`,
        { cause: error },
      );
    }

    return Buffer.concat(chunks);
  } finally {
    clearTimeout(deadline);
  }
}

/** The Atom feed is small; a version lookup that needs more is not one. */
const ATOM_RESPONSE_LIMIT = 1024 * 1024;

/**
 * Asks arXiv which version an identifier currently resolves to.
 *
 * The answer is taken from the entry ID (`http://arxiv.org/abs/1610.03042v2`)
 * and nowhere else: the feed's own `<id>` echoes the query, and a title or a
 * summary is prose. The identifier in that URL has to be the one that was
 * asked about, so a feed that answered with a different paper is refused
 * instead of pinned.
 */
export async function resolveLatestArxivVersion(options: {
  id: string;
  fetchImpl?: typeof fetch;
  timeoutMs?: number;
}): Promise<string> {
  if (!ARXIV_ID_PATTERN.test(options.id)) {
    throw new ArxivError("unusable-identifier", `"${options.id}" is not an arXiv identifier`);
  }

  const url = `${ARXIV_API_URL}?${new URLSearchParams({
    id_list: options.id,
    max_results: "1",
  }).toString()}`;
  const body = (
    await downloadBounded({
      url,
      maxBytes: ATOM_RESPONSE_LIMIT,
      ...(options.fetchImpl === undefined ? {} : { fetchImpl: options.fetchImpl }),
      ...(options.timeoutMs === undefined ? {} : { timeoutMs: options.timeoutMs }),
      accept: "application/atom+xml",
    })
  ).toString("utf8");

  const entry = /<entry\b[^>]*>([\s\S]*?)<\/entry>/i.exec(body);
  if (entry === null) {
    throw new ArxivError(
      "unusable-response",
      `the arXiv API returned no entry for "${options.id}"; the identifier may be withdrawn or wrong`,
    );
  }
  const identifier = /<id>\s*([^<\s]+)\s*<\/id>/i.exec(entry[1]);
  if (identifier === null) {
    throw new ArxivError(
      "unusable-response",
      `the arXiv API entry for "${options.id}" carries no identifier`,
    );
  }

  const match = /^https?:\/\/arxiv\.org\/abs\/(.+?)(v[1-9]\d*)$/i.exec(identifier[1]);
  if (match === null || match[1] !== options.id) {
    throw new ArxivError(
      "unusable-response",
      `the arXiv API answered "${options.id}" with "${identifier[1]}", which is not a versioned identifier for it`,
    );
  }
  return match[2];
}
