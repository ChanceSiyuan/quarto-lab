import type {
  NativeProcessExit,
  NativeProcessSession,
  NativePtyProcessSession,
  NativeSshSetupAction,
  NativeBridge,
  SpawnOptions,
  VerifiedRemoteHelperCommand,
} from "./native-bridge";
import {
  NativeBridgeOpenSshProfileRuntime,
  OpenSshProfileProvider,
  type ResolvedOpenSshProfile,
} from "./openssh-profiles";
import type { AcceptedHostKeyFingerprint } from "./repository-target";
import { makeLocalFile, profilePath, sleep } from "./platform";

export type VerifiedRemoteHelperPath = string & {
  readonly __verifiedRemoteHelperPath: unique symbol;
};
export type { VerifiedRemoteHelperCommand } from "./native-bridge";
export type VerifiedRemoteHelperArtifact = Uint8Array & {
  readonly __verifiedRemoteHelperArtifact: unique symbol;
};

export type RemoteHelperTuple = "linux-x86_64-static" | "linux-aarch64-static";

export type InstalledHelper = Readonly<{
  helperVersion: string;
  tuple: RemoteHelperTuple;
  executableSha256: string;
  absoluteVersionedPath: VerifiedRemoteHelperPath;
}>;

export type VerifiedHelperInstall = Readonly<{
  manifest: Readonly<{
    helperVersion: string;
    tuple: RemoteHelperTuple;
    archiveSha256: string;
    executableSha256: string;
  }>;
  artifact: VerifiedRemoteHelperArtifact;
}>;

export type SshChannelExit = Readonly<{
  code: number | null;
  signal: number | null;
  reason: string;
}>;

export interface SshChannel {
  readonly channelId: string;
  readonly generation: number;
  write(bytes: Uint8Array): Promise<void>;
  onBytes(listener: (bytes: Uint8Array) => void): () => void;
  onExit(listener: (exit: SshChannelExit) => void): () => void;
  close(): Promise<void>;
}

export interface RemoteSetupSession {
  readonly generation: number;
  write(bytes: Uint8Array): Promise<void>;
  onBytes(listener: (bytes: Uint8Array) => void): () => void;
  onExit(listener: (exit: SshChannelExit) => void): () => void;
  resize(rows: number, cols: number): void;
  close(): Promise<void>;
}

export type SshMasterLoss = Readonly<{
  generation: number;
  exit: SshChannelExit;
}>;

export interface SshMaster {
  readonly profile: ResolvedOpenSshProfile;
  readonly controlPath: string;
  readonly generation: number;
  readonly acceptedHostKeyFingerprint: AcceptedHostKeyFingerprint;
  readonly installedHelper: InstalledHelper | null;
  probeRemotePlatform(): Promise<Readonly<{
    os: "linux";
    arch: "x86_64" | "aarch64";
    kernel: string;
  }>>;
  installVerifiedHelper(input: VerifiedHelperInstall): Promise<InstalledHelper>;
  openBrowse(): Promise<SshChannel>;
  openRepositoryHandshake(): Promise<SshChannel>;
  openAgent(): Promise<SshChannel>;
  openSetupAuth(): Promise<RemoteSetupSession>;
  onLost(listener: (loss: SshMasterLoss) => void): () => void;
  close(): Promise<void>;
}

export type SetupAction = NativeSshSetupAction;

export interface SshTransportRuntime {
  resolveProfile(alias: string): Promise<ResolvedOpenSshProfile>;
  createPrivateDirectory(): Promise<string>;
  createRegularFileNoFollow(path: string, mode: 0o600): Promise<void>;
  inspectPath(path: string): Promise<Readonly<{
    kind: "file" | "socket" | "symlink" | "directory";
    mode: number;
  }> | null>;
  readTextFileBounded(path: string, maxBytes: number): Promise<string>;
  isSocket(path: string): Promise<boolean>;
  wait(milliseconds: number): Promise<void>;
  openPipeProcess(options: SpawnOptions): Promise<NativeProcessSession>;
  openPtyProcess(options: SpawnOptions): Promise<NativePtyProcessSession>;
  openSshSetupProcess(action: SetupAction, cwd: string): Promise<NativePtyProcessSession>;
  installVerifiedHelper(input: VerifiedHelperInstall): Promise<InstalledHelper>;
  removeFile(path: string): Promise<void>;
  removePrivateDirectory(path: string): Promise<void>;
}

