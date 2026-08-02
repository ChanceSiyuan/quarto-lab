import { describe, expect, it } from "vitest";

import type {
  NativeProcessExit, NativeProcessSession, NativePtyProcessSession, NativeSshSetupAction,
} from "../src/native-bridge";
import type { ResolvedOpenSshProfile } from "../src/openssh-profiles";
import {
  REMOTE_PLATFORM_PROBE_SCRIPT,
  NativeBridgeSshTransportRuntime,
  SshTargetTransport,
  type InstalledHelper,
  type SshTransportRuntime,
  type VerifiedHelperInstall,
  type VerifiedRemoteHelperArtifact,
  type VerifiedRemoteHelperPath,
} from "../src/ssh-target-transport";

const TARGET_FINGERPRINT = "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
const OTHER_FINGERPRINT = `SHA256:${"B".repeat(42)}E`;

function profile(alias = "qlab-gpu"): ResolvedOpenSshProfile {
  return {
    alias,
    hostname: "10.0.0.8",
    user: "alice",
    port: 22,
    identityFiles: ["~/.ssh/id_ed25519"],
    proxyJump: "bastion",
    proxyCommand: null,
    effectiveConfig: Object.freeze({
      hostname: ["10.0.0.8"], user: ["alice"], port: ["22"],
    }),
  };
}

class FakeProcess implements NativePtyProcessSession {
  readonly bytesListeners = new Set<(bytes: Uint8Array) => void>();
  readonly exitListeners = new Set<(exit: NativeProcessExit) => void>();
  readonly writes: Uint8Array[] = [];
  readonly resizes: Array<readonly [number, number]> = [];
  closeCount = 0;
  exited = false;
  exitValue: NativeProcessExit | null = null;

  constructor(readonly sessionId: string) {}

  async write(bytes: Uint8Array): Promise<void> { this.writes.push(bytes.slice()); }
  onBytes(listener: (bytes: Uint8Array) => void): () => void {
    this.bytesListeners.add(listener);
    return () => this.bytesListeners.delete(listener);
  }
  onExit(listener: (exit: NativeProcessExit) => void): () => void {
    if (this.exitValue) {
      listener(this.exitValue);
      return () => {};
    }
    this.exitListeners.add(listener);
    return () => this.exitListeners.delete(listener);
  }
  resize(rows: number, cols: number): void { this.resizes.push([rows, cols]); }
  async close(): Promise<void> { if (!this.closeCount) this.closeCount = 1; }
  emitText(value: string): void {
    const bytes = new TextEncoder().encode(value);
    for (const listener of [...this.bytesListeners]) listener(bytes);
  }
  exit(exitCode: number | null, signal: number | null = null): void {
    if (this.exited) return;
    this.exited = true;
    this.exitValue = { exitCode, signal };
    for (const listener of [...this.exitListeners]) listener(this.exitValue);
  }
}

class FakeSshRuntime implements SshTransportRuntime {
  readonly opens: Array<{ kind: "pipe" | "pty" | "raw-pty"; argv: string[] }> = [];
  readonly files = new Map<string, { kind: "file" | "socket" | "symlink" | "directory"; mode: number; text: string }>();
  readonly removed: string[] = [];
  readonly processes: FakeProcess[] = [];
  readonly setup = new Map<string, string>();
  readonly installCalls: VerifiedHelperInstall[] = [];
  readonly order: string[] = [];
  waitCalls = 0;
  private directoryNumber = 0;
  masterLog = `debug1: Server host key: ssh-ed25519 ${TARGET_FINGERPRINT}\n`;
  masterProxyDiagnostic = `jump-host: ${OTHER_FINGERPRINT}\n`;
  createLogAsSymlink = false;
  createSocket = true;
  directoryMode = 0o700;
  processNumber = 0;
  exitNextPipe: NativeProcessExit | null = null;
  exitMasterOnOpen: NativeProcessExit | null = null;
  installBarrier: Promise<void> | null = null;
  installerResult: InstalledHelper = {
    helperVersion: "1.2.3",
    tuple: "linux-x86_64-static",
    executableSha256: "c".repeat(64),
    absoluteVersionedPath: "/home/alice/.qlab/bin/1.2.3/linux-x86_64-static/qlab-remote" as VerifiedRemoteHelperPath,
  };

