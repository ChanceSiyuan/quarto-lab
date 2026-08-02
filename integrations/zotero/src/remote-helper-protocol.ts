export const REMOTE_HELPER_PROTOCOL_VERSION = 1 as const;
export const REMOTE_HELPER_VERSION = "1.0.0" as const;
export const REMOTE_HELPER_MAX_FRAME_BYTES = 8 * 1024 * 1024;
export const REMOTE_HELPER_MAX_ID_BYTES = 128;
export const REMOTE_HELPER_MAX_DIRECTORY_ENTRIES = 1024;
export const MINIMUM_CODEX_VERSION = "0.146.0" as const;

export type ActivationClientHello = Readonly<{
  kind: "hello";
  phase: "activation";
  requestId: string;
  protocolVersion: 1;
  helperVersion: string;
  activationId: string;
  mode: "browse" | "repository-handshake" | "setup-auth";
  candidateRoot: string | null;
  expectedHostInstanceId: string | null;
  requestedCapabilities: readonly string[];
}>;

export type ActivationServerHello = Readonly<{
  kind: "hello";
  phase: "activation";
  requestId: string;
  protocolVersion: 1;
  helperVersion: string;
  activationId: string;
  mode: ActivationClientHello["mode"];
  hostInstanceId: string;
  canonicalRoot: string | null;
  repositoryUuid: string | null;
  capabilities: readonly string[];
}>;

export type BoundClientHello = Readonly<{
  kind: "hello";
  phase: "bound";
  requestId: string;
  protocolVersion: 1;
  helperVersion: string;
  mode: "agent" | "repository";
  targetId: string;
  targetEpoch: number;
  canonicalRoot: string;
  expectedHostInstanceId: string;
  expectedRepositoryUuid: string;
  expectedRepositoryId: string;
  requestedCapabilities: readonly string[];
}>;

export type BoundServerHello = Readonly<{
  kind: "hello";
  phase: "bound";
  requestId: string;
  protocolVersion: 1;
  helperVersion: string;
  mode: BoundClientHello["mode"];
  targetId: string;
  targetEpoch: number;
  canonicalRoot: string;
  hostInstanceId: string;
  repositoryUuid: string;
  repositoryId: string;
  helperInstanceId: string;
  capabilities: readonly string[];
}>;

export type BoundFrameContext = Readonly<{
  protocolVersion: 1;
  helperVersion: string;
  targetId: string;
  targetEpoch: number;
  hostInstanceId: string;
  repositoryId: string;
  capabilities: readonly string[];
}>;

export type CanonicalRemoteDirectory = string & {
  readonly __canonicalRemoteDirectory: unique symbol;
};

export type RemoteDirectoryEntry = Readonly<{
  name: string;
  path: CanonicalRemoteDirectory;
  kind: "directory";
}>;

export type CodexProbeResult =
  | Readonly<{ state: "missing" }>
  | Readonly<{ state: "incompatible"; foundVersion: string; minimumVersion: string }>
  | Readonly<{ state: "unauthenticated"; version: string }>
  | Readonly<{ state: "ready"; version: string }>;

export interface ActivationRpcMap {
  "browse.home": {
    params: Record<string, never>;
    result: { path: CanonicalRemoteDirectory };
  };
  "browse.listDirectories": {
    params: { path: CanonicalRemoteDirectory };
    result: { entries: readonly RemoteDirectoryEntry[] };
  };
  "browse.canonicalize": {
    params: { input: string };
    result: { path: CanonicalRemoteDirectory };
  };
  "codex.probe": {
    params: Record<string, never>;
    result: CodexProbeResult;
  };
}

export type ActivationMethod = keyof ActivationRpcMap;

export type ActivationFrameContext = Readonly<{
  protocolVersion: 1;
  helperVersion: string;
  activationId: string;
  hostInstanceId: string;
  capabilities: readonly string[];
}>;

export type ActivationChannelBinding = Readonly<{
  mode: ActivationClientHello["mode"];
  context: ActivationFrameContext;
}>;

export type ActivationRequest = {
  [M in ActivationMethod]: ActivationFrameContext & Readonly<{
    kind: "request";
    id: string;
    method: M;
    params: ActivationRpcMap[M]["params"];
  }>;
}[ActivationMethod];

export type ActivationErrorCode =
  | "INVALID_REQUEST"
  | "METHOD_NOT_ALLOWED"
  | "PATH_REJECTED"
  | "NOT_FOUND"
  | "NOT_DIRECTORY"
  | "IDENTITY_MISMATCH"
  | "PROBE_FAILED"
  | "INTERNAL";

export type ActivationResponse = {
  [M in ActivationMethod]:
    | (ActivationFrameContext & Readonly<{
      kind: "response";
      id: string;
      method: M;
      result: ActivationRpcMap[M]["result"];
      error?: never;
    }>)
    | (ActivationFrameContext & Readonly<{
      kind: "response";
      id: string;
      method: M;
      result?: never;
      error: { code: ActivationErrorCode; message: string };
    }>);
}[ActivationMethod];

export type HelperRequest = BoundFrameContext & Readonly<{
  kind: "request";
  id: string;
}>;
export type HelperResponse = BoundFrameContext & Readonly<{
  kind: "response";
  id: string;
}>;
export type HelperEvent = BoundFrameContext & Readonly<{
  kind: "event";
  id: string;
}>;
export type StreamReady = BoundFrameContext & Readonly<{
  kind: "stream-ready";
  requestId: string;
  stream: "codex-jsonl";
}>;
export type SetupReady = Readonly<{
  kind: "setup-ready";
  requestId: string;
  protocolVersion: 1;
  helperVersion: string;
  activationId: string;
  hostInstanceId: string;
  capability: "codex-device-auth-pty";
}>;

