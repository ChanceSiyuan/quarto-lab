import { geckoTargetDigest } from "./local-repository-target-resolver";
import { randomID } from "./platform";
import { RemoteAgentConnection } from "./remote-agent-connection";
import { BundledRemoteHelperAssets } from "./remote-helper-assets";
import {
  BoundedJsonlDecoder,
  decodeActivationProtocolError,
  decodeActivationResponse,
  decodeActivationServerHello,
  encodeJsonlFrame,
  REMOTE_HELPER_PROTOCOL_VERSION,
  REMOTE_HELPER_VERSION,
  type ActivationChannelBinding,
  type ActivationClientHello,
  type ActivationMethod,
  type ActivationRequest,
  type ActivationResponse,
  type ActivationRpcMap,
  type ActivationServerHello,
  type CanonicalRemoteDirectory,
  type CodexProbeResult,
  type RemoteDirectoryEntry,
} from "./remote-helper-protocol";
import {
  deriveRepositoryId,
  deriveSshEndpointId,
  deriveTargetId,
  type RepositoryTargetSnapshot,
  type ResolvedSshRepositoryTarget,
} from "./repository-target";
import {
  createNativeSshTargetTransport,
  type RemoteHelperTuple,
  type SshChannel,
  type SshMaster,
} from "./ssh-target-transport";
import type { NativeBridge } from "./native-bridge";
import type { WebSocketLike } from "./protocol";

type PendingRequest = Readonly<{
  request: ActivationRequest;
  resolve: (value: ActivationResponse) => void;
  reject: (error: unknown) => void;
  timer: ReturnType<typeof setTimeout>;
}>;

class ActivationClient {
  private readonly decoder = new BoundedJsonlDecoder();
  private readonly pending = new Map<string, PendingRequest>();
  private server: ActivationServerHello | null = null;
  private binding: ActivationChannelBinding | null = null;
  private readonly ready: Promise<ActivationServerHello>;
  private resolveReady!: (hello: ActivationServerHello) => void;
  private rejectReady!: (error: unknown) => void;
  private requestNumber = 0;
  private closed = false;

  constructor(
    private readonly channel: SshChannel,
    private readonly hello: ActivationClientHello,
  ) {
    this.ready = new Promise((resolve, reject) => {
      this.resolveReady = resolve;
      this.rejectReady = reject;
    });
    channel.onBytes((bytes) => this.receive(bytes));
    channel.onExit((exit) => this.fail(new Error(exit.reason)));
  }

  async connect(): Promise<ActivationServerHello> {
    await this.channel.write(encodeJsonlFrame(this.hello));
    return this.ready;
  }