export interface SshTransportFiles {
  createPrivateDirectory(): Promise<string>;
  createRegularFileNoFollow(path: string, mode: 0o600): Promise<void>;
  inspectPath(path: string): Promise<Readonly<{
    kind: "file" | "socket" | "symlink" | "directory";
    mode: number;
  }> | null>;
  readTextFileBounded(path: string, maxBytes: number): Promise<string>;
  isSocket(path: string): Promise<boolean>;
  removeFile(path: string): Promise<void>;
  removePrivateDirectory(path: string): Promise<void>;
}

/** Secure Gecko filesystem owner for private master directories created by this instance. */
export class GeckoSshTransportFiles implements SshTransportFiles {
  private readonly ownedDirectories = new Set<string>();

  constructor(private readonly root = profilePath("run", "ssh-masters")) {}

  async createPrivateDirectory(): Promise<string> {
    await IOUtils.makeDirectory(this.root, {
      createAncestors: true,
      ignoreExisting: true,
      permissions: 0o700,
    });
    const root = makeLocalFile(this.root);
    root.permissions = 0o700;
    const directory = makeLocalFile(`${this.root}/master`);
    directory.createUnique(Ci.nsIFile.DIRECTORY_TYPE, 0o700);
    directory.permissions = 0o700;
    this.ownedDirectories.add(directory.path);
    return directory.path;
  }

  async createRegularFileNoFollow(path: string, mode: 0o600): Promise<void> {
    this.requireOwnedChild(path);
    const file = makeLocalFile(path);
    if (file.exists()) throw new Error("SSH master log path already exists");
    file.create(Ci.nsIFile.NORMAL_FILE_TYPE, mode);
    if (file.isSymlink() || !file.isFile()) throw new Error("SSH master log is not a regular file");
    file.permissions = mode;
  }

  async inspectPath(path: string): Promise<Readonly<{
    kind: "file" | "socket" | "symlink" | "directory";
    mode: number;
  }> | null> {
    const file = makeLocalFile(path);
    if (!file.exists()) return null;
    const kind = file.isSymlink() ? "symlink" as const
      : file.isDirectory() ? "directory" as const
        : file.isFile() ? "file" as const
          : "socket" as const;
    return { kind, mode: file.permissions & 0o777 };
  }

  async readTextFileBounded(path: string, maxBytes: number): Promise<string> {
    this.requireOwnedChild(path);
    const stat = await IOUtils.stat(path);
    if (stat.size > maxBytes) throw new Error("SSH master log exceeds its size bound");
    const value = await IOUtils.readUTF8(path);
    if (new TextEncoder().encode(value).length > maxBytes) {
      throw new Error("SSH master log exceeds its size bound");
    }
    return value;
  }

  async isSocket(path: string): Promise<boolean> {
    this.requireOwnedChild(path);
    const file = makeLocalFile(path);
    return file.exists() && !file.isSymlink() && !file.isFile()
      && !file.isDirectory() && file.isSpecial();
  }

  async removeFile(path: string): Promise<void> {
    this.requireOwnedChild(path);
    await IOUtils.remove(path, { ignoreAbsent: true });
  }

  async removePrivateDirectory(path: string): Promise<void> {
    if (!this.ownedDirectories.delete(path)) {
      throw new Error("Refusing to remove an unowned SSH runtime directory");
    }
    await IOUtils.remove(path, { ignoreAbsent: true, recursive: true });
  }

  private requireOwnedChild(path: string): void {
    if (![...this.ownedDirectories].some((directory) =>
      path.startsWith(`${directory}/`) && !path.slice(directory.length + 1).includes("/")
    )) throw new Error("SSH runtime path is outside its owned private directory");
  }
}

export class NativeBridgeSshTransportRuntime implements SshTransportRuntime {
  private readonly files: SshTransportFiles;

  constructor(private readonly options: Readonly<{
    profiles: Pick<OpenSshProfileProvider, "resolve">;
    bridge: Pick<NativeBridge,
      "openPipeProcess" | "openPtyProcess" | "openSshSetupProcess">;
    files?: SshTransportFiles;
    installVerifiedHelper?: (input: VerifiedHelperInstall) => Promise<InstalledHelper>;
  }>) {
    this.files = options.files || new GeckoSshTransportFiles();
  }