export type ProtocolErrorCode = "INVALID_REQUEST" | "METHOD_NOT_ALLOWED" | "DUPLICATE_ID";

export type ActivationProtocolError = ActivationFrameContext & Readonly<{
  kind: "protocol-error";
  requestId: string | null;
  code: ProtocolErrorCode;
  message: string;
}>;

export type BoundProtocolError = BoundFrameContext & Readonly<{
  kind: "protocol-error";
  requestId: string | null;
  code: ProtocolErrorCode;
  message: string;
}>;

export type RemoteHelperProtocolErrorCode =
  | "FRAME_TOO_LARGE"
  | "MALFORMED_FRAME"
  | "TRUNCATED_FRAME"
  | "INVALID_FRAME"
  | "CONTEXT_MISMATCH"
  | "DUPLICATE_ID"
  | "METHOD_NOT_ALLOWED";

export class RemoteHelperProtocolError extends Error {
  constructor(
    readonly code: RemoteHelperProtocolErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "RemoteHelperProtocolError";
  }
}

const textEncoder = new TextEncoder();
const ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/u;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const SEMVER_PATTERN = /^(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)$/u;
const ACTIVATION_METHODS = new Set<ActivationMethod>([
  "browse.home",
  "browse.listDirectories",
  "browse.canonicalize",
  "codex.probe",
]);
const ACTIVATION_ERROR_CODES = new Set<ActivationErrorCode>([
  "INVALID_REQUEST",
  "METHOD_NOT_ALLOWED",
  "PATH_REJECTED",
  "NOT_FOUND",
  "NOT_DIRECTORY",
  "IDENTITY_MISMATCH",
  "PROBE_FAILED",
  "INTERNAL",
]);
const PROTOCOL_ERROR_CODES = new Set<ProtocolErrorCode>([
  "INVALID_REQUEST",
  "METHOD_NOT_ALLOWED",
  "DUPLICATE_ID",
]);
const ACTIVATION_MODE_CAPABILITIES = {
  browse: ["browse", "codex-probe"],
  "repository-handshake": [],
  "setup-auth": ["codex-device-auth-pty"],
} as const satisfies Record<ActivationClientHello["mode"], readonly string[]>;
const BOUND_MODE_CAPABILITIES = {
  agent: ["codex-app-server"],
  repository: [],
} as const satisfies Record<BoundClientHello["mode"], readonly string[]>;
type UnknownObject = { [key: string]: unknown };

function protocolError(code: RemoteHelperProtocolErrorCode, message: string): never {
  throw new RemoteHelperProtocolError(code, message);
}

function joinBytes(left: Uint8Array, right: Uint8Array): Uint8Array {
  if (!left.length) return right.slice();
  if (!right.length) return left;
  const joined = new Uint8Array(left.length + right.length);
  joined.set(left);
  joined.set(right, left.length);
  return joined;
}

class StrictJsonPreflight {
  private index = 0;

  constructor(private readonly source: string) {}

  parse(): void {
    this.skipWhitespace();
    this.parseValue();
    this.skipWhitespace();
    if (this.index !== this.source.length) this.fail();
  }

  private fail(): never {
    throw new SyntaxError("Malformed JSON or duplicate object key");
  }

  private skipWhitespace(): void {
    while (this.index < this.source.length
      && (this.source[this.index] === " " || this.source[this.index] === "\t"
        || this.source[this.index] === "\r" || this.source[this.index] === "\n")) {
      this.index++;
    }
  }

  private parseValue(): void {
    const token = this.source[this.index];
    if (token === "{") return this.parseObject();
    if (token === "[") return this.parseArray();
    if (token === '"') {
      this.parseString(false);
      return;
    }
    if (token === "t") return this.parseLiteral("true");
    if (token === "f") return this.parseLiteral("false");
    if (token === "n") return this.parseLiteral("null");
    this.parseNumber();
  }

  private parseObject(): void {
    this.index++;
    this.skipWhitespace();
    if (this.source[this.index] === "}") {
      this.index++;
      return;
    }
    const keys = new Set<string>();
    for (;;) {
      if (this.source[this.index] !== '"') this.fail();
      const key = this.parseString(true);
      if (keys.has(key)) this.fail();
      keys.add(key);
      this.skipWhitespace();
      if (this.source[this.index++] !== ":") this.fail();
      this.skipWhitespace();
      this.parseValue();
      this.skipWhitespace();
      const separator = this.source[this.index++];
      if (separator === "}") return;
      if (separator !== ",") this.fail();
      this.skipWhitespace();
    }
  }

  private parseArray(): void {
    this.index++;
    this.skipWhitespace();
    if (this.source[this.index] === "]") {
      this.index++;
      return;
    }
    for (;;) {
      this.parseValue();
      this.skipWhitespace();
      const separator = this.source[this.index++];
      if (separator === "]") return;
      if (separator !== ",") this.fail();
      this.skipWhitespace();
    }
  }

  private parseString(capture: boolean): string {
    this.index++;
    const pieces: string[] = [];
    let plainStart = this.index;
    for (;;) {
      if (this.index >= this.source.length) this.fail();
      const character = this.source[this.index];
      const code = this.source.charCodeAt(this.index);
      if (character === '"') {
        if (capture) pieces.push(this.source.slice(plainStart, this.index));
        this.index++;
        return capture ? pieces.join("") : "";
      }
      if (code < 0x20) this.fail();
      if (character !== "\\") {
        this.index++;
        continue;
      }
      if (capture) pieces.push(this.source.slice(plainStart, this.index));
      this.index++;
      const escaped = this.source[this.index++];
      const simple: { [key: string]: string } = {
        '"': '"', "\\": "\\", "/": "/", b: "\b", f: "\f",
        n: "\n", r: "\r", t: "\t",
      };
      if (escaped === "u") {
        const hexadecimal = this.source.slice(this.index, this.index + 4);
        if (!/^[0-9A-Fa-f]{4}$/u.test(hexadecimal)) this.fail();
        if (capture) pieces.push(String.fromCharCode(Number.parseInt(hexadecimal, 16)));
        this.index += 4;
      }
      else if (Object.hasOwn(simple, escaped)) {
        if (capture) pieces.push(simple[escaped]);
      }
      else this.fail();
      plainStart = this.index;
    }
  }

