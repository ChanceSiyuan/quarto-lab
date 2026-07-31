import { sha256Bytes } from "./hashing";
import type { QLabRepositoryState } from "./qlab-workspace";

export type LocalRepositoryTarget = Readonly<{ kind: "local"; root: string }>;
export type ResolvedLocalRepositoryTarget = Readonly<LocalRepositoryTarget & {
  canonicalRoot: string;
  repositoryId: string;
  targetId: string;
}>;
export type RepositoryTargetSnapshot = Readonly<{
  target: ResolvedLocalRepositoryTarget;
  targetEpoch: number;
}>;
export type LegacyRootDisposition = "bind" | "candidate" | "unassigned";
export type StoredTargetPreferences = Readonly<{
  version: 1;
  active: ResolvedLocalRepositoryTarget | null;
  pendingCandidate: PendingLocalRepositoryCandidate | null;
  legacyUnassigned: readonly LegacyThreadBinding[];
  migratedLegacy: boolean;
}>;

export type LocalRepositoryCandidate = Readonly<{
  kind: "candidate";
  canonicalRoot: string;
  state: "empty" | "partial";
}>;
export type PendingLocalRepositoryCandidate = Readonly<LocalRepositoryCandidate & {
  eligibleLegacyThreads: readonly PendingLegacyThreadBinding[];
}>;
export type LocalRepositoryUnavailable = Readonly<{
  kind: "unavailable";
  reason: "missing" | "incompatible" | "identity-unavailable";
}>;
export type LocalRepositoryInspection =
  | ResolvedLocalRepositoryTarget
  | LocalRepositoryCandidate
  | LocalRepositoryUnavailable;
export type LegacyUnassignedReason = LocalRepositoryUnavailable["reason"] | "different-root" | "pending-candidate";
export type LegacyThreadBinding = Readonly<{
  threadId: string;
  recordedCwd: string | null;
  reason: LegacyUnassignedReason;
}>;
export type PendingLegacyThreadBinding = Readonly<{
  threadId: string;
  recordedCwd: string | null;
  activeWithoutCwd: boolean;
}>;
export type TargetableSessionRecord = Readonly<{
  threadId: string;
  recordedCwd: string | null;
  targetId?: string;
}>;
export type TargetAssignedSession<TSession extends TargetableSessionRecord> = Readonly<
  Omit<TSession, "targetId"> & { targetId?: string }
>;
export type LegacyMigrationOutcome<TSession extends TargetableSessionRecord = TargetableSessionRecord> = Readonly<{
  preferences: StoredTargetPreferences;
  sessions: readonly TargetAssignedSession<TSession>[];
}>;
export interface LegacyMigrationInput<TSession extends TargetableSessionRecord = TargetableSessionRecord> {
  legacyRoot: string;
  sessions: readonly TSession[];
  activeThreadId: string | null;
}
export interface LegacyMigrationResolver {
  inspect(root: string): Promise<LocalRepositoryInspection>;
  canonicalize(path: string): Promise<string | null>;
}
export type TargetDigest = (bytes: Uint8Array) => string;

const IDENTITY_PATTERN = /^[a-f0-9]{64}$/;
const EMPTY_PREFERENCES: StoredTargetPreferences = {
  version: 1,
  active: null,
  pendingCandidate: null,
  legacyUnassigned: [],
  migratedLegacy: false,
};

/** The production digest stays at the Gecko boundary; tests inject their own. */
const geckoTargetDigest: TargetDigest = (bytes) => sha256Bytes(bytes);
void geckoTargetDigest;

export function deriveRepositoryId(endpointId: string, repositoryUuid: string, digest: TargetDigest): string {
  return digestIdentity(new TextEncoder().encode(`${endpointId}\0${repositoryUuid}`), digest);
}

export function deriveTargetId(endpointId: string, canonicalRoot: string, repositoryId: string, digest: TargetDigest): string {
  return digestIdentity(new TextEncoder().encode(`${endpointId}\0${canonicalRoot}\0${repositoryId}`), digest);
}

function digestIdentity(bytes: Uint8Array, digest: TargetDigest): string {
  const value = digest(bytes);
  if (!IDENTITY_PATTERN.test(value)) throw new Error("Repository target digest must return a lowercase 64-hex identity");
  return value;
}

export function parseStoredTargetPreferences(value: string): StoredTargetPreferences {
  try {
    const parsed: unknown = JSON.parse(value);
    return parsePreferencesObject(parsed) ?? EMPTY_PREFERENCES;
  }
  catch {
    return EMPTY_PREFERENCES;
  }
}