  resolveProfile(alias: string): Promise<ResolvedOpenSshProfile> {
    return this.options.profiles.resolve(alias);
  }
  createPrivateDirectory(): Promise<string> { return this.files.createPrivateDirectory(); }
  createRegularFileNoFollow(path: string, mode: 0o600): Promise<void> {
    return this.files.createRegularFileNoFollow(path, mode);
  }
  inspectPath(path: string) { return this.files.inspectPath(path); }
  readTextFileBounded(path: string, maxBytes: number): Promise<string> {
    return this.files.readTextFileBounded(path, maxBytes);
  }
  isSocket(path: string): Promise<boolean> { return this.files.isSocket(path); }
  wait(milliseconds: number): Promise<void> { return sleep(milliseconds); }
  openPipeProcess(options: SpawnOptions): Promise<NativeProcessSession> {
    return this.options.bridge.openPipeProcess(options);
  }
  openPtyProcess(options: SpawnOptions): Promise<NativePtyProcessSession> {
    return this.options.bridge.openPtyProcess(options);
  }
  openSshSetupProcess(action: SetupAction, cwd: string): Promise<NativePtyProcessSession> {
    return this.options.bridge.openSshSetupProcess(action, cwd);
  }
  installVerifiedHelper(input: VerifiedHelperInstall): Promise<InstalledHelper> {
    if (!this.options.installVerifiedHelper) {
      return Promise.reject(new Error("Verified remote helper installer is not configured"));
    }
    return this.options.installVerifiedHelper(input);
  }
  removeFile(path: string): Promise<void> { return this.files.removeFile(path); }
  removePrivateDirectory(path: string): Promise<void> {
    return this.files.removePrivateDirectory(path);
  }
}

export const REMOTE_PLATFORM_PROBE_SCRIPT = "uname -s; uname -m; uname -r";

const SSH = "/usr/bin/ssh" as const;
const MAX_MASTER_LOG_BYTES = 256 * 1024;
const MASTER_READY_ATTEMPTS = 100;
const MASTER_READY_DELAY_MS = 20;
const PROCESS_EXIT_ATTEMPTS = 50;
const FINGERPRINT_PATTERN = /^SHA256:[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]$/u;
const DIGEST_PATTERN = /^[a-f0-9]{64}$/u;

function processOptions(argv: readonly string[], cwd: string): SpawnOptions {
  return { argv, cwd };
}

function masterArgv(alias: string, logPath: string, controlPath: string): readonly string[] {
  return [
    SSH, "-v", "-E", logPath, "-MN", "-o", "FingerprintHash=sha256",
    "-o", "ControlMaster=yes", "-o", "ControlPersist=600", "-o", "BatchMode=yes",
    "-o", `ControlPath=${controlPath}`, "--", alias,
  ];
}

function shellQuote(value: string): string {
  if (/\0|\r|\n/u.test(value)) throw new Error("Remote helper command contains an invalid path");
  return `'${value.replaceAll("'", `'"'"'`)}'`;
}

function verifiedHelperCommand(
  helperPath: VerifiedRemoteHelperPath,
  ...mode: readonly string[]
): VerifiedRemoteHelperCommand {
  return [helperPath, ...mode].map(shellQuote).join(" ") as VerifiedRemoteHelperCommand;
}

function fixedChannelArgv(
  alias: string,
  controlPath: string,
  helperPath: VerifiedRemoteHelperPath,
  mode: "browse" | "repository-handshake" | "agent",
): readonly string[] {
  return [
    SSH, "-T", "-S", controlPath, "-o", "BatchMode=yes", "--",
    alias, verifiedHelperCommand(helperPath, mode),
  ];
}

function canonicalFingerprintFromLog(source: string): AcceptedHostKeyFingerprint | null {
  const fingerprints = new Set<string>();
  for (const line of source.split(/\r?\n/u)) {
    const diagnostic = /(?:^|\s)Server host key:/u.test(line);
    const match = /(?:^|\s)Server host key:\s+\S+\s+(SHA256:\S+)\s*$/u.exec(line);
    if (!match) {
      if (diagnostic) throw new Error("SSH master log contains a malformed authenticated host key");
      continue;
    }
    const fingerprint = match[1]!;
    if (!FINGERPRINT_PATTERN.test(fingerprint)) {
      throw new Error("SSH master log contains a malformed authenticated host key");
    }
    fingerprints.add(fingerprint);
  }
  if (fingerprints.size > 1) throw new Error("SSH master log contains distinct authenticated host keys");
  return fingerprints.size === 1 ? [...fingerprints][0]! : null;
}