  private parseLiteral(literal: string): void {
    if (!this.source.startsWith(literal, this.index)) this.fail();
    this.index += literal.length;
  }

  private parseNumber(): void {
    if (this.source[this.index] === "-") this.index++;
    if (this.source[this.index] === "0") {
      this.index++;
      if (/[0-9]/u.test(this.source[this.index] ?? "")) this.fail();
    }
    else {
      if (!/[1-9]/u.test(this.source[this.index] ?? "")) this.fail();
      while (/[0-9]/u.test(this.source[this.index] ?? "")) this.index++;
    }
    if (this.source[this.index] === ".") {
      this.index++;
      if (!/[0-9]/u.test(this.source[this.index] ?? "")) this.fail();
      while (/[0-9]/u.test(this.source[this.index] ?? "")) this.index++;
    }
    if (this.source[this.index] === "e" || this.source[this.index] === "E") {
      this.index++;
      if (this.source[this.index] === "+" || this.source[this.index] === "-") this.index++;
      if (!/[0-9]/u.test(this.source[this.index] ?? "")) this.fail();
      while (/[0-9]/u.test(this.source[this.index] ?? "")) this.index++;
    }
  }
}

function parseJson(bytes: Uint8Array): unknown {
  let source: string;
  try {
    source = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  }
  catch {
    return protocolError("MALFORMED_FRAME", "Remote helper frame is not valid UTF-8");
  }
  try {
    new StrictJsonPreflight(source).parse();
    return JSON.parse(source) as unknown;
  }
  catch {
    return protocolError("MALFORMED_FRAME", "Remote helper frame is not valid JSON");
  }
}

export type BoundedJsonlDecodeResult = Readonly<{
  frames: readonly unknown[];
  transitioned: boolean;
  rawRemainder: Uint8Array | null;
}>;

/** One byte-oriented decoder for every helper JSONL phase. */
export class BoundedJsonlDecoder {
  private pending: Uint8Array<ArrayBufferLike> = new Uint8Array();
  private decodedFrames = 0;
  private state: "open" | "terminal" | "transitioned" | "finished" | "failed" = "open";

  constructor(
    private readonly transitionAfter: ((frame: unknown) => boolean) | null = null,
  ) {}

  push(chunk: Uint8Array): BoundedJsonlDecodeResult {
    if (this.state !== "open") {
      return protocolError("INVALID_FRAME", "Remote helper JSONL stream is already terminal");
    }
    if (!(chunk instanceof Uint8Array)) {
      return protocolError("INVALID_FRAME", "Remote helper input must be bytes");
    }
    try {
      this.pending = joinBytes(this.pending, chunk);
      const frames: unknown[] = [];
      for (;;) {
        const newline = this.pending.indexOf(0x0a);
        if (newline < 0) break;
        const physicalBytes = newline + 1;
        if (physicalBytes > REMOTE_HELPER_MAX_FRAME_BYTES) {
          return protocolError("FRAME_TOO_LARGE", "Remote helper JSONL frame exceeds 8 MiB");
        }
        const frame = parseJson(this.pending.slice(0, newline));
        frames.push(frame);
        this.decodedFrames++;
        this.pending = this.pending.slice(physicalBytes);
        if (isRecord(frame) && frame.kind === "protocol-error") {
          if (this.pending.length) {
            return protocolError("INVALID_FRAME", "Remote helper sent bytes after a terminal error");
          }
          this.state = "terminal";
          break;
        }
        if (this.transitionAfter?.(frame)) {
          const rawRemainder = chunk.subarray(chunk.length - this.pending.length);
          this.pending = new Uint8Array();
          this.state = "transitioned";
          return Object.freeze({
            frames: Object.freeze(frames),
            transitioned: true,
            rawRemainder,
          });
        }
      }
      if (this.pending.length >= REMOTE_HELPER_MAX_FRAME_BYTES) {
        return protocolError("FRAME_TOO_LARGE", "Remote helper JSONL frame exceeds 8 MiB");
      }
      return Object.freeze({
        frames: Object.freeze(frames),
        transitioned: false,
        rawRemainder: null,
      });
    }
    catch (error) {
      this.state = "failed";
      throw error;
    }
  }

  finish(): readonly unknown[] {
    if (this.state === "finished" || this.state === "failed" || this.state === "transitioned") {
      return protocolError("INVALID_FRAME", "Remote helper JSONL stream is already closed");
    }
    if (this.state === "terminal") {
      this.state = "finished";
      return [];
    }
    this.state = "finished";
    if (this.pending.length || this.decodedFrames === 0) {
      return protocolError(
        "TRUNCATED_FRAME",
        this.pending.length
          ? "Remote helper stream ended inside a JSONL frame"
          : "Remote helper stream ended before its first hello",
      );
    }
    return [];
  }
}

export function encodeJsonlFrame(value: unknown): Uint8Array {
  let encoded: Uint8Array;
  try {
    const source = JSON.stringify(value);
    if (source === undefined) return protocolError("INVALID_FRAME", "Remote helper frame is not JSON-serializable");
    encoded = textEncoder.encode(`${source}\n`);
  }
  catch {
    return protocolError("INVALID_FRAME", "Remote helper frame is not JSON-serializable");
  }
  if (encoded.length > REMOTE_HELPER_MAX_FRAME_BYTES) {
    return protocolError("FRAME_TOO_LARGE", "Remote helper JSONL frame exceeds 8 MiB");
  }
  return encoded;
}