function parsePreferencesObject(value: unknown): StoredTargetPreferences | null {
  if (!isRecord(value) || value.version !== 1 || typeof value.migratedLegacy !== "boolean") return null;
  const active = value.active === null ? null : parseResolvedTarget(value.active);
  const pendingCandidate = value.pendingCandidate === null ? null : parsePendingCandidate(value.pendingCandidate);
  const legacyUnassigned = parseLegacyBindings(value.legacyUnassigned);
  if (active === undefined || pendingCandidate === undefined || legacyUnassigned === undefined) return null;
  return {
    version: 1,
    active,
    pendingCandidate,
    legacyUnassigned,
    migratedLegacy: value.migratedLegacy,
  };
}

function parseResolvedTarget(value: unknown): ResolvedLocalRepositoryTarget | undefined {
  if (!isRecord(value)
    || value.kind !== "local"
    || !nonEmptyString(value.root)
    || !nonEmptyString(value.canonicalRoot)
    || !validIdentity(value.repositoryId)
    || !validIdentity(value.targetId)) return undefined;
  return {
    kind: "local",
    root: value.root,
    canonicalRoot: value.canonicalRoot,
    repositoryId: value.repositoryId,
    targetId: value.targetId,
  };
}

function parsePendingCandidate(value: unknown): PendingLocalRepositoryCandidate | undefined {
  if (!isRecord(value)
    || value.kind !== "candidate"
    || !nonEmptyString(value.canonicalRoot)
    || (value.state !== "empty" && value.state !== "partial")) return undefined;
  const eligibleLegacyThreads = value.eligibleLegacyThreads === undefined
    ? []
    : parsePendingBindings(value.eligibleLegacyThreads);
  if (eligibleLegacyThreads === undefined) return undefined;
  return { kind: "candidate", canonicalRoot: value.canonicalRoot, state: value.state, eligibleLegacyThreads };
}

function parseLegacyBindings(value: unknown): readonly LegacyThreadBinding[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const bindings: LegacyThreadBinding[] = [];
  for (const binding of value) {
    if (!isRecord(binding)
      || !nonEmptyString(binding.threadId)
      || !(typeof binding.recordedCwd === "string" || binding.recordedCwd === null)
      || !isLegacyUnassignedReason(binding.reason)) return undefined;
    bindings.push({ threadId: binding.threadId, recordedCwd: binding.recordedCwd, reason: binding.reason });
  }
  return bindings;
}

function parsePendingBindings(value: unknown): readonly PendingLegacyThreadBinding[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const bindings: PendingLegacyThreadBinding[] = [];
  for (const binding of value) {
    if (!isRecord(binding)
      || !nonEmptyString(binding.threadId)
      || !(typeof binding.recordedCwd === "string" || binding.recordedCwd === null)
      || typeof binding.activeWithoutCwd !== "boolean") return undefined;
    bindings.push({
      threadId: binding.threadId,
      recordedCwd: binding.recordedCwd,
      activeWithoutCwd: binding.activeWithoutCwd,
    });
  }
  return bindings;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.length > 0;
}

function validIdentity(value: unknown): value is string {
  return typeof value === "string" && IDENTITY_PATTERN.test(value);
}

function isLegacyUnassignedReason(value: unknown): value is LegacyUnassignedReason {
  return value === "missing"
    || value === "incompatible"
    || value === "identity-unavailable"
    || value === "different-root"
    || value === "pending-candidate";
}

export function classifyLegacyRoot(state: QLabRepositoryState): LegacyRootDisposition {
  return state === "ready" ? "bind" : state === "empty" || state === "partial" ? "candidate" : "unassigned";
}

export async function migrateLegacy<TSession extends TargetableSessionRecord>(
  stored: StoredTargetPreferences,
  input: LegacyMigrationInput<TSession>,
  resolver: LegacyMigrationResolver,
): Promise<LegacyMigrationOutcome<TSession>> {
  if (stored.migratedLegacy) return { preferences: stored, sessions: input.sessions };

  const inspection = await resolver.inspect(input.legacyRoot);
  if (inspection.kind === "local") {
    const { sessions, legacyUnassigned } = await assignReadySessions(input.sessions, input.activeThreadId, inspection, resolver);
    return {
      preferences: migratedPreferences(inspection, null, legacyUnassigned),
      sessions,
    };
  }
  if (inspection.kind === "candidate") {
    const eligibleLegacyThreads = await findEligibleSessions(input.sessions, input.activeThreadId, inspection.canonicalRoot, resolver);
    return {
      preferences: migratedPreferences(null, { ...inspection, eligibleLegacyThreads }, []),
      sessions: input.sessions,
    };
  }
  return {
    preferences: migratedPreferences(null, null, unassignedSessions(input.sessions, inspection.reason)),
    sessions: input.sessions,
  };
}