function lastDiagnostic(buffer: string): string {
  const line = buffer.split(/\r?\n/u).map((value) => value.trim()).filter(Boolean).at(-1);
  return line?.slice(0, 512) || "SSH master exited";
}

function mapExit(exit: NativeProcessExit, reason: string): SshChannelExit {
  return { code: exit.exitCode, signal: exit.signal, reason };
}

function notify<T>(listeners: ReadonlySet<(value: T) => void>, value: T): void {
  for (const listener of [...listeners]) {
    try { listener(value); }
    catch { /* one consumer cannot break resource ownership or fanout */ }
  }
}

function collectProcess(process: NativeProcessSession): {
  output: () => Uint8Array;
  overflowed: () => boolean;
  exited: Promise<NativeProcessExit>;
} {
  const chunks: Uint8Array[] = [];
  let size = 0;
  let overflowed = false;
  process.onBytes((bytes) => {
    if (size + bytes.length > MAX_MASTER_LOG_BYTES) {
      overflowed = true;
      return;
    }
    chunks.push(bytes.slice());
    size += bytes.length;
  });
  const exited = new Promise<NativeProcessExit>((resolve) => process.onExit(resolve));
  return {
    output: () => {
      const output = new Uint8Array(size);
      let offset = 0;
      for (const chunk of chunks) {
        output.set(chunk, offset);
        offset += chunk.length;
      }
      return output;
    },
    overflowed: () => overflowed,
    exited,
  };
}

class OwnedChannel implements SshChannel {
  private readonly bytesListeners = new Set<(bytes: Uint8Array) => void>();
  private readonly exitListeners = new Set<(exit: SshChannelExit) => void>();
  private exited = false;
  private exitValue: SshChannelExit | null = null;
  private closed = false;
  private closePromise: Promise<void> | null = null;

  constructor(
    readonly channelId: string,
    readonly generation: number,
    private readonly process: NativeProcessSession,
    private readonly release: (channel: OwnedChannel) => void,
  ) {
    process.onBytes((bytes) => {
      if (this.closed || this.exited) return;
      notify(this.bytesListeners, bytes);
    });
    process.onExit((exit) => this.finish(mapExit(exit, "SSH channel exited")));
  }

  async write(bytes: Uint8Array): Promise<void> {
    if (this.closed || this.exited) throw new Error("SSH channel is closed or its master was lost");
    await this.process.write(bytes);
  }

  onBytes(listener: (bytes: Uint8Array) => void): () => void {
    this.bytesListeners.add(listener);
    return () => this.bytesListeners.delete(listener);
  }

  onExit(listener: (exit: SshChannelExit) => void): () => void {
    if (this.exitValue) {
      listener(this.exitValue);
      return () => {};
    }
    this.exitListeners.add(listener);
    return () => this.exitListeners.delete(listener);
  }

  close(): Promise<void> {
    if (this.closePromise) return this.closePromise;
    this.closed = true;
    this.release(this);
    this.closePromise = this.process.close();
    return this.closePromise;
  }

  fail(exit: SshChannelExit): Promise<void> {
    if (!this.exited) this.finish(exit);
    return this.close();
  }

  get isExited(): boolean { return this.exited; }

  private finish(exit: SshChannelExit): void {
    if (this.exited) return;
    this.exited = true;
    this.exitValue = exit;
    this.release(this);
    notify(this.exitListeners, exit);
  }
}

class OwnedSetupSession implements RemoteSetupSession {
  private readonly exitListeners = new Set<(exit: SshChannelExit) => void>();
  private exited = false;
  private exitValue: SshChannelExit | null = null;
  private closed = false;
  private closePromise: Promise<void> | null = null;

  constructor(
    readonly generation: number,
    private readonly process: NativePtyProcessSession,
    private readonly release: () => void,
  ) {
    process.onExit((exit) => {
      if (this.exited) return;
      this.exited = true;
      this.release();
      const mapped = mapExit(exit, "SSH setup session exited");
      this.exitValue = mapped;
      notify(this.exitListeners, mapped);
    });
  }