export class RemoteRequestIdRegistry {
  private readonly claimed = new Set<string>();

  claim(value: unknown): string {
    const id = requireId(value, "request ID");
    if (this.claimed.has(id)) {
      return protocolError("DUPLICATE_ID", `Remote helper request ID ${id} was reused`);
    }
    this.claimed.add(id);
    return id;
  }
}

function isRecord(value: unknown): value is UnknownObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function record(value: unknown, label: string): UnknownObject {
  if (!isRecord(value)) return protocolError("INVALID_FRAME", `${label} must be an object`);
  return value;
}

function exactKeys(value: UnknownObject, keys: readonly string[], label: string): void {
  const actual = Object.keys(value);
  if (actual.length !== keys.length || keys.some((key) => !Object.hasOwn(value, key))) {
    protocolError("INVALID_FRAME", `${label} has missing or unknown fields`);
  }
}

function requireString(value: unknown, label: string, maxBytes = 4096): string {
  if (typeof value !== "string" || !value.length || value.includes("\0")
    || textEncoder.encode(value).length > maxBytes) {
    return protocolError("INVALID_FRAME", `${label} must be a bounded non-empty string`);
  }
  return value;
}

function requireId(value: unknown, label: string): string {
  if (typeof value !== "string" || !ID_PATTERN.test(value)) {
    return protocolError("INVALID_FRAME", `${label} must be a 1-128 byte ASCII identifier`);
  }
  return value;
}

function requireUuid(value: unknown, label: string): string {
  if (typeof value !== "string" || !UUID_PATTERN.test(value)) {
    return protocolError("INVALID_FRAME", `${label} must be a canonical RFC-4122 UUID`);
  }
  return value;
}

function requireHelperVersion(value: unknown, label: string): typeof REMOTE_HELPER_VERSION {
  if (value !== REMOTE_HELPER_VERSION) {
    return protocolError("INVALID_FRAME", `${label} is unsupported`);
  }
  return value;
}

function requireCoreVersion(value: unknown, label: string): string {
  if (typeof value !== "string" || !SEMVER_PATTERN.test(value)) {
    return protocolError("INVALID_FRAME", `${label} must be a numeric semantic version core`);
  }
  return value;
}

function compareCoreVersions(left: string, right: string): number {
  const leftParts = left.split(".");
  const rightParts = right.split(".");
  for (let index = 0; index < 3; index++) {
    if (leftParts[index].length !== rightParts[index].length) {
      return leftParts[index].length < rightParts[index].length ? -1 : 1;
    }
    if (leftParts[index] !== rightParts[index]) {
      return leftParts[index] < rightParts[index] ? -1 : 1;
    }
  }
  return 0;
}

function requireEpoch(value: unknown): number {
  if (typeof value !== "number" || !Number.isSafeInteger(value) || value < 0) {
    return protocolError("INVALID_FRAME", "targetEpoch must be a non-negative safe integer");
  }
  return value;
}

function requireCapabilities(value: unknown, label: string): readonly string[] {
  if (!Array.isArray(value) || value.length > 128) {
    return protocolError("INVALID_FRAME", `${label} must be a bounded capability array`);
  }
  const capabilities = value.map((entry) => requireId(entry, "capability"));
  if (new Set(capabilities).size !== capabilities.length) {
    return protocolError("INVALID_FRAME", `${label} must not contain duplicates`);
  }
  return Object.freeze(capabilities);
}

function requireExactCapabilities(
  value: unknown,
  expected: readonly string[],
  label: string,
): readonly string[] {
  const capabilities = requireCapabilities(value, label);
  if (!sameStrings(capabilities, expected)) {
    return protocolError("INVALID_FRAME", `${label} do not match the fixed mode capabilities`);
  }
  return capabilities;
}

function requireActivationCapabilities(
  value: unknown,
  mode: ActivationClientHello["mode"],
  label: string,
): readonly string[] {
  return requireExactCapabilities(value, ACTIVATION_MODE_CAPABILITIES[mode], label);
}

function requireBoundCapabilities(
  value: unknown,
  mode: BoundClientHello["mode"],
  label: string,
): readonly string[] {
  return requireExactCapabilities(value, BOUND_MODE_CAPABILITIES[mode], label);
}