export async function bindPendingLegacyThreads<TSession extends TargetableSessionRecord>(
  stored: StoredTargetPreferences,
  sessions: readonly TargetAssignedSession<TSession>[],
  target: ResolvedLocalRepositoryTarget,
  resolver: LegacyMigrationResolver,
): Promise<LegacyMigrationOutcome<TSession>> {
  const pending = stored.pendingCandidate;
  if (!pending) return { preferences: stored, sessions };

  const eligible = new Map(pending.eligibleLegacyThreads.map((binding) => [binding.threadId, binding]));
  const bound = new Set<string>();
  const assigned: TargetAssignedSession<TSession>[] = [];
  for (const session of sessions) {
    const binding = eligible.get(session.threadId);
    const mayBind = binding !== undefined
      && binding.recordedCwd === session.recordedCwd
      && await bindingStillMatches(binding, target.canonicalRoot, resolver);
    if (mayBind && !bound.has(session.threadId)) {
      bound.add(session.threadId);
      assigned.push(assignTarget<TSession>(session, target.targetId));
    }
    else {
      assigned.push(session);
    }
  }
  const legacyUnassigned = unassignedSessions(
    sessions.filter((session) => !bound.has(session.threadId)),
    "different-root",
  );
  return {
    preferences: migratedPreferences(target, null, legacyUnassigned),
    sessions: assigned,
  };
}

async function assignReadySessions<TSession extends TargetableSessionRecord>(
  sessions: readonly TSession[],
  activeThreadId: string | null,
  target: ResolvedLocalRepositoryTarget,
  resolver: LegacyMigrationResolver,
): Promise<Readonly<{ sessions: readonly TargetAssignedSession<TSession>[]; legacyUnassigned: readonly LegacyThreadBinding[] }>> {
  const assigned: TargetAssignedSession<TSession>[] = [];
  const unassigned: TSession[] = [];
  for (const session of sessions) {
    const activeWithoutCwd = session.threadId === activeThreadId && session.recordedCwd === null;
    const canonicalCwd = session.recordedCwd === null ? null : await resolver.canonicalize(session.recordedCwd);
    if (activeWithoutCwd || (canonicalCwd !== null && isInsideRoot(canonicalCwd, target.canonicalRoot))) {
      assigned.push(assignTarget<TSession>(session, target.targetId));
    }
    else {
      assigned.push(session);
      unassigned.push(session);
    }
  }
  return { sessions: assigned, legacyUnassigned: unassignedSessions(unassigned, "different-root") };
}

async function findEligibleSessions<TSession extends TargetableSessionRecord>(
  sessions: readonly TSession[],
  activeThreadId: string | null,
  canonicalRoot: string,
  resolver: LegacyMigrationResolver,
): Promise<readonly PendingLegacyThreadBinding[]> {
  const eligible: PendingLegacyThreadBinding[] = [];
  const seen = new Set<string>();
  for (const session of sessions) {
    const activeWithoutCwd = session.threadId === activeThreadId && session.recordedCwd === null;
    const canonicalCwd = session.recordedCwd === null ? null : await resolver.canonicalize(session.recordedCwd);
    if (!seen.has(session.threadId) && (activeWithoutCwd || (canonicalCwd !== null && isInsideRoot(canonicalCwd, canonicalRoot)))) {
      seen.add(session.threadId);
      eligible.push({ threadId: session.threadId, recordedCwd: session.recordedCwd, activeWithoutCwd });
    }
  }
  return eligible;
}

async function bindingStillMatches(
  binding: PendingLegacyThreadBinding,
  canonicalRoot: string,
  resolver: LegacyMigrationResolver,
): Promise<boolean> {
  if (binding.activeWithoutCwd && binding.recordedCwd === null) return true;
  if (binding.recordedCwd === null) return false;
  const canonicalCwd = await resolver.canonicalize(binding.recordedCwd);
  return canonicalCwd !== null && isInsideRoot(canonicalCwd, canonicalRoot);
}

function assignTarget<TSession extends TargetableSessionRecord>(
  session: TSession | TargetAssignedSession<TSession>,
  targetId: string,
): TargetAssignedSession<TSession> {
  return { ...session, targetId } as TargetAssignedSession<TSession>;
}

function unassignedSessions<TSession extends TargetableSessionRecord>(
  sessions: readonly TSession[],
  reason: LegacyUnassignedReason,
): readonly LegacyThreadBinding[] {
  const seen = new Set<string>();
  const bindings: LegacyThreadBinding[] = [];
  for (const session of sessions) {
    if (!seen.has(session.threadId)) {
      seen.add(session.threadId);
      bindings.push({ threadId: session.threadId, recordedCwd: session.recordedCwd, reason });
    }
  }
  return bindings;
}

function migratedPreferences(
  active: ResolvedLocalRepositoryTarget | null,
  pendingCandidate: PendingLocalRepositoryCandidate | null,
  legacyUnassigned: readonly LegacyThreadBinding[],
): StoredTargetPreferences {
  return { version: 1, active, pendingCandidate, legacyUnassigned, migratedLegacy: true };
}

function isInsideRoot(path: string, canonicalRoot: string): boolean {
  const root = canonicalRoot.replace(/[\\/]+$/, "");
  return path === root || path.startsWith(`${root}/`) || path.startsWith(`${root}\\`);
}