  write(bytes: Uint8Array): Promise<void> {
    if (this.closed || this.exited) return Promise.reject(new Error("SSH setup session is closed"));
    return this.process.write(bytes);
  }

  onBytes(listener: (bytes: Uint8Array) => void): () => void {
    return this.process.onBytes(listener);
  }

  onExit(listener: (exit: SshChannelExit) => void): () => void {
    if (this.exitValue) {
      listener(this.exitValue);
      return () => {};
    }
    this.exitListeners.add(listener);
    return () => this.exitListeners.delete(listener);
  }

  resize(rows: number, cols: number): void {
    if (this.closed || this.exited) throw new Error("SSH setup session is closed");
    this.process.resize(rows, cols);
  }

  close(): Promise<void> {
    if (this.closePromise) return this.closePromise;
    this.closed = true;
    this.release();
    this.closePromise = this.process.close();
    return this.closePromise;
  }

  fail(exit: SshChannelExit): Promise<void> {
    if (!this.exited) {
      this.exited = true;
      this.exitValue = exit;
      this.release();
      notify(this.exitListeners, exit);
    }
    return this.close();
  }

  get isExited(): boolean { return this.exited; }
}

class OwnedProbe {
  private closePromise: Promise<void> | null = null;
  private lossError: Error | null = null;
  private rejectLoss: ((error: Error) => void) | null = null;

  constructor(private readonly process: NativeProcessSession) {}

  waitForExit(exit: Promise<NativeProcessExit>): Promise<NativeProcessExit> {
    if (this.lossError) return Promise.reject(this.lossError);
    const loss = new Promise<never>((_resolve, reject) => { this.rejectLoss = reject; });
    return Promise.race([exit, loss]);
  }

  fail(reason: string): Promise<void> {
    if (!this.lossError) {
      this.lossError = new Error(reason);
      this.rejectLoss?.(this.lossError);
    }
    return this.close();
  }

  close(): Promise<void> {
    if (this.closePromise) return this.closePromise;
    this.closePromise = this.process.close();
    return this.closePromise;
  }
}

class OwnedSshMaster implements SshMaster {
  private helper: InstalledHelper | null = null;
  private installInFlight = false;
  private readonly channels = new Set<OwnedChannel>();
  private readonly setups = new Set<OwnedSetupSession>();
  private readonly probes = new Set<OwnedProbe>();
  private readonly lossListeners = new Set<(loss: SshMasterLoss) => void>();
  private state: "active" | "closing" | "lost" | "closed" = "active";
  private cleanupPromise: Promise<void> | null = null;
  private closePromise: Promise<void> | null = null;
  private lossClosePromise: Promise<void> = Promise.resolve();
  private activeOperations = 0;
  private readonly operationWaiters = new Set<() => void>();
  private masterExited = false;
  private masterDiagnostics = "";
  private nextChannel = 0;

  constructor(
    readonly profile: ResolvedOpenSshProfile,
    readonly controlPath: string,
    readonly generation: number,
    readonly acceptedHostKeyFingerprint: AcceptedHostKeyFingerprint,
    private readonly runtime: SshTransportRuntime,
    private readonly directory: string,
    private readonly logPath: string,
    private readonly masterProcess: NativePtyProcessSession,
  ) {
    masterProcess.onBytes((bytes) => {
      if (this.masterDiagnostics.length >= 32 * 1024) return;
      this.masterDiagnostics = (this.masterDiagnostics + new TextDecoder().decode(bytes))
        .slice(-(32 * 1024));
    });
    masterProcess.onExit((exit) => this.masterLost(exit));
  }

  get installedHelper(): InstalledHelper | null { return this.helper; }