function sameStrings(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function requireAbsolutePath(value: unknown, label: string): string {
  const path = requireString(value, label);
  if (!path.startsWith("/") || path.includes("\r") || path.includes("\n")
    || path.split("/").some((part) => part === "." || part === "..")) {
    return protocolError("INVALID_FRAME", `${label} must be an absolute traversal-free path`);
  }
  return path;
}

function requireNullableUuid(value: unknown, label: string): string | null {
  return value === null ? null : requireUuid(value, label);
}

function requireNullablePath(value: unknown, label: string): string | null {
  return value === null ? null : requireAbsolutePath(value, label);
}

function requireActivationMode(value: unknown): ActivationClientHello["mode"] {
  if (value !== "browse" && value !== "repository-handshake" && value !== "setup-auth") {
    return protocolError("INVALID_FRAME", "Activation hello contains an unknown mode");
  }
  return value;
}

function requireBoundMode(value: unknown): BoundClientHello["mode"] {
  if (value !== "agent" && value !== "repository") {
    return protocolError("INVALID_FRAME", "Bound hello contains an unknown mode");
  }
  return value;
}

function requireProtocolVersion(value: unknown): 1 {
  if (value !== REMOTE_HELPER_PROTOCOL_VERSION) {
    return protocolError("INVALID_FRAME", "Remote helper protocol version is unsupported");
  }
  return value;
}

export function decodeActivationClientHello(value: unknown): ActivationClientHello {
  const frame = record(value, "Activation client hello");
  exactKeys(frame, [
    "kind", "phase", "requestId", "protocolVersion", "helperVersion", "activationId",
    "mode", "candidateRoot", "expectedHostInstanceId", "requestedCapabilities",
  ], "Activation client hello");
  if (frame.kind !== "hello" || frame.phase !== "activation") {
    return protocolError("INVALID_FRAME", "Expected an activation client hello");
  }
  const mode = requireActivationMode(frame.mode);
  const candidateRoot = requireNullablePath(frame.candidateRoot, "candidateRoot");
  if ((mode === "repository-handshake") !== (candidateRoot !== null)) {
    return protocolError("INVALID_FRAME", "candidateRoot is permitted only for repository-handshake");
  }
  return Object.freeze({
    kind: "hello" as const,
    phase: "activation" as const,
    requestId: requireId(frame.requestId, "requestId"),
    protocolVersion: requireProtocolVersion(frame.protocolVersion),
    helperVersion: requireHelperVersion(frame.helperVersion, "helperVersion"),
    activationId: requireId(frame.activationId, "activationId"),
    mode,
    candidateRoot,
    expectedHostInstanceId: requireNullableUuid(frame.expectedHostInstanceId, "expectedHostInstanceId"),
    requestedCapabilities: requireActivationCapabilities(
      frame.requestedCapabilities,
      mode,
      "requestedCapabilities",
    ),
  });
}

export function decodeActivationServerHello(
  value: unknown,
  expected: ActivationClientHello,
): ActivationServerHello {
  if (!expected) {
    return protocolError("CONTEXT_MISMATCH", "Activation server hello requires its client hello");
  }
  const frame = record(value, "Activation server hello");
  exactKeys(frame, [
    "kind", "phase", "requestId", "protocolVersion", "helperVersion", "activationId",
    "mode", "hostInstanceId", "canonicalRoot", "repositoryUuid", "capabilities",
  ], "Activation server hello");
  if (frame.kind !== "hello" || frame.phase !== "activation") {
    return protocolError("INVALID_FRAME", "Expected an activation server hello");
  }
  const mode = requireActivationMode(frame.mode);
  const canonicalRoot = requireNullablePath(frame.canonicalRoot, "canonicalRoot");
  const repositoryUuid = requireNullableUuid(frame.repositoryUuid, "repositoryUuid");
  if (mode === "repository-handshake") {
    if (canonicalRoot === null || repositoryUuid === null) {
      return protocolError("INVALID_FRAME", "Repository activation requires canonical root and UUID");
    }
  }
  else if (canonicalRoot !== null || repositoryUuid !== null) {
    return protocolError("INVALID_FRAME", "Non-repository activation cannot claim repository identity");
  }
  const decoded: ActivationServerHello = Object.freeze({
    kind: "hello" as const,
    phase: "activation" as const,
    requestId: requireId(frame.requestId, "requestId"),
    protocolVersion: requireProtocolVersion(frame.protocolVersion),
    helperVersion: requireHelperVersion(frame.helperVersion, "helperVersion"),
    activationId: requireId(frame.activationId, "activationId"),
    mode,
    hostInstanceId: requireUuid(frame.hostInstanceId, "hostInstanceId"),
    canonicalRoot,
    repositoryUuid,
    capabilities: requireActivationCapabilities(frame.capabilities, mode, "capabilities"),
  });
  if (
    decoded.requestId !== expected.requestId
    || decoded.protocolVersion !== expected.protocolVersion
    || decoded.helperVersion !== expected.helperVersion
    || decoded.activationId !== expected.activationId
    || decoded.mode !== expected.mode
    || (expected.expectedHostInstanceId !== null
      && decoded.hostInstanceId !== expected.expectedHostInstanceId)
    || !sameStrings(decoded.capabilities, expected.requestedCapabilities)
  ) return protocolError("CONTEXT_MISMATCH", "Activation server hello does not match its client hello");
  return decoded;
}

export function decodeBoundClientHello(value: unknown): BoundClientHello {
  const frame = record(value, "Bound client hello");
  exactKeys(frame, [
    "kind", "phase", "requestId", "protocolVersion", "helperVersion", "mode", "targetId",
    "targetEpoch", "canonicalRoot", "expectedHostInstanceId", "expectedRepositoryUuid",
    "expectedRepositoryId", "requestedCapabilities",
  ], "Bound client hello");
  if (frame.kind !== "hello" || frame.phase !== "bound") {
    return protocolError("INVALID_FRAME", "Expected a bound client hello");
  }
  return Object.freeze({
    kind: "hello" as const,
    phase: "bound" as const,
    requestId: requireId(frame.requestId, "requestId"),
    protocolVersion: requireProtocolVersion(frame.protocolVersion),
    helperVersion: requireHelperVersion(frame.helperVersion, "helperVersion"),
    mode: requireBoundMode(frame.mode),
    targetId: requireId(frame.targetId, "targetId"),
    targetEpoch: requireEpoch(frame.targetEpoch),
    canonicalRoot: requireAbsolutePath(frame.canonicalRoot, "canonicalRoot"),
    expectedHostInstanceId: requireUuid(frame.expectedHostInstanceId, "expectedHostInstanceId"),
    expectedRepositoryUuid: requireUuid(frame.expectedRepositoryUuid, "expectedRepositoryUuid"),
    expectedRepositoryId: requireId(frame.expectedRepositoryId, "expectedRepositoryId"),
    requestedCapabilities: requireBoundCapabilities(
      frame.requestedCapabilities,
      requireBoundMode(frame.mode),
      "requestedCapabilities",
    ),
  });
}

export function decodeBoundServerHello(
  value: unknown,
  expected: BoundClientHello,
): BoundServerHello {
  if (!expected) {
    return protocolError("CONTEXT_MISMATCH", "Bound server hello requires its client hello");
  }
  const frame = record(value, "Bound server hello");
  exactKeys(frame, [
    "kind", "phase", "requestId", "protocolVersion", "helperVersion", "mode", "targetId",
    "targetEpoch", "canonicalRoot", "hostInstanceId", "repositoryUuid", "repositoryId",
    "helperInstanceId", "capabilities",
  ], "Bound server hello");
  if (frame.kind !== "hello" || frame.phase !== "bound") {
    return protocolError("INVALID_FRAME", "Expected a bound server hello");
  }
  const decoded: BoundServerHello = Object.freeze({
    kind: "hello" as const,
    phase: "bound" as const,
    requestId: requireId(frame.requestId, "requestId"),
    protocolVersion: requireProtocolVersion(frame.protocolVersion),
    helperVersion: requireHelperVersion(frame.helperVersion, "helperVersion"),
    mode: requireBoundMode(frame.mode),
    targetId: requireId(frame.targetId, "targetId"),
    targetEpoch: requireEpoch(frame.targetEpoch),
    canonicalRoot: requireAbsolutePath(frame.canonicalRoot, "canonicalRoot"),
    hostInstanceId: requireUuid(frame.hostInstanceId, "hostInstanceId"),
    repositoryUuid: requireUuid(frame.repositoryUuid, "repositoryUuid"),
    repositoryId: requireId(frame.repositoryId, "repositoryId"),
    helperInstanceId: requireId(frame.helperInstanceId, "helperInstanceId"),
    capabilities: requireBoundCapabilities(frame.capabilities, requireBoundMode(frame.mode), "capabilities"),
  });
  if (
    decoded.requestId !== expected.requestId
    || decoded.protocolVersion !== expected.protocolVersion
    || decoded.helperVersion !== expected.helperVersion
    || decoded.mode !== expected.mode
    || decoded.targetId !== expected.targetId
    || decoded.targetEpoch !== expected.targetEpoch
    || decoded.canonicalRoot !== expected.canonicalRoot
    || decoded.hostInstanceId !== expected.expectedHostInstanceId
    || decoded.repositoryUuid !== expected.expectedRepositoryUuid
    || decoded.repositoryId !== expected.expectedRepositoryId
    || !sameStrings(decoded.capabilities, expected.requestedCapabilities)
  ) return protocolError("CONTEXT_MISMATCH", "Bound server hello does not match its client hello");
  return decoded;
}

function decodeActivationContext(
  frame: UnknownObject,
  expected: ActivationFrameContext,
): ActivationFrameContext {
  if (!expected) {
    return protocolError("CONTEXT_MISMATCH", "Activation frame requires its negotiated context");
  }
  const context: ActivationFrameContext = {
    protocolVersion: requireProtocolVersion(frame.protocolVersion),
    helperVersion: requireHelperVersion(frame.helperVersion, "helperVersion"),
    activationId: requireId(frame.activationId, "activationId"),
    hostInstanceId: requireUuid(frame.hostInstanceId, "hostInstanceId"),
    capabilities: requireCapabilities(frame.capabilities, "capabilities"),
  };
  if (
    context.protocolVersion !== expected.protocolVersion
    || context.helperVersion !== expected.helperVersion
    || context.activationId !== expected.activationId
    || context.hostInstanceId !== expected.hostInstanceId
    || !sameStrings(context.capabilities, expected.capabilities)
  ) return protocolError("CONTEXT_MISMATCH", "Activation frame context changed within the channel");
  return context;
}

function decodeBoundContext(
  frame: UnknownObject,
  expected: BoundFrameContext,
): BoundFrameContext {
  if (!expected) {
    return protocolError("CONTEXT_MISMATCH", "Bound frame requires its negotiated context");
  }
  const context: BoundFrameContext = {
    protocolVersion: requireProtocolVersion(frame.protocolVersion),
    helperVersion: requireHelperVersion(frame.helperVersion, "helperVersion"),
    targetId: requireId(frame.targetId, "targetId"),
    targetEpoch: requireEpoch(frame.targetEpoch),
    hostInstanceId: requireUuid(frame.hostInstanceId, "hostInstanceId"),
    repositoryId: requireId(frame.repositoryId, "repositoryId"),
    capabilities: requireCapabilities(frame.capabilities, "capabilities"),
  };
  if (
    context.protocolVersion !== expected.protocolVersion
    || context.helperVersion !== expected.helperVersion
    || context.targetId !== expected.targetId
    || context.targetEpoch !== expected.targetEpoch
    || context.hostInstanceId !== expected.hostInstanceId
    || context.repositoryId !== expected.repositoryId
    || !sameStrings(context.capabilities, expected.capabilities)
  ) return protocolError("CONTEXT_MISMATCH", "Bound frame context changed within the channel");
  return context;
}

function requireActivationMethod(value: unknown): ActivationMethod {
  if (typeof value !== "string" || !ACTIVATION_METHODS.has(value as ActivationMethod)) {
    return protocolError("METHOD_NOT_ALLOWED", "Activation method is not allowed");
  }
  return value as ActivationMethod;
}

function decodeEmptyParams(value: unknown, label: string): Record<string, never> {
  const params = record(value, label);
  exactKeys(params, [], label);
  return Object.freeze({});
}

function decodeActivationParams(method: ActivationMethod, value: unknown): ActivationRequest["params"] {
  if (method === "browse.home" || method === "codex.probe") {
    return decodeEmptyParams(value, `${method} params`);
  }
  const params = record(value, `${method} params`);
  const key = method === "browse.listDirectories" ? "path" : "input";
  exactKeys(params, [key], `${method} params`);
  const path = requireAbsolutePath(params[key], key);
  return method === "browse.listDirectories"
    ? { path: path as CanonicalRemoteDirectory }
    : { input: path };
}

export function decodeActivationRequest(
  value: unknown,
  expectedBinding: ActivationChannelBinding,
): ActivationRequest {
  if (!expectedBinding?.context) {
    return protocolError("CONTEXT_MISMATCH", "Activation request requires its channel binding");
  }
  const frame = record(value, "Activation request");
  exactKeys(frame, [
    "protocolVersion", "helperVersion", "activationId", "hostInstanceId", "capabilities",
    "kind", "id", "method", "params",
  ], "Activation request");
  if (frame.kind !== "request") return protocolError("INVALID_FRAME", "Expected an activation request");
  const mode = requireActivationMode(expectedBinding.mode);
  requireActivationCapabilities(expectedBinding.context.capabilities, mode, "channel capabilities");
  const context = decodeActivationContext(frame, expectedBinding.context);
  const method = requireActivationMethod(frame.method);
  if (mode !== "browse") {
    return protocolError("METHOD_NOT_ALLOWED", `${mode} does not accept activation RPCs`);
  }
  const params = decodeActivationParams(method, frame.params);
  return Object.freeze({
    ...context,
    kind: "request" as const,
    id: requireId(frame.id, "request id"),
    method,
    params,
  }) as ActivationRequest;
}

function decodeDirectoryPathResult(value: unknown, label: string): { path: CanonicalRemoteDirectory } {
  const result = record(value, label);
  exactKeys(result, ["path"], label);
  return { path: requireAbsolutePath(result.path, "path") as CanonicalRemoteDirectory };
}

function decodeDirectoryEntriesResult(value: unknown): { entries: readonly RemoteDirectoryEntry[] } {
  const result = record(value, "browse.listDirectories result");
  exactKeys(result, ["entries"], "browse.listDirectories result");
  if (!Array.isArray(result.entries)
    || result.entries.length > REMOTE_HELPER_MAX_DIRECTORY_ENTRIES) {
    return protocolError("INVALID_FRAME", "Directory entries must be a bounded array");
  }
  const names = new Set<string>();
  const paths = new Set<string>();
  const entries = result.entries.map((raw): RemoteDirectoryEntry => {
    const entry = record(raw, "Directory entry");
    exactKeys(entry, ["name", "path", "kind"], "Directory entry");
    const name = requireString(entry.name, "Directory entry name", 255);
    if (name === "." || name === ".." || name.includes("/") || entry.kind !== "directory") {
      return protocolError("INVALID_FRAME", "Directory entry is malformed");
    }
    const path = requireAbsolutePath(entry.path, "Directory entry path");
    if (names.has(name) || paths.has(path)) {
      return protocolError("INVALID_FRAME", "Directory entries must be unique");
    }
    names.add(name);
    paths.add(path);
    return Object.freeze({ name, path: path as CanonicalRemoteDirectory, kind: "directory" as const });
  });
  return { entries: Object.freeze(entries) };
}

function decodeCodexProbeResult(value: unknown): CodexProbeResult {
  const result = record(value, "codex.probe result");
  if (result.state === "missing") {
    exactKeys(result, ["state"], "missing Codex probe result");
    return Object.freeze({ state: "missing" as const });
  }
  if (result.state === "incompatible") {
    exactKeys(result, ["state", "foundVersion", "minimumVersion"], "incompatible Codex probe result");
    const foundVersion = requireCoreVersion(result.foundVersion, "foundVersion");
    const minimumVersion = requireCoreVersion(result.minimumVersion, "minimumVersion");
    if (minimumVersion !== MINIMUM_CODEX_VERSION
      || compareCoreVersions(foundVersion, MINIMUM_CODEX_VERSION) >= 0) {
      return protocolError("INVALID_FRAME", "Incompatible Codex result contradicts the version floor");
    }
    return Object.freeze({
      state: "incompatible" as const,
      foundVersion,
      minimumVersion,
    });
  }
  if (result.state === "unauthenticated" || result.state === "ready") {
    exactKeys(result, ["state", "version"], `${result.state} Codex probe result`);
    const version = requireCoreVersion(result.version, "version");
    if (compareCoreVersions(version, MINIMUM_CODEX_VERSION) < 0) {
      return protocolError("INVALID_FRAME", `${result.state} Codex result is below the version floor`);
    }
    return Object.freeze({
      state: result.state,
      version,
    });
  }
  return protocolError("INVALID_FRAME", "Codex probe result has an unknown state");
}

function decodeActivationResult(method: ActivationMethod, value: unknown): ActivationResponse["result"] {
  if (method === "browse.home" || method === "browse.canonicalize") {
    return decodeDirectoryPathResult(value, `${method} result`);
  }
  if (method === "browse.listDirectories") return decodeDirectoryEntriesResult(value);
  return decodeCodexProbeResult(value);
}

function decodeActivationError(value: unknown): { code: ActivationErrorCode; message: string } {
  const error = record(value, "Activation response error");
  exactKeys(error, ["code", "message"], "Activation response error");
  if (typeof error.code !== "string" || !ACTIVATION_ERROR_CODES.has(error.code as ActivationErrorCode)) {
    return protocolError("INVALID_FRAME", "Activation response contains an unknown error code");
  }
  return {
    code: error.code as ActivationErrorCode,
    message: requireString(error.message, "Activation error message", 4096),
  };
}

export function decodeActivationResponse(
  value: unknown,
  expectedRequest: ActivationRequest,
): ActivationResponse {
  if (!expectedRequest) {
    return protocolError("CONTEXT_MISMATCH", "Activation response requires its originating request");
  }
  const frame = record(value, "Activation response");
  const hasResult = Object.hasOwn(frame, "result");
  const hasError = Object.hasOwn(frame, "error");
  if (hasResult === hasError) {
    return protocolError("INVALID_FRAME", "Activation response must contain exactly one of result or error");
  }
  exactKeys(frame, [
    "protocolVersion", "helperVersion", "activationId", "hostInstanceId", "capabilities",
    "kind", "id", "method", hasResult ? "result" : "error",
  ], "Activation response");
  if (frame.kind !== "response") return protocolError("INVALID_FRAME", "Expected an activation response");
  const context = decodeActivationContext(frame, expectedRequest);
  const method = requireActivationMethod(frame.method);
  const id = requireId(frame.id, "response id");
  if (id !== expectedRequest.id || method !== expectedRequest.method) {
    return protocolError("CONTEXT_MISMATCH", "Activation response does not match its request");
  }
  const common = {
    ...context,
    kind: "response" as const,
    id,
    method,
  };
  return Object.freeze(hasResult
    ? { ...common, result: decodeActivationResult(method, frame.result) }
    : { ...common, error: decodeActivationError(frame.error) }) as ActivationResponse;
}

function decodeProtocolErrorFields(frame: UnknownObject): Readonly<{
  requestId: string | null;
  code: ProtocolErrorCode;
  message: string;
}> {
  const requestId = frame.requestId === null ? null : requireId(frame.requestId, "requestId");
  if (typeof frame.code !== "string" || !PROTOCOL_ERROR_CODES.has(frame.code as ProtocolErrorCode)) {
    return protocolError("INVALID_FRAME", "Terminal protocol error contains an unknown code");
  }
  return {
    requestId,
    code: frame.code as ProtocolErrorCode,
    message: requireString(frame.message, "Protocol error message", 4096),
  };
}

export function decodeActivationProtocolError(
  value: unknown,
  expectedContext: ActivationFrameContext,
): ActivationProtocolError {
  const frame = record(value, "Activation protocol error");
  exactKeys(frame, [
    "protocolVersion", "helperVersion", "activationId", "hostInstanceId", "capabilities",
    "kind", "requestId", "code", "message",
  ], "Activation protocol error");
  if (frame.kind !== "protocol-error") return protocolError("INVALID_FRAME", "Expected a protocol error");
  return Object.freeze({
    ...decodeActivationContext(frame, expectedContext),
    kind: "protocol-error" as const,
    ...decodeProtocolErrorFields(frame),
  });
}

export function decodeBoundProtocolError(
  value: unknown,
  expectedContext: BoundFrameContext,
): BoundProtocolError {
  const frame = record(value, "Bound protocol error");
  exactKeys(frame, [
    "protocolVersion", "helperVersion", "targetId", "targetEpoch", "hostInstanceId",
    "repositoryId", "capabilities", "kind", "requestId", "code", "message",
  ], "Bound protocol error");
  if (frame.kind !== "protocol-error") return protocolError("INVALID_FRAME", "Expected a protocol error");
  return Object.freeze({
    ...decodeBoundContext(frame, expectedContext),
    kind: "protocol-error" as const,
    ...decodeProtocolErrorFields(frame),
  });
}

export function decodeStreamReady(
  value: unknown,
  expectedHello: BoundServerHello,
): StreamReady {
  const frame = record(value, "Stream-ready frame");
  exactKeys(frame, [
    "protocolVersion", "helperVersion", "targetId", "targetEpoch", "hostInstanceId",
    "repositoryId", "capabilities", "kind", "requestId", "stream",
  ], "Stream-ready frame");
  if (frame.kind !== "stream-ready" || frame.stream !== "codex-jsonl") {
    return protocolError("INVALID_FRAME", "Expected a codex-jsonl stream-ready frame");
  }
  const requestId = requireId(frame.requestId, "requestId");
  if (requestId !== expectedHello?.requestId) {
    return protocolError("CONTEXT_MISMATCH", "Stream-ready does not match its bound hello");
  }
  return Object.freeze({
    ...decodeBoundContext(frame, expectedHello),
    kind: "stream-ready" as const,
    requestId,
    stream: "codex-jsonl" as const,
  });
}

export function decodeSetupReady(
  value: unknown,
  client: ActivationClientHello,
  server: ActivationServerHello,
): SetupReady {
  if (!client || !server) {
    return protocolError("CONTEXT_MISMATCH", "Setup-ready requires both activation hellos");
  }
  const frame = record(value, "Setup-ready frame");
  exactKeys(frame, [
    "kind", "requestId", "protocolVersion", "helperVersion", "activationId",
    "hostInstanceId", "capability",
  ], "Setup-ready frame");
  if (frame.kind !== "setup-ready" || frame.capability !== "codex-device-auth-pty") {
    return protocolError("INVALID_FRAME", "Expected a device-auth setup-ready frame");
  }
  const decoded: SetupReady = Object.freeze({
    kind: "setup-ready" as const,
    requestId: requireId(frame.requestId, "requestId"),
    protocolVersion: requireProtocolVersion(frame.protocolVersion),
    helperVersion: requireHelperVersion(frame.helperVersion, "helperVersion"),
    activationId: requireId(frame.activationId, "activationId"),
    hostInstanceId: requireUuid(frame.hostInstanceId, "hostInstanceId"),
    capability: "codex-device-auth-pty" as const,
  });
  if (
    client.mode !== "setup-auth"
    || decoded.requestId !== client.requestId
    || decoded.protocolVersion !== client.protocolVersion
    || decoded.helperVersion !== client.helperVersion
    || decoded.activationId !== client.activationId
    || !client.requestedCapabilities.includes(decoded.capability)
  ) return protocolError("CONTEXT_MISMATCH", "Setup-ready frame does not match its client hello");
  if (
    server.mode !== "setup-auth"
    || decoded.requestId !== server.requestId
    || decoded.protocolVersion !== server.protocolVersion
    || decoded.helperVersion !== server.helperVersion
    || decoded.activationId !== server.activationId
    || decoded.hostInstanceId !== server.hostInstanceId
    || !server.capabilities.includes(decoded.capability)
  ) return protocolError("CONTEXT_MISMATCH", "Setup-ready frame does not match its server hello");
  return decoded;
}
