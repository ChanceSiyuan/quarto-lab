import { sha256Bytes } from "./hashing";
import {
  classifyLegacyRoot,
  deriveRepositoryId,
  deriveTargetId,
  type LocalRepositoryCandidate,
  type LocalRepositoryInspection,
  type LocalRepositoryTarget,
  type ResolvedLocalRepositoryTarget,
  type TargetDigest,
} from "./repository-target";
import type { QLabRepositoryState } from "./qlab-workspace";

const LOCAL_ENDPOINT_ID = "local";
const PRIVATE_FILE_MODE = 0o600;
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const INVALID_REPOSITORY_ERROR = "Choose a valid local Research Loop Git repository";

export const geckoTargetDigest: TargetDigest = (bytes) => sha256Bytes(bytes);

export interface LocalRepositoryTargetRuntime {
  canonicalize(root: string): Promise<string>;
  state(root: string): Promise<QLabRepositoryState>;
  initialize(root: string): Promise<void>;
  gitPrivatePath(root: string): Promise<string>;
  readPrivate(path: string): Promise<string | null>;
  createPrivateIfAbsent(path: string, value: string, mode: number): Promise<"created" | "exists">;
  resolvePath(root: string, path: string): string;
  isPathInside(root: string, candidate: string): boolean;
  digest: TargetDigest;
}

export class LocalRepositoryTargetResolver {
  private readonly pendingIdentities = new Map<string, Promise<ResolvedLocalRepositoryTarget>>();

  constructor(private readonly runtime: LocalRepositoryTargetRuntime) {}

  async inspect(root: string): Promise<LocalRepositoryInspection> {
    let canonicalRoot: string;
    let state: QLabRepositoryState;
    try {
      canonicalRoot = await this.runtime.canonicalize(root);
      state = await this.runtime.state(canonicalRoot);
    }
    catch {
      // A legacy preference may point at a directory that was moved or
      // deleted. Gecko's nsIFile.normalize() throws for that path, but a stale
      // preference must degrade to an unassigned target instead of aborting
      // the entire Zotero plugin bootstrap.
      return { kind: "unavailable", reason: "missing" };
    }
    const disposition = classifyLegacyRoot(state);
    if (disposition === "candidate") {
      return {
        kind: "candidate",
        canonicalRoot,
        state: state as LocalRepositoryCandidate["state"],
      };
    }
    if (disposition === "unassigned") {
      return {
        kind: "unavailable",
        reason: state === "missing" ? "missing" : "incompatible",
      };
    }
    try {
      return await this.resolveReady(canonicalRoot);
    }
    catch {
      return { kind: "unavailable", reason: "identity-unavailable" };
    }
  }

  async confirm(candidate: LocalRepositoryCandidate): Promise<ResolvedLocalRepositoryTarget> {
    const canonicalRoot = await this.runtime.canonicalize(candidate.canonicalRoot);
    if (canonicalRoot !== candidate.canonicalRoot) {
      throw new Error(INVALID_REPOSITORY_ERROR);
    }
    const state = await this.runtime.state(canonicalRoot);
    if (state === "ready") return this.resolveReady(canonicalRoot);
    if (state !== "empty" && state !== "partial") {
      throw new Error(INVALID_REPOSITORY_ERROR);
    }
    await this.runtime.initialize(canonicalRoot);
    return this.resolveReady(canonicalRoot);
  }

  private async resolveReady(root: string): Promise<ResolvedLocalRepositoryTarget> {
    const canonicalRoot = await this.runtime.canonicalize(root);
    if (await this.runtime.state(canonicalRoot) !== "ready") {
      throw new Error(INVALID_REPOSITORY_ERROR);
    }
    const pending = this.pendingIdentities.get(canonicalRoot);
    if (pending) return pending;
    const resolution = this.resolveIdentity(canonicalRoot);
    this.pendingIdentities.set(canonicalRoot, resolution);
    void resolution.finally(() => {
      if (this.pendingIdentities.get(canonicalRoot) === resolution) {
        this.pendingIdentities.delete(canonicalRoot);
      }
    }).catch(() => {});
    return resolution;
  }

  private async resolveIdentity(canonicalRoot: string): Promise<ResolvedLocalRepositoryTarget> {
    const rawPrivatePath = await this.runtime.gitPrivatePath(canonicalRoot);
    const privatePath = rawPrivatePath.trim();
    if (!privatePath || /[\r\n]/u.test(privatePath)) throw new Error(INVALID_REPOSITORY_ERROR);
    const resolvedPrivatePath = this.runtime.resolvePath(canonicalRoot, privatePath);
    if (!this.runtime.isPathInside(canonicalRoot, resolvedPrivatePath)) {
      throw new Error(INVALID_REPOSITORY_ERROR);
    }

    let repositoryUuid = parseStoredUuid(await this.runtime.readPrivate(resolvedPrivatePath));
    if (repositoryUuid === null) {
      const generated = normalizeGeneratedUuid(String(Services.uuid.generateUUID()));
      const creation = await this.runtime.createPrivateIfAbsent(
        resolvedPrivatePath,
        `${generated}\n`,
        PRIVATE_FILE_MODE,
      );
      repositoryUuid = creation === "created"
        ? generated
        : requireStoredUuid(await this.runtime.readPrivate(resolvedPrivatePath));
    }

    const repositoryId = deriveRepositoryId(LOCAL_ENDPOINT_ID, repositoryUuid, this.runtime.digest);
    const targetId = deriveTargetId(
      LOCAL_ENDPOINT_ID,
      canonicalRoot,
      repositoryId,
      this.runtime.digest,
    );
    const target: LocalRepositoryTarget = { kind: "local", root: canonicalRoot };
    return { ...target, canonicalRoot, repositoryId, targetId };
  }
}

function parseStoredUuid(value: string | null): string | null {
  if (value === null) return null;
  return requireUuid(value.trim().toLowerCase());
}

function requireStoredUuid(value: string | null): string {
  if (value === null) throw new Error(INVALID_REPOSITORY_ERROR);
  return requireUuid(value.trim().toLowerCase());
}

function normalizeGeneratedUuid(value: string): string {
  const trimmed = value.trim().toLowerCase();
  const unwrapped = trimmed.startsWith("{") && trimmed.endsWith("}")
    ? trimmed.slice(1, -1)
    : trimmed;
  return requireUuid(unwrapped);
}

function requireUuid(value: string): string {
  if (!UUID_PATTERN.test(value)) throw new Error(INVALID_REPOSITORY_ERROR);
  return value;
}