  async resolveProfile(alias: string): Promise<ResolvedOpenSshProfile> {
    if (!/^[A-Za-z0-9._-]+$/.test(alias) || alias !== "qlab-gpu") {
      throw new Error("Not a concrete OpenSSH alias");
    }
    return profile(alias);
  }

  async createPrivateDirectory(): Promise<string> {
    const path = `/private/ssh-master-${++this.directoryNumber}`;
    this.files.set(path, { kind: "directory", mode: this.directoryMode, text: "" });
    this.order.push(`mkdir:${path}:0700`);
    return path;
  }

  async createRegularFileNoFollow(path: string, mode: 0o600): Promise<void> {
    this.order.push(`create:${path}:0600:nofollow`);
    this.files.set(path, {
      kind: this.createLogAsSymlink ? "symlink" : "file",
      mode,
      text: "",
    });
  }

  async inspectPath(path: string) {
    const entry = this.files.get(path);
    return entry ? { kind: entry.kind, mode: entry.mode } as const : null;
  }

  async readTextFileBounded(path: string, maxBytes: number): Promise<string> {
    const text = this.files.get(path)?.text ?? "";
    if (new TextEncoder().encode(text).length > maxBytes) throw new Error("bounded file exceeded");
    return text;
  }

  async isSocket(path: string): Promise<boolean> { return this.files.get(path)?.kind === "socket"; }
  async wait(_milliseconds: number): Promise<void> { this.waitCalls += 1; }

  async openPipeProcess(options: { argv: readonly string[] }): Promise<NativeProcessSession> {
    const process = this.open("pipe", options.argv);
    if (this.exitNextPipe) {
      process.exit(this.exitNextPipe.exitCode, this.exitNextPipe.signal);
      this.exitNextPipe = null;
    }
    return process;
  }

  async openPtyProcess(options: { argv: readonly string[] }): Promise<NativePtyProcessSession> {
    const process = this.open("pty", options.argv);
    if (options.argv.includes("-MN")) {
      const logPath = options.argv[options.argv.indexOf("-E") + 1]!;
      this.files.get(logPath)!.text = this.masterLog;
      const control = options.argv.find((value) => value.startsWith("ControlPath="))!.slice("ControlPath=".length);
      if (this.createSocket) this.files.set(control, { kind: "socket", mode: 0o600, text: "" });
      process.emitText(this.masterProxyDiagnostic);
      if (this.exitMasterOnOpen) process.exit(this.exitMasterOnOpen.exitCode, this.exitMasterOnOpen.signal);
    }
    return process;
  }

  async openSshSetupProcess(action: NativeSshSetupAction): Promise<NativePtyProcessSession> {
    return this.open(action.kind === "codex-device-auth" ? "raw-pty" : "pty", action.argv);
  }

  private open(kind: "pipe" | "pty" | "raw-pty", argv: readonly string[]): FakeProcess {
    this.opens.push({ kind, argv: [...argv] });
    this.order.push(`open:${argv.join("\0")}`);
    const process = new FakeProcess(`fake-${++this.processNumber}`);
    this.processes.push(process);
    return process;
  }

  async installVerifiedHelper(input: VerifiedHelperInstall): Promise<InstalledHelper> {
    this.installCalls.push(input);
    if (this.installBarrier) await this.installBarrier;
    return this.installerResult;
  }

  async removeFile(path: string): Promise<void> {
    this.order.push(`remove-file:${path}`);
    this.removed.push(path);
    this.files.delete(path);
  }

  async removePrivateDirectory(path: string): Promise<void> {
    this.order.push(`remove-dir:${path}`);
    this.removed.push(path);
    this.files.delete(path);
  }