  async probeRemotePlatform(): Promise<Readonly<{
    os: "linux";
    arch: "x86_64" | "aarch64";
    kernel: string;
  }>> {
    const releaseOperation = this.beginOperation();
    let probe: OwnedProbe | null = null;
    try {
      const argv = [
        SSH, "-T", "-S", this.controlPath, "-o", "BatchMode=yes", "--",
        this.profile.alias, REMOTE_PLATFORM_PROBE_SCRIPT,
      ];
      const process = await this.runtime.openPipeProcess(processOptions(argv, this.directory));
      const collected = collectProcess(process);
      probe = new OwnedProbe(process);
      this.probes.add(probe);
      await this.assertActiveOrClose(process);
      const exit = await probe.waitForExit(collected.exited);
      this.assertActive();
      if (exit.exitCode !== 0 || exit.signal !== null || collected.overflowed()) {
        throw new Error("Remote platform probe failed or exceeded its output bound");
      }
      const lines = new TextDecoder().decode(collected.output()).split(/\r?\n/u);
      if (lines.at(-1) === "") lines.pop();
      if (lines.length !== 3 || lines.some((line) => !line || line.length > 256)) {
        throw new Error("Remote platform probe returned malformed output");
      }
      const [os, rawArch, kernel] = lines as [string, string, string];
      if (os !== "Linux" || (rawArch !== "x86_64" && rawArch !== "aarch64") || /\s/u.test(kernel)) {
        throw new Error("Remote platform probe returned an unsupported platform");
      }
      return Object.freeze({ os: "linux" as const, arch: rawArch, kernel });
    }
    finally {
      if (probe) this.probes.delete(probe);
      releaseOperation();
    }
  }

  installVerifiedHelper(input: VerifiedHelperInstall): Promise<InstalledHelper> {
    try {
      this.assertActive();
      if (this.helper || this.installInFlight) {
        throw new Error("A verified helper install is already bound or in progress");
      }
      this.installInFlight = true;
      return this.installVerifiedHelperInternal(input).finally(() => {
        this.installInFlight = false;
      });
    }
    catch (error) {
      return Promise.reject(error);
    }
  }

  private async installVerifiedHelperInternal(input: VerifiedHelperInstall): Promise<InstalledHelper> {
    if (!input.artifact.length || !DIGEST_PATTERN.test(input.manifest.archiveSha256)
      || !DIGEST_PATTERN.test(input.manifest.executableSha256)
      || !/^\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?$/u.test(input.manifest.helperVersion)) {
      throw new Error("Verified helper install input is malformed");
    }
    const installed = await this.runtime.installVerifiedHelper(input);
    const expectedSuffix = `/${input.manifest.helperVersion}/${input.manifest.tuple}/qlab-remote`;
    if (installed.helperVersion !== input.manifest.helperVersion
      || installed.tuple !== input.manifest.tuple
      || installed.executableSha256 !== input.manifest.executableSha256
      || !installed.absoluteVersionedPath.startsWith("/")
      || !installed.absoluteVersionedPath.endsWith(expectedSuffix)
      || /\0|\r|\n/u.test(installed.absoluteVersionedPath)
      || /(?:^|\/)current(?:\/|$)/u.test(installed.absoluteVersionedPath)) {
      throw new Error("Verified helper installer returned an invalid versioned binding");
    }
    this.assertActive();
    this.helper = Object.freeze({ ...installed });
    return this.helper;
  }

  openBrowse(): Promise<SshChannel> { return this.openFixedChannel("browse"); }
  openRepositoryHandshake(): Promise<SshChannel> { return this.openFixedChannel("repository-handshake"); }
  openAgent(): Promise<SshChannel> { return this.openFixedChannel("agent"); }

  async openSetupAuth(): Promise<RemoteSetupSession> {
    this.assertActive();
    const helper = this.requireHelper();
    const action: SetupAction = { kind: "codex-device-auth", argv: [
      SSH, "-tt", "-S", this.controlPath, "-o", "BatchMode=yes", "--",
      this.profile.alias, verifiedHelperCommand(
        helper.absoluteVersionedPath, "setup", "codex-device-auth",
      ),
    ] };
    const process = await this.runtime.openSshSetupProcess(action, this.directory);
    await this.assertActiveOrClose(process);
    let session!: OwnedSetupSession;
    session = new OwnedSetupSession(this.generation, process, () => this.setups.delete(session));
    if (!session.isExited) this.setups.add(session);
    return session;
  }

  onLost(listener: (loss: SshMasterLoss) => void): () => void {
    this.lossListeners.add(listener);
    return () => this.lossListeners.delete(listener);
  }

  close(): Promise<void> {
    if (this.closePromise) return this.closePromise;
    this.closePromise = this.closeInternal();
    return this.closePromise;
  }