  async invoke<M extends ActivationMethod>(
    method: M,
    params: ActivationRpcMap[M]["params"],
  ): Promise<ActivationRpcMap[M]["result"]> {
    const server = this.server || await this.connect();
    if (this.closed) throw new Error("Remote helper activation channel is closed");
    const id = `request-${++this.requestNumber}`;
    const request = Object.freeze({
      protocolVersion: server.protocolVersion,
      helperVersion: server.helperVersion,
      activationId: server.activationId,
      hostInstanceId: server.hostInstanceId,
      capabilities: server.capabilities,
      kind: "request" as const,
      id,
      method,
      params,
    }) as ActivationRequest;
    const response = new Promise<ActivationResponse>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Remote helper ${method} request timed out`));
      }, 15_000);
      this.pending.set(id, { request, resolve, reject, timer });
    });
    await this.channel.write(encodeJsonlFrame(request));
    const value = await response;
    if (value.error) throw new Error(value.error.message);
    return value.result as ActivationRpcMap[M]["result"];
  }

  async close(): Promise<void> {
    this.closed = true;
    this.fail(new Error("Remote helper activation channel closed"));
    await this.channel.close();
  }

  private receive(bytes: Uint8Array): void {
    try {
      const result = this.decoder.push(bytes);
      for (const value of result.frames) {
        if (!this.server) {
          this.server = decodeActivationServerHello(value, this.hello);
          this.binding = Object.freeze({
            mode: this.hello.mode,
            context: Object.freeze({
              protocolVersion: this.server.protocolVersion,
              helperVersion: this.server.helperVersion,
              activationId: this.server.activationId,
              hostInstanceId: this.server.hostInstanceId,
              capabilities: this.server.capabilities,
            }),
          });
          this.resolveReady(this.server);
          continue;
        }
        if (!this.binding) throw new Error("Remote helper activation binding is unavailable");
        if (typeof value === "object" && value !== null
          && (value as { kind?: unknown }).kind === "protocol-error") {
          const protocolError = decodeActivationProtocolError(value, this.binding.context);
          throw new Error(protocolError.message);
        }
        const id = typeof value === "object" && value !== null
          ? (value as { id?: unknown }).id : null;
        if (typeof id !== "string") throw new Error("Remote helper response omitted its request ID");
        const pending = this.pending.get(id);
        if (!pending) throw new Error("Remote helper returned an unknown request ID");
        const response = decodeActivationResponse(value, pending.request);
        clearTimeout(pending.timer);
        this.pending.delete(id);
        pending.resolve(response);
      }
    }
    catch (error) { this.fail(error); }
  }

  private fail(error: unknown): void {
    if (this.closed && !this.pending.size) return;
    this.closed = true;
    this.rejectReady(error);
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
  }
}

export interface RemoteRepositoryBrowser {
  readonly alias: string;
  home(): Promise<CanonicalRemoteDirectory>;
  canonicalize(path: string): Promise<CanonicalRemoteDirectory>;
  listDirectories(path: CanonicalRemoteDirectory): Promise<readonly RemoteDirectoryEntry[]>;
  probeCodex(): Promise<CodexProbeResult>;
  resolveRepository(path: string): Promise<ResolvedSshRepositoryTarget>;
  close(): Promise<void>;
}

type MasterBinding = Readonly<{
  master: SshMaster;
  target: ResolvedSshRepositoryTarget;
}>;

/** Owns remote repository discovery, helper installation, identity restoration, and AgentConnection. */
export class RemoteWorkbenchTargetService {
  private readonly profiles;
  private readonly transport;
  private active: MasterBinding | null = null;
  private pending: MasterBinding | null = null;

  constructor(
    bridge: NativeBridge,
    private readonly assets: BundledRemoteHelperAssets,
  ) {
    const created = createNativeSshTargetTransport(bridge);
    this.profiles = created.profiles;
    this.transport = created.transport;
  }

  async listProfiles(): Promise<readonly string[]> {
    return (await this.profiles.listConcreteAliases()).map(({ alias }) => alias);
  }

  async browse(alias: string): Promise<RemoteRepositoryBrowser> {
    await this.discardPending();
    const master = await this.connectInstalled(alias);
    const channel = await master.openBrowse();
    const hello = activationHello("browse", null, null);
    const client = new ActivationClient(channel, hello);
    try { await client.connect(); }
    catch (error) { await master.close().catch(() => {}); throw error; }
    let transferred = false;
    const browser: RemoteRepositoryBrowser = {
      alias,
      home: async () => (await client.invoke("browse.home", {})).path,
      canonicalize: async (input: string) => (
        await client.invoke("browse.canonicalize", { input })
      ).path,
      listDirectories: async (path: CanonicalRemoteDirectory) => (
        await client.invoke("browse.listDirectories", { path })
      ).entries,
      probeCodex: () => client.invoke("codex.probe", {}),
      resolveRepository: async (path: string) => {
        const canonical = await client.invoke("browse.canonicalize", { input: path });
        const target = await this.handshake(master, canonical.path);
        transferred = true;
        await this.discardPending();
        this.pending = Object.freeze({ master, target });
        await client.close().catch(() => {});
        return target;
      },
      close: async () => {
        await client.close().catch(() => {});
        if (!transferred) await master.close().catch(() => {});
      },
    };
    return Object.freeze(browser);
  }

  async restore(target: ResolvedSshRepositoryTarget): Promise<ResolvedSshRepositoryTarget> {
    await this.discardPending();
    const master = await this.connectInstalled(target.sshProfile);
    try {
      if (master.acceptedHostKeyFingerprint !== target.acceptedHostKeyFingerprint) {
        throw new Error("The remote SSH host key changed; choose the repository again");
      }
      const resolved = await this.handshake(master, target.canonicalRoot, target.hostInstanceId);
      if (!sameTargetIdentity(resolved, target)) {
        throw new Error("The stored remote repository identity no longer matches");
      }
      this.pending = Object.freeze({ master, target: resolved });
      return resolved;
    }
    catch (error) { await master.close().catch(() => {}); throw error; }
  }

  commit(target: ResolvedSshRepositoryTarget): void {
    if (!this.pending || this.pending.target.targetId !== target.targetId) {
      throw new Error("Remote repository connection was not staged");
    }
    const previous = this.active;
    this.active = this.pending;
    this.pending = null;
    if (previous && previous.master !== this.active.master) void previous.master.close().catch(() => {});
  }

  async activateLocal(): Promise<void> {
    await this.discardPending();
    const active = this.active;
    this.active = null;
    if (active) await active.master.close().catch(() => {});
  }

  async cancelPending(): Promise<void> {
    await this.discardPending();
  }

  async openAgent(snapshot: RepositoryTargetSnapshot): Promise<WebSocketLike> {
    if (snapshot.target.kind !== "ssh") throw new Error("Remote AgentConnection requires an SSH target");
    let binding = this.active;
    if (!binding || binding.target.targetId !== snapshot.target.targetId) {
      await this.restore(snapshot.target);
      this.commit(snapshot.target);
      binding = this.active;
    }
    if (!binding) throw new Error("Remote repository connection is unavailable");
    try {
      return new RemoteAgentConnection(await binding.master.openAgent(), {
        target: snapshot.target,
        targetEpoch: snapshot.targetEpoch,
      });
    }
    catch {
      await binding.master.close().catch(() => {});
      this.active = null;
      await this.restore(snapshot.target);
      this.commit(snapshot.target);
      return new RemoteAgentConnection(await this.active!.master.openAgent(), {
        target: snapshot.target,
        targetEpoch: snapshot.targetEpoch,
      });
    }
  }

  async close(): Promise<void> {
    await this.discardPending();
    const active = this.active;
    this.active = null;
    if (active) await active.master.close().catch(() => {});
  }

  private async connectInstalled(alias: string): Promise<SshMaster> {
    const master = await this.transport.connect(alias);
    try {
      const platform = await master.probeRemotePlatform();
      const tuple: RemoteHelperTuple = platform.arch === "x86_64"
        ? "linux-x86_64-static" : "linux-aarch64-static";
      await master.installVerifiedHelper(await this.assets.load(tuple));
      return master;
    }
    catch (error) { await master.close().catch(() => {}); throw error; }
  }

  private async handshake(
    master: SshMaster,
    root: string,
    expectedHostInstanceId: string | null = null,
  ): Promise<ResolvedSshRepositoryTarget> {
    const channel = await master.openRepositoryHandshake();
    const client = new ActivationClient(channel, activationHello(
      "repository-handshake", root, expectedHostInstanceId,
    ));
    try {
      const server = await client.connect();
      if (!server.canonicalRoot || !server.repositoryUuid) {
        throw new Error("The selected remote folder is not a Research Loop repository");
      }
      const endpointId = deriveSshEndpointId(
        master.acceptedHostKeyFingerprint,
        server.hostInstanceId,
        geckoTargetDigest,
      );
      const repositoryId = deriveRepositoryId(endpointId, server.repositoryUuid, geckoTargetDigest);
      const targetId = deriveTargetId(endpointId, server.canonicalRoot, repositoryId, geckoTargetDigest);
      return Object.freeze({
        kind: "ssh" as const,
        sshProfile: master.profile.alias,
        root,
        canonicalRoot: server.canonicalRoot,
        acceptedHostKeyFingerprint: master.acceptedHostKeyFingerprint,
        endpointId,
        hostInstanceId: server.hostInstanceId,
        repositoryUuid: server.repositoryUuid,
        repositoryId,
        targetId,
      });
    }
    finally { await client.close().catch(() => {}); }
  }

  private async discardPending(): Promise<void> {
    const pending = this.pending;
    this.pending = null;
    if (pending) await pending.master.close().catch(() => {});
  }
}

function activationHello(
  mode: ActivationClientHello["mode"],
  candidateRoot: string | null,
  expectedHostInstanceId: string | null,
): ActivationClientHello {
  const capabilities = mode === "browse" ? ["browse", "codex-probe"]
    : mode === "setup-auth" ? ["codex-device-auth-pty"] : [];
  return Object.freeze({
    kind: "hello",
    phase: "activation",
    requestId: randomID("activation-hello").slice(0, 128),
    protocolVersion: REMOTE_HELPER_PROTOCOL_VERSION,
    helperVersion: REMOTE_HELPER_VERSION,
    activationId: randomID("activation").slice(0, 128),
    mode,
    candidateRoot,
    expectedHostInstanceId,
    requestedCapabilities: Object.freeze(capabilities),
  });
}

function sameTargetIdentity(
  left: ResolvedSshRepositoryTarget,
  right: ResolvedSshRepositoryTarget,
): boolean {
  return left.sshProfile === right.sshProfile
    && left.canonicalRoot === right.canonicalRoot
    && left.acceptedHostKeyFingerprint === right.acceptedHostKeyFingerprint
    && left.endpointId === right.endpointId
    && left.hostInstanceId === right.hostInstanceId
    && left.repositoryUuid === right.repositoryUuid
    && left.repositoryId === right.repositoryId
    && left.targetId === right.targetId;
}