  master(): FakeProcess { return this.processes[0]!; }
  lastProcess(): FakeProcess { return this.processes.at(-1)!; }
  killMaster(code: number, reason: string): void {
    this.master().emitText(`${reason}\n`);
    this.master().exit(code);
  }
}

function verifiedInstall(): VerifiedHelperInstall {
  return {
    manifest: Object.freeze({
      helperVersion: "1.2.3",
      tuple: "linux-x86_64-static",
      archiveSha256: "b".repeat(64),
      executableSha256: "c".repeat(64),
    }),
    artifact: Uint8Array.from([1, 2, 3]) as VerifiedRemoteHelperArtifact,
  };
}

describe("SshTargetTransport master ownership", () => {
  it("instantiates the production transport adapter over NativeBridge and secure Gecko files", async () => {
    const host = new FakeSshRuntime();
    const runtime = new NativeBridgeSshTransportRuntime({
      profiles: { resolve: (alias) => host.resolveProfile(alias) },
      bridge: host,
      files: host,
      installVerifiedHelper: (input) => host.installVerifiedHelper(input),
    });

    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");

    expect(master.acceptedHostKeyFingerprint).toBe(TARGET_FINGERPRINT);
    expect(host.opens[0]?.argv[0]).toBe("/usr/bin/ssh");
  });

  it("creates one private master with the exact argv and accepts only its bounded -E fingerprint", async () => {
    const runtime = new FakeSshRuntime();
    const transport = new SshTargetTransport(runtime);

    const master = await transport.connect("qlab-gpu");

    expect(master.acceptedHostKeyFingerprint).toBe(TARGET_FINGERPRINT);
    expect(master.controlPath).toBe("/private/ssh-master-1/master.sock");
    expect(runtime.opens[0]).toEqual({
      kind: "pty",
      argv: [
        "/usr/bin/ssh", "-v", "-E", "/private/ssh-master-1/master.log", "-MN",
        "-o", "FingerprintHash=sha256", "-o", "ControlMaster=yes",
        "-o", "ControlPersist=600", "-o", "BatchMode=yes",
        "-o", "ControlPath=/private/ssh-master-1/master.sock", "--", "qlab-gpu",
      ],
    });
    expect(runtime.order.slice(0, 3)).toEqual([
      "mkdir:/private/ssh-master-1:0700",
      "create:/private/ssh-master-1/master.log:0600:nofollow",
      expect.stringContaining("open:/usr/bin/ssh\0-v\0-E\0/private/ssh-master-1/master.log"),
    ]);
    expect(await runtime.inspectPath("/private/ssh-master-1/master.log"))
      .toEqual({ kind: "file", mode: 0o600 });
  });

  it.each([
    ["missing", ""],
    ["malformed", "Server host key: ssh-ed25519 MD5:aa:bb\n"],
    ["valid plus malformed", `Server host key: ssh-ed25519 ${TARGET_FINGERPRINT}\nServer host key: ssh-rsa not-a-fingerprint\n`],
    ["distinct", `Server host key: ssh-ed25519 ${TARGET_FINGERPRINT}\nServer host key: ssh-rsa ${OTHER_FINGERPRINT}\n`],
  ])("fails closed for a %s authenticated-key log", async (_name, masterLog) => {
    const runtime = new FakeSshRuntime();
    runtime.masterLog = masterLog;

    await expect(new SshTargetTransport(runtime).connect("qlab-gpu"))
      .rejects.toThrow(/authenticated host key/i);
    expect(runtime.removed).toContain("/private/ssh-master-1");
  });

  it("allows identical target-key repeats but ignores proxy and configured identity sources", async () => {
    const runtime = new FakeSshRuntime();
    runtime.masterLog = `Server host key: ssh-ed25519 ${TARGET_FINGERPRINT}\nServer host key: ssh-ed25519 ${TARGET_FINGERPRINT}\n`;
    runtime.masterProxyDiagnostic = `ProxyCommand Server host key: ssh-rsa ${OTHER_FINGERPRINT}\n`;

    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");

    expect(master.acceptedHostKeyFingerprint).toBe(TARGET_FINGERPRINT);
    expect(JSON.stringify(master.profile)).not.toContain("acceptedHostKeyFingerprint");
  });

  it("rejects a symlink log, absent control socket, and invalid alias before master spawn", async () => {
    const permissive = new FakeSshRuntime();
    permissive.directoryMode = 0o755;
    await expect(new SshTargetTransport(permissive).connect("qlab-gpu"))
      .rejects.toThrow(/private.*0700/i);
    expect(permissive.opens).toHaveLength(0);

    const symlink = new FakeSshRuntime();
    symlink.createLogAsSymlink = true;
    await expect(new SshTargetTransport(symlink).connect("qlab-gpu"))
      .rejects.toThrow(/regular.*0600/i);
    expect(symlink.opens).toHaveLength(0);

    const socket = new FakeSshRuntime();
    socket.createSocket = false;
    await expect(new SshTargetTransport(socket).connect("qlab-gpu"))
      .rejects.toThrow(/control socket/i);

    const alias = new FakeSshRuntime();
    await expect(new SshTargetTransport(alias).connect("qlab gpu"))
      .rejects.toThrow(/concrete OpenSSH alias/i);
    expect(alias.opens).toHaveLength(0);
  });

  it("rejects helper openers before install and binds every fixed mode to one immutable versioned path", async () => {
    const runtime = new FakeSshRuntime();
    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");
    await expect(master.openBrowse()).rejects.toThrow(/verified helper/i);
    await expect(master.openRepositoryHandshake()).rejects.toThrow(/verified helper/i);
    await expect(master.openAgent()).rejects.toThrow(/verified helper/i);
    await expect(master.openSetupAuth()).rejects.toThrow(/verified helper/i);

    const installed = await master.installVerifiedHelper(verifiedInstall());
    runtime.installerResult = {
      ...runtime.installerResult,
      absoluteVersionedPath: "/home/alice/.qlab/bin/current/qlab-remote" as VerifiedRemoteHelperPath,
    };
    const [browse, repository, agent, setup] = await Promise.all([
      master.openBrowse(), master.openRepositoryHandshake(), master.openAgent(), master.openSetupAuth(),
    ]);

    const fixedPrefix = [
      "/usr/bin/ssh", "-T", "-S", master.controlPath,
      "-o", "BatchMode=yes", "--", "qlab-gpu",
    ];
    expect(runtime.opens.slice(1).map((open) => open.argv)).toEqual([
      [...fixedPrefix, `'${installed.absoluteVersionedPath}' 'browse'`],
      [...fixedPrefix, `'${installed.absoluteVersionedPath}' 'repository-handshake'`],
      [...fixedPrefix, `'${installed.absoluteVersionedPath}' 'agent'`],
      [
        "/usr/bin/ssh", "-tt", "-S", master.controlPath,
        "-o", "BatchMode=yes", "--", "qlab-gpu",
        `'${installed.absoluteVersionedPath}' 'setup' 'codex-device-auth'`,
      ],
    ]);
    expect(runtime.opens.slice(1).map((open) => open.kind)).toEqual([
      "pipe", "pipe", "pipe", "raw-pty",
    ]);
    expect([browse, repository, agent, setup].every((value) => value.generation === master.generation))
      .toBe(true);
    expect((master as unknown as Record<string, unknown>).open).toBeUndefined();
  });

  it("quotes the internally bound helper path as one fixed remote command", async () => {
    const runtime = new FakeSshRuntime();
    runtime.installerResult = {
      ...runtime.installerResult,
      absoluteVersionedPath: "/home/al'ice/.qlab/bin/1.2.3/linux-x86_64-static/qlab-remote" as VerifiedRemoteHelperPath,
    };
    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");
    await master.installVerifiedHelper(verifiedInstall());

    await master.openAgent();

    expect(runtime.opens.at(-1)?.argv.at(-1)).toBe(
      `'/home/al'"'"'ice/.qlab/bin/1.2.3/linux-x86_64-static/qlab-remote' 'agent'`,
    );
  });

  it("binds at most one verified helper install while installation is in flight", async () => {
    const runtime = new FakeSshRuntime();
    let release!: () => void;
    runtime.installBarrier = new Promise<void>((resolve) => { release = resolve; });
    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");

    const first = master.installVerifiedHelper(verifiedInstall());
    await expect(master.installVerifiedHelper(verifiedInstall()))
      .rejects.toThrow(/already.*install|in progress/i);
    expect(runtime.installCalls).toHaveLength(1);
    release();
    await expect(first).resolves.toMatchObject({ helperVersion: "1.2.3" });
  });

  it("uses one fixed platform probe and rejects malformed probe output", async () => {
    const runtime = new FakeSshRuntime();
    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");
    const probe = master.probeRemotePlatform();
    await Promise.resolve();
    const process = runtime.lastProcess();
    process.emitText("Linux\nx86_64\n6.8.0\n");
    process.exit(0);

    await expect(probe).resolves.toEqual({ os: "linux", arch: "x86_64", kernel: "6.8.0" });
    expect(runtime.opens.at(-1)?.argv).toEqual([
      "/usr/bin/ssh", "-T", "-S", master.controlPath, "-o", "BatchMode=yes", "--",
      "qlab-gpu", REMOTE_PLATFORM_PROBE_SCRIPT,
    ]);

    const badRuntime = new FakeSshRuntime();
    const badMaster = await new SshTargetTransport(badRuntime).connect("qlab-gpu");
    const badProbe = badMaster.probeRemotePlatform();
    await Promise.resolve();
    badRuntime.lastProcess().emitText("Linux\nx86_64\n6.8.0\nextra\n");
    badRuntime.lastProcess().exit(0);
    await expect(badProbe).rejects.toThrow(/platform probe/i);

    const overflowRuntime = new FakeSshRuntime();
    const overflowMaster = await new SshTargetTransport(overflowRuntime).connect("qlab-gpu");
    const overflowProbe = overflowMaster.probeRemotePlatform();
    await Promise.resolve();
    overflowRuntime.lastProcess().emitText("Linux\nx86_64\n6.8.0\n");
    overflowRuntime.lastProcess().emitText("x".repeat(300_000));
    overflowRuntime.lastProcess().exit(0);
    await expect(overflowProbe).rejects.toThrow(/platform probe/i);
  });

  it("replays a channel exit that races publication and rejects a master already exited at readiness", async () => {
    const runtime = new FakeSshRuntime();
    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");
    await master.installVerifiedHelper(verifiedInstall());
    runtime.exitNextPipe = { exitCode: 7, signal: null };
    const channel = await master.openAgent();
    const exits: unknown[] = [];

    channel.onExit((exit) => exits.push(exit));

    expect(exits).toEqual([{ code: 7, signal: null, reason: "SSH channel exited" }]);
    await expect(channel.write(Uint8Array.of(1))).rejects.toThrow(/closed/i);

    const exited = new FakeSshRuntime();
    exited.exitMasterOnOpen = { exitCode: 255, signal: null };
    await expect(new SshTargetTransport(exited).connect("qlab-gpu"))
      .rejects.toThrow(/master.*exit/i);
  });

  it("fans natural master loss out once, fences old writes, and advances generation", async () => {
    const runtime = new FakeSshRuntime();
    const transport = new SshTargetTransport(runtime);
    const master = await transport.connect("qlab-gpu");
    await master.installVerifiedHelper(verifiedInstall());
    const agent = await master.openAgent();
    const browse = await master.openBrowse();
    const exits: unknown[] = [];
    const losses: unknown[] = [];
    agent.onExit((exit) => exits.push(["agent", exit]));
    browse.onExit((exit) => exits.push(["browse", exit]));
    master.onLost((loss) => losses.push(loss));

    runtime.killMaster(255, "connection reset");
    runtime.master().exit(255);

    expect(exits).toEqual([
      ["agent", expect.objectContaining({ code: 255, reason: "connection reset" })],
      ["browse", expect.objectContaining({ code: 255, reason: "connection reset" })],
    ]);
    expect(losses).toHaveLength(1);
    await expect(agent.write(Uint8Array.of(1))).rejects.toThrow(/lost|closed/i);
    await expect(master.openAgent()).rejects.toThrow(/lost|closed/i);
    const next = await transport.connect("qlab-gpu");
    expect(next.generation).toBe(master.generation + 1);
    expect(runtime.opens.some((open) => open.argv.includes("-O"))).toBe(false);
  });

  it("fans loss out even when one channel listener throws", async () => {
    const runtime = new FakeSshRuntime();
    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");
    await master.installVerifiedHelper(verifiedInstall());
    const first = await master.openAgent();
    const second = await master.openBrowse();
    const exits: unknown[] = [];
    first.onExit(() => { throw new Error("consumer failed"); });
    second.onExit((exit) => exits.push(exit));

    expect(() => runtime.killMaster(255, "connection reset")).not.toThrow();
    expect(exits).toEqual([expect.objectContaining({ code: 255 })]);
  });

  it("closes idempotently in order and asks the live master to exit before private cleanup", async () => {
    const runtime = new FakeSshRuntime();
    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");
    await master.installVerifiedHelper(verifiedInstall());
    const channel = await master.openAgent();

    const first = master.close();
    for (let index = 0; index < 4; index++) await Promise.resolve();
    const control = runtime.lastProcess();
    expect(runtime.opens.at(-1)?.argv).toEqual([
      "/usr/bin/ssh", "-S", master.controlPath, "-O", "exit", "--", "qlab-gpu",
    ]);
    control.exit(0);
    runtime.master().exit(0);
    await first;
    await master.close();

    expect(runtime.opens.filter((open) => open.argv.includes("-O"))).toHaveLength(1);
    expect(runtime.removed.slice(-3)).toEqual([
      "/private/ssh-master-1/master.sock",
      "/private/ssh-master-1/master.log",
      "/private/ssh-master-1",
    ]);
    await expect(channel.write(Uint8Array.of(1))).rejects.toThrow(/closed/i);
  });

  it("bounds the control-exit wait and terminates a master that does not exit on request", async () => {
    const runtime = new FakeSshRuntime();
    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");

    const closing = master.close();
    for (let index = 0; index < 6; index++) await Promise.resolve();
    const control = runtime.lastProcess();
    expect(control).not.toBe(runtime.master());
    expect(runtime.waitCalls).toBeGreaterThan(0);
    await closing;

    expect(runtime.master().closeCount).toBe(1);
    expect(runtime.removed).toContain("/private/ssh-master-1");
  });

  it("owns the fixed host-key acceptance PTY and cancellation closes only that process", async () => {
    const runtime = new FakeSshRuntime();
    const transport = new SshTargetTransport(runtime);
    const setup = await transport.openHostKeyAcceptance("qlab-gpu");

    expect(runtime.opens[0]).toEqual({ kind: "pty", argv: [
      "/usr/bin/ssh", "-tt", "-o", "BatchMode=no", "-o", "ControlMaster=no",
      "--", "qlab-gpu", "/bin/true",
    ] });
    const output: string[] = [];
    setup.onBytes((bytes) => output.push(new TextDecoder().decode(bytes)));
    runtime.lastProcess().emitText("The authenticity of host cannot be established");
    await setup.write(new TextEncoder().encode("yes\n"));
    setup.resize(30, 100);
    await setup.close();

    expect(output.join("")).toContain("authenticity");
    expect(runtime.lastProcess().writes).toEqual([new TextEncoder().encode("yes\n")]);
    expect(runtime.lastProcess().resizes).toEqual([[30, 100]]);
    expect(runtime.lastProcess().closeCount).toBe(1);
    expect(runtime.opens).toHaveLength(1);
  });
});