  private async openFixedChannel(mode: "browse" | "repository-handshake" | "agent"): Promise<SshChannel> {
    this.assertActive();
    const helper = this.requireHelper();
    const process = await this.runtime.openPipeProcess(processOptions(
      fixedChannelArgv(this.profile.alias, this.controlPath, helper.absoluteVersionedPath, mode),
      this.directory,
    ));
    await this.assertActiveOrClose(process);
    const channel = new OwnedChannel(
      `ssh-${this.generation}-${++this.nextChannel}`,
      this.generation,
      process,
      (value) => this.channels.delete(value),
    );
    if (!channel.isExited) this.channels.add(channel);
    return channel;
  }

  private requireHelper(): InstalledHelper {
    if (!this.helper) throw new Error("A verified helper must be installed before opening this SSH channel");
    return this.helper;
  }

  private assertActive(): void {
    if (this.state !== "active") throw new Error("SSH master is lost or closed");
  }

  private async assertActiveOrClose(process: NativeProcessSession): Promise<void> {
    if (this.state !== "active") {
      await process.close();
      throw new Error("SSH master is lost or closed");
    }
  }

  private beginOperation(): () => void {
    this.assertActive();
    this.activeOperations += 1;
    let released = false;
    return () => {
      if (released) return;
      released = true;
      this.activeOperations -= 1;
      if (this.activeOperations === 0) {
        for (const resolve of [...this.operationWaiters]) resolve();
        this.operationWaiters.clear();
      }
    };
  }

  private waitForOperations(): Promise<void> {
    if (this.activeOperations === 0) return Promise.resolve();
    return new Promise<void>((resolve) => this.operationWaiters.add(resolve));
  }

  private masterLost(exit: NativeProcessExit): void {
    if (this.masterExited) return;
    this.masterExited = true;
    if (this.state === "closing" || this.state === "closed") return;
    this.state = "lost";
    const mapped = mapExit(exit, lastDiagnostic(this.masterDiagnostics));
    const closes = [
      ...[...this.channels].map((channel) => channel.fail(mapped)),
      ...[...this.setups].map((setup) => setup.fail(mapped)),
      ...[...this.probes].map((probe) => probe.fail("SSH master was lost during platform probe")),
    ];
    this.lossClosePromise = Promise.allSettled(closes).then(() => undefined);
    const loss = { generation: this.generation, exit: mapped };
    notify(this.lossListeners, loss);
    void this.cleanup().catch(() => {});
  }

  private async closeInternal(): Promise<void> {
    if (this.state === "closed") return;
    if (this.state === "lost") {
      await this.cleanup();
      return;
    }
    this.state = "closing";
    let primaryError: unknown = null;
    const closeResults = await Promise.allSettled([
      ...[...this.channels].map((channel) => channel.close()),
      ...[...this.setups].map((setup) => setup.close()),
      ...[...this.probes].map((probe) => probe.fail("SSH master was closed during platform probe")),
    ]);
    primaryError = closeResults.find((result) => result.status === "rejected")?.reason ?? null;
    let control: NativeProcessSession | null = null;
    try {
      control = await this.runtime.openPipeProcess(processOptions([
        SSH, "-S", this.controlPath, "-O", "exit", "--", this.profile.alias,
      ], this.directory));
      if (!await this.waitForExit(control)) await control.close();
      if (!this.masterExited && !await this.waitForExit(this.masterProcess)) {
        await this.masterProcess.close();
        await this.waitForExit(this.masterProcess, 10);
      }
    }
    catch (error) {
      primaryError ??= error;
    }
    finally {
      if (control) await control.close().catch((error) => { primaryError ??= error; });
      if (!this.masterExited) {
        await this.masterProcess.close().catch((error) => { primaryError ??= error; });
      }
      await this.cleanup().catch((error) => { primaryError ??= error; });
    }
    if (primaryError) throw primaryError;
  }

  private async waitForExit(
    process: NativeProcessSession,
    attempts = PROCESS_EXIT_ATTEMPTS,
  ): Promise<boolean> {
    let exited = false;
    const remove = process.onExit(() => { exited = true; });
    for (let attempt = 0; attempt < attempts && !exited; attempt++) {
      await this.runtime.wait(MASTER_READY_DELAY_MS);
    }
    remove();
    return exited;
  }

