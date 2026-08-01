import { SAFE_CITEKEY_PATTERN } from "../literature/bibliography.js";

export const COMPANION_ID_VERSION = 1 as const;
export const MAX_COMPANION_ID_CHARS = 4_096;
export const MAX_COMPANION_QUERY_CODE_POINTS = 2_048;
export const MAX_COMPANION_QUERY_UTF8_BYTES = 2_048;

const KNOWLEDGE_PREFIX = "knowledge:";
const PROBLEM_PREFIX = "problem:";
const LITERATURE_PREFIX = "literature:";
const SHA256_HEX = /^[a-f0-9]{64}$/u;
const PROBLEM_ID = /^Prob-\d{3}$/u;
const BASE64URL = /^[A-Za-z0-9_-]+$/u;

export class CompanionIdError extends Error {
  constructor(message = "invalid companion document ID") {
    super(message);
    this.name = "CompanionIdError";
  }
}

export interface KnowledgeCompanionId {
  version: typeof COMPANION_ID_VERSION;
  namespace: "knowledge";
  query: string;
  selectionDigest: string;
}

export interface ProblemCompanionId {
  version: typeof COMPANION_ID_VERSION;
  namespace: "problem";
  problemId: string;
}

export interface LiteratureCompanionId {
  version: typeof COMPANION_ID_VERSION;
  namespace: "literature";
  citekey: string;
}

export type DecodedCompanionId =
  | KnowledgeCompanionId
  | ProblemCompanionId
  | LiteratureCompanionId;

function fail(): never {
  throw new CompanionIdError();
}

function hasForbiddenControl(value: string): boolean {
  for (const character of value) {
    const code = character.codePointAt(0) ?? 0;
    if (code === 0 || code < 0x20 || code === 0x7f) return true;
  }
  return false;
}

export function assertCompanionQuery(query: string): void {
  if (
    typeof query !== "string" ||
    query.trim() === "" ||
    hasForbiddenControl(query) ||
    [...query].length > MAX_COMPANION_QUERY_CODE_POINTS ||
    Buffer.byteLength(query, "utf8") > MAX_COMPANION_QUERY_UTF8_BYTES
  ) {
    fail();
  }
}

function assertIdLength(id: string): void {
  if (typeof id !== "string" || id.length === 0 || id.length > MAX_COMPANION_ID_CHARS) {
    fail();
  }
}

function assertExactKeys(value: Record<string, unknown>, keys: readonly string[]): void {
  const actual = Object.keys(value).sort();
  const expected = [...keys].sort();
  if (actual.length !== expected.length || actual.some((key, index) => key !== expected[index])) {
    fail();
  }
}

export function encodeKnowledgeId(input: {
  query: string;
  selectionDigest: string;
}): string {
  assertCompanionQuery(input.query);
  if (!SHA256_HEX.test(input.selectionDigest)) fail();
  const payload: KnowledgeCompanionId = {
    version: COMPANION_ID_VERSION,
    namespace: "knowledge",
    query: input.query,
    selectionDigest: input.selectionDigest,
  };
  const id = `${KNOWLEDGE_PREFIX}${Buffer.from(JSON.stringify(payload), "utf8").toString("base64url")}`;
  assertIdLength(id);
  return id;
}

export function encodeProblemId(problemId: string): string {
  if (!PROBLEM_ID.test(problemId)) fail();
  return `${PROBLEM_PREFIX}${problemId}`;
}

export function encodeLiteratureId(citekey: string): string {
  if (!SAFE_CITEKEY_PATTERN.test(citekey)) fail();
  return `${LITERATURE_PREFIX}${citekey}`;
}

function decodeKnowledge(encoded: string): KnowledgeCompanionId {
  if (!BASE64URL.test(encoded)) fail();
  let source: string;
  try {
    const bytes = Buffer.from(encoded, "base64url");
    if (bytes.toString("base64url") !== encoded) fail();
    source = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return fail();
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(source);
  } catch {
    return fail();
  }
  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) fail();
  const payload = parsed as Record<string, unknown>;
  assertExactKeys(payload, ["version", "namespace", "query", "selectionDigest"]);
  if (
    payload.version !== COMPANION_ID_VERSION ||
    payload.namespace !== "knowledge" ||
    typeof payload.query !== "string" ||
    typeof payload.selectionDigest !== "string" ||
    !SHA256_HEX.test(payload.selectionDigest)
  ) {
    fail();
  }
  assertCompanionQuery(payload.query);
  return {
    version: COMPANION_ID_VERSION,
    namespace: "knowledge",
    query: payload.query,
    selectionDigest: payload.selectionDigest,
  };
}

export function decodeCompanionId(id: string): DecodedCompanionId {
  assertIdLength(id);
  if (id.startsWith(KNOWLEDGE_PREFIX)) {
    return decodeKnowledge(id.slice(KNOWLEDGE_PREFIX.length));
  }
  if (id.startsWith(PROBLEM_PREFIX)) {
    const problemId = id.slice(PROBLEM_PREFIX.length);
    if (!PROBLEM_ID.test(problemId)) fail();
    return { version: COMPANION_ID_VERSION, namespace: "problem", problemId };
  }
  if (id.startsWith(LITERATURE_PREFIX)) {
    const citekey = id.slice(LITERATURE_PREFIX.length);
    if (!SAFE_CITEKEY_PATTERN.test(citekey)) fail();
    return { version: COMPANION_ID_VERSION, namespace: "literature", citekey };
  }
  return fail();
}
