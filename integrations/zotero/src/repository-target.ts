import type { QLabRepositoryState } from "./qlab-workspace";

export type LocalRepositoryTarget = Readonly<{ kind: "local"; root: string }>;
export type ResolvedLocalRepositoryTarget = Readonly<LocalRepositoryTarget & {
  canonicalRoot: string;
  repositoryId: string;
  targetId: string;
}>;
export type SshRepositoryTarget = Readonly<{
  kind: "ssh";
  sshProfile: string;
  root: string;
}>;
export type AcceptedHostKeyFingerprint = string;
export type ResolvedSshRepositoryTarget = Readonly<SshRepositoryTarget & {
  canonicalRoot: string;
  acceptedHostKeyFingerprint: AcceptedHostKeyFingerprint;
  endpointId: string;
  hostInstanceId: string;
  repositoryUuid: string;
  repositoryId: string;
  targetId: string;
}>;
export type RepositoryTarget = LocalRepositoryTarget | SshRepositoryTarget;
export type ResolvedRepositoryTarget = ResolvedLocalRepositoryTarget | ResolvedSshRepositoryTarget;
export type RepositoryTargetCapabilities = Readonly<{
  chat: boolean;
  qmdRead: boolean;
  qmdWrite: boolean;
  terminal: boolean;
  preview: boolean;
  mainSiteSupported: boolean;
  externalEditor: boolean;
  promoteDraft: boolean;
}>;
export type RepositoryTargetSnapshot = Readonly<{
  target: ResolvedRepositoryTarget;
  targetEpoch: number;
  capabilities: RepositoryTargetCapabilities;
}>;
export type LegacyRootDisposition = "bind" | "candidate" | "unassigned";
export type StoredTargetPreferencesV1 = Readonly<{
  version: 1;
  active: ResolvedLocalRepositoryTarget | null;
  pendingCandidate: PendingLocalRepositoryCandidate | null;
  legacyUnassigned: readonly LegacyThreadBinding[];
  migratedLegacy: boolean;
}>;
export type StoredTargetPreferencesV2 = Readonly<{
  version: 2;
  active: ResolvedRepositoryTarget | null;
  pendingCandidate: PendingLocalRepositoryCandidate | null;
  legacyUnassigned: readonly LegacyThreadBinding[];
  migratedLegacy: boolean;
}>;
export type StoredTargetPreferences = StoredTargetPreferencesV2;
export type DecodedTargetPreferences = Readonly<{
  preferences: StoredTargetPreferencesV2;
  rewrite: "v1-to-v2" | null;
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
const ACCEPTED_HOST_KEY_FINGERPRINT_PATTERN = /^SHA256:[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]$/;
const REPOSITORY_UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/u;
const EMPTY_PREFERENCES: StoredTargetPreferences = {
  version: 2,
  active: null,
  pendingCandidate: null,
  legacyUnassigned: [],
  migratedLegacy: false,
};

export function capabilitiesFor(target: ResolvedRepositoryTarget): RepositoryTargetCapabilities {
  return Object.freeze(target.kind === "local"
    ? {
      chat: true,
      qmdRead: true,
      qmdWrite: true,
      terminal: true,
      preview: true,
      mainSiteSupported: true,
      externalEditor: true,
      promoteDraft: true,
    }
    : {
      chat: true,
      qmdRead: false,
      qmdWrite: false,
      terminal: false,
      preview: false,
      mainSiteSupported: false,
      externalEditor: false,
      promoteDraft: false,
    });
}

export function deriveRepositoryId(endpointId: string, repositoryUuid: string, digest: TargetDigest): string {
  return digestIdentity(new TextEncoder().encode(`${endpointId}\0${repositoryUuid}`), digest);
}

export function deriveSshEndpointId(
  acceptedHostKeyFingerprint: string,
  hostInstanceId: string,
  digest: TargetDigest,
): string {
  if (!validAcceptedHostKeyFingerprint(acceptedHostKeyFingerprint)
    || !validRepositoryUuid(hostInstanceId)) {
    throw new Error("SSH endpoint identity is malformed");
  }
  return digestIdentity(new TextEncoder().encode(
    `ssh\0${acceptedHostKeyFingerprint}\0${hostInstanceId}`,
  ), digest);
}

export function deriveTargetId(endpointId: string, canonicalRoot: string, repositoryId: string, digest: TargetDigest): string {
  return digestIdentity(new TextEncoder().encode(`${endpointId}\0${canonicalRoot}\0${repositoryId}`), digest);
}

function digestIdentity(bytes: Uint8Array, digest: TargetDigest): string {
  const value = digest(bytes);
  if (!IDENTITY_PATTERN.test(value)) throw new Error("Repository target digest must return a lowercase 64-hex identity");
  return value;
}

export function decodeStoredTargetPreferences(value: string): DecodedTargetPreferences {
  try {
    const parsed: unknown = JSON.parse(value);
    return parsePreferencesObject(parsed) ?? { preferences: EMPTY_PREFERENCES, rewrite: null };
  }
  catch {
    return { preferences: EMPTY_PREFERENCES, rewrite: null };
  }
}

/** @deprecated Use decodeStoredTargetPreferences() to learn whether persistence must be rewritten. */
export function parseStoredTargetPreferences(value: string): StoredTargetPreferences {
  return decodeStoredTargetPreferences(value).preferences;
}

function parsePreferencesObject(value: unknown): DecodedTargetPreferences | null {
  if (!isRecord(value) || typeof value.migratedLegacy !== "boolean") return null;
  if (value.version === 1) return parseV1PreferencesObject(value);
  if (value.version === 2) return parseV2PreferencesObject(value);
  return null;
}

function parseV1PreferencesObject(value: Record<string, unknown>): DecodedTargetPreferences | null {
  if (!hasOnlyKeys(value, ["version", "active", "pendingCandidate", "legacyUnassigned", "migratedLegacy"])
    || typeof value.migratedLegacy !== "boolean") return null;
  const active = value.active === null ? null : parseResolvedLocalTarget(value.active);
  const pendingCandidate = value.pendingCandidate === null ? null : parsePendingCandidate(value.pendingCandidate);
  const legacyUnassigned = parseLegacyBindings(value.legacyUnassigned);
  if (active === undefined || pendingCandidate === undefined || legacyUnassigned === undefined) return null;
  return { preferences: {
    version: 2,
    active,
    pendingCandidate,
    legacyUnassigned,
    migratedLegacy: value.migratedLegacy,
  }, rewrite: "v1-to-v2" };
}

function parseV2PreferencesObject(value: Record<string, unknown>): DecodedTargetPreferences | null {
  if (!hasOnlyKeys(value, ["version", "active", "pendingCandidate", "legacyUnassigned", "migratedLegacy"])
    || typeof value.migratedLegacy !== "boolean") return null;
  const active = value.active === null ? null : parseResolvedTarget(value.active);
  const pendingCandidate = value.pendingCandidate === null ? null : parsePendingCandidate(value.pendingCandidate);
  const legacyUnassigned = parseLegacyBindings(value.legacyUnassigned);
  if (active === undefined || pendingCandidate === undefined || legacyUnassigned === undefined) return null;
  return { preferences: {
    version: 2,
    active,
    pendingCandidate,
    legacyUnassigned,
    migratedLegacy: value.migratedLegacy,
  }, rewrite: null };
}

function parseResolvedTarget(value: unknown): ResolvedRepositoryTarget | undefined {
  if (!isRecord(value)) return undefined;
  return value.kind === "local" ? parseResolvedLocalTarget(value) : value.kind === "ssh" ? parseResolvedSshTarget(value) : undefined;
}

function parseResolvedLocalTarget(value: unknown): ResolvedLocalRepositoryTarget | undefined {
  if (!isRecord(value)
    || !hasOnlyKeys(value, ["kind", "root", "canonicalRoot", "repositoryId", "targetId"])
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

function parseResolvedSshTarget(value: Record<string, unknown>): ResolvedSshRepositoryTarget | undefined {
  if (!hasOnlyKeys(value, [
    "kind", "sshProfile", "root", "canonicalRoot", "acceptedHostKeyFingerprint",
    "endpointId", "hostInstanceId", "repositoryUuid", "repositoryId", "targetId",
  ])
    || !nonEmptyString(value.sshProfile)
    || !nonEmptyString(value.root)
    || !nonEmptyString(value.canonicalRoot)
    || !validAcceptedHostKeyFingerprint(value.acceptedHostKeyFingerprint)
    || !validIdentity(value.endpointId)
    || !validRepositoryUuid(value.hostInstanceId)
    || !validRepositoryUuid(value.repositoryUuid)
    || !validIdentity(value.repositoryId)
    || !validIdentity(value.targetId)) return undefined;
  return {
    kind: "ssh",
    sshProfile: value.sshProfile,
    root: value.root,
    canonicalRoot: value.canonicalRoot,
    acceptedHostKeyFingerprint: value.acceptedHostKeyFingerprint,
    endpointId: value.endpointId,
    hostInstanceId: value.hostInstanceId,
    repositoryUuid: value.repositoryUuid,
    repositoryId: value.repositoryId,
    targetId: value.targetId,
  };
}

function parsePendingCandidate(value: unknown): PendingLocalRepositoryCandidate | undefined {
  if (!isRecord(value)
    || !hasOnlyKeys(value, ["kind", "canonicalRoot", "state", "eligibleLegacyThreads"])
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
      || !hasOnlyKeys(binding, ["threadId", "recordedCwd", "reason"])
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
      || !hasOnlyKeys(binding, ["threadId", "recordedCwd", "activeWithoutCwd"])
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

function hasOnlyKeys(value: Record<string, unknown>, allowedKeys: readonly string[]): boolean {
  return Object.keys(value).every((key) => allowedKeys.includes(key));
}

function validIdentity(value: unknown): value is string {
  return typeof value === "string" && IDENTITY_PATTERN.test(value);
}

function validAcceptedHostKeyFingerprint(value: unknown): value is AcceptedHostKeyFingerprint {
  return typeof value === "string" && ACCEPTED_HOST_KEY_FINGERPRINT_PATTERN.test(value);
}

function validRepositoryUuid(value: unknown): value is string {
  return typeof value === "string" && REPOSITORY_UUID_PATTERN.test(value);
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
  return { version: 2, active, pendingCandidate, legacyUnassigned, migratedLegacy: true };
}

function isInsideRoot(path: string, canonicalRoot: string): boolean {
  const root = canonicalRoot.replace(/[\\/]+$/, "");
  return path === root || path.startsWith(`${root}/`) || path.startsWith(`${root}\\`);
}