  private cleanup(): Promise<void> {
    if (this.cleanupPromise) return this.cleanupPromise;
    this.cleanupPromise = (async () => {
      let error: unknown = null;
      await this.lossClosePromise;
      await this.waitForOperations();
      await this.runtime.removeFile(this.controlPath).catch((failure) => { error ??= failure; });
      await this.runtime.removeFile(this.logPath).catch((failure) => { error ??= failure; });
      await this.runtime.removePrivateDirectory(this.directory).catch((failure) => { error ??= failure; });
      this.state = "closed";
      if (error) throw error;
    })();
    return this.cleanupPromise;
  }
}

export class SshTargetTransport {
  private nextGeneration = 1;

  constructor(private readonly runtime: SshTransportRuntime) {}

  async connect(alias: string): Promise<SshMaster> {
    const profile = await this.runtime.resolveProfile(alias);
    if (profile.alias !== alias) throw new Error("Resolved OpenSSH alias does not match the requested alias");
    const directory = await this.runtime.createPrivateDirectory();
    const logPath = `${directory}/master.log`;
    const controlPath = `${directory}/master.sock`;
    let masterProcess: NativePtyProcessSession | null = null;
    try {
      const privateDirectory = await this.runtime.inspectPath(directory);
      if (privateDirectory?.kind !== "directory" || privateDirectory.mode !== 0o700) {
        throw new Error("SSH master runtime must be a private 0700 directory");
      }
      await this.runtime.createRegularFileNoFollow(logPath, 0o600);
      const log = await this.runtime.inspectPath(logPath);
      if (log?.kind !== "file" || log.mode !== 0o600) {
        throw new Error("SSH master log must be a regular owner-only 0600 file");
      }
      masterProcess = await this.runtime.openPtyProcess(processOptions(
        masterArgv(profile.alias, logPath, controlPath), directory,
      ));
      let processExit: NativeProcessExit | null = null;
      masterProcess.onExit((exit) => { processExit = exit; });
      let fingerprint: AcceptedHostKeyFingerprint | null = null;
      let socketLive = false;
      for (let attempt = 0; attempt < MASTER_READY_ATTEMPTS; attempt++) {
        const source = await this.runtime.readTextFileBounded(logPath, MAX_MASTER_LOG_BYTES);
        fingerprint = canonicalFingerprintFromLog(source);
        socketLive = await this.runtime.isSocket(controlPath);
        if (fingerprint && socketLive) break;
        if (processExit) break;
        await this.runtime.wait(MASTER_READY_DELAY_MS);
      }
      if (processExit) throw new Error("SSH master exited before readiness completed");
      if (!fingerprint) throw new Error("SSH master log has no canonical authenticated host key");
      if (!socketLive) throw new Error("SSH master control socket did not become live");
      const generation = this.nextGeneration++;
      return new OwnedSshMaster(
        profile, controlPath, generation, fingerprint,
        this.runtime, directory, logPath, masterProcess,
      );
    }
    catch (error) {
      if (masterProcess) await masterProcess.close().catch(() => {});
      await this.runtime.removeFile(controlPath).catch(() => {});
      await this.runtime.removeFile(logPath).catch(() => {});
      await this.runtime.removePrivateDirectory(directory).catch(() => {});
      throw error;
    }
  }

  async openHostKeyAcceptance(alias: string): Promise<RemoteSetupSession> {
    const profile = await this.runtime.resolveProfile(alias);
    if (profile.alias !== alias) throw new Error("Resolved OpenSSH alias does not match the requested alias");
    const action: SetupAction = { kind: "accept-host-key", argv: [
      SSH, "-tt", "-o", "BatchMode=no", "-o", "ControlMaster=no",
      "--", profile.alias, "/bin/true",
    ] };
    const process = await this.runtime.openSshSetupProcess(action, "/");
    return new OwnedSetupSession(0, process, () => {});
  }
}

export function createNativeSshTargetTransport(
  bridge: NativeBridge,
  installVerifiedHelper?: (input: VerifiedHelperInstall) => Promise<InstalledHelper>,
): Readonly<{
  profiles: OpenSshProfileProvider;
  transport: SshTargetTransport;
}> {
  const profiles = new OpenSshProfileProvider(new NativeBridgeOpenSshProfileRuntime(bridge));
  const runtime = new NativeBridgeSshTransportRuntime({
    profiles,
    bridge,
    installVerifiedHelper,
  });
  return Object.freeze({ profiles, transport: new SshTargetTransport(runtime) });
}
