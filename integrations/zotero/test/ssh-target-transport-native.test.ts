import { execFile } from "node:child_process";
import { createHash, createHmac, randomBytes } from "node:crypto";
import { appendFile, chmod, lstat, mkdir, mkdtemp, open, readFile, rm, writeFile } from "node:fs/promises";
import { createConnection, type Socket } from "node:net";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { promisify } from "node:util";
import { afterEach, expect, it } from "vitest";

import {
  NativeBridge,
  ServerWebSocketFrameDecoder,
  encodeClientWebSocketFrame,
  nativeWebSocketUpgradeRequest,
  validateNativeWebSocketUpgrade,
} from "../src/native-bridge";
import type { ResolvedOpenSshProfile } from "../src/openssh-profiles";
import {
  NativeBridgeSshTransportRuntime,
  SshTargetTransport,
  type InstalledHelper,
  type SshTransportFiles,
  type VerifiedHelperInstall,
  type VerifiedRemoteHelperPath,
} from "../src/ssh-target-transport";

const execFileAsync = promisify(execFile);
const TOKEN = "native-transport-test-token-0123456789";
const FINGERPRINT = "SHA256:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";
const roots: string[] = [];

afterEach(async () => {
  await Promise.all(roots.splice(0).map((path) => rm(path, { recursive: true, force: true })));
});

class NodeWebSocketClient {
  private readonly decoder = new ServerWebSocketFrameDecoder();
  private socket!: Socket;
  private upgraded = false;
  private handshake = Buffer.alloc(0);
  private readonly key = randomBytes(16).toString("base64");
  private readonly expectedAccept = createHash("sha1")
    .update(this.key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").digest("base64");
  private readonly serverProof = createHmac("sha1", TOKEN)
    .update(`server:${this.key}`).digest("base64");
  private onJson: (value: string) => void = () => {};

  async connect(path: string): Promise<void> {
    this.socket = createConnection(path);
    await new Promise<void>((resolveReady, reject) => {
      this.socket.once("error", reject);
      this.socket.once("connect", () => {
        const clientProof = createHmac("sha1", TOKEN)
          .update(`client:${this.key}`).digest("base64");
        this.socket.write(nativeWebSocketUpgradeRequest(this.key, clientProof));
      });
      this.socket.on("data", (chunk) => {
        try {
          if (!this.upgraded) {
            this.handshake = Buffer.concat([this.handshake, chunk]);
            const end = this.handshake.indexOf("\r\n\r\n");
            if (end < 0) return;
            validateNativeWebSocketUpgrade(
              this.handshake.subarray(0, end + 4).toString(),
              this.expectedAccept,
              this.serverProof,
            );
            this.upgraded = true;
            const remainder = this.handshake.subarray(end + 4);
            this.handshake = Buffer.alloc(0);
            if (remainder.length) this.receiveFrames(remainder);
            resolveReady();
            return;
          }
          this.receiveFrames(chunk);
        }
        catch (error) { reject(error); }
      });
    });
  }

  attach(bridge: NativeBridge): void {
    this.onJson = (value) => (bridge as any).onMessage(value);
    (bridge as any).socket = {
      readyState: 1,
      send: (value: string) => this.sendJson(value),
    };
  }

  close(): void { this.socket.destroy(); }

  private sendJson(value: string): void {
    const frame = encodeClientWebSocketFrame(
      1,
      new TextEncoder().encode(value),
      Uint8Array.from(randomBytes(4)),
    );
    this.socket.write(frame);
  }

  private receiveFrames(chunk: Uint8Array): void {
    for (const frame of this.decoder.push(chunk)) {
      if (frame.opcode === 1) this.onJson(new TextDecoder().decode(frame.payload));
    }
  }
}

class NodeTransportFiles implements SshTransportFiles {
  readonly removed: string[] = [];
  constructor(private readonly root: string, private readonly auditPath: string) {}

  async createPrivateDirectory(): Promise<string> {
    const path = await mkdtemp(join(this.root, "master-"));
    await chmod(path, 0o700);
    return path;
  }
  async createRegularFileNoFollow(path: string, mode: 0o600): Promise<void> {
    const handle = await open(path, "wx", mode);
    await handle.close();
  }
  async inspectPath(path: string) {
    try {
      const stat = await lstat(path);
      const kind = stat.isSymbolicLink() ? "symlink" as const
        : stat.isDirectory() ? "directory" as const
          : stat.isFile() ? "file" as const : "socket" as const;
      return { kind, mode: stat.mode & 0o777 };
    }
    catch { return null; }
  }
  async readTextFileBounded(path: string, maxBytes: number): Promise<string> {
    const bytes = await readFile(path);
    if (bytes.length > maxBytes) throw new Error("bounded file exceeded");
    return bytes.toString();
  }
  async isSocket(path: string): Promise<boolean> {
    try { return (await lstat(path)).isSocket(); }
    catch { return false; }
  }
  async removeFile(path: string): Promise<void> {
    this.removed.push(path);
    await appendFile(this.auditPath, `${JSON.stringify({ event: "remove", path })}\n`);
    await rm(path, { force: true });
  }
  async removePrivateDirectory(path: string): Promise<void> {
    this.removed.push(path);
    await appendFile(this.auditPath, `${JSON.stringify({ event: "remove", path })}\n`);
    await rm(path, { recursive: true, force: true });
  }
}

async function waitForPath(path: string): Promise<void> {
  for (let attempt = 0; attempt < 100; attempt++) {
    try { await lstat(path); return; }
    catch { await new Promise((resolveWait) => setTimeout(resolveWait, 10)); }
  }
  throw new Error(`Timed out waiting for ${path}`);
}

it("runs the production adapter through NativeBridge and the native helper into a fake SSH", async () => {
  const root = await mkdtemp(join(tmpdir(), "qlab-native-ssh-"));
  roots.push(root);
  await chmod(root, 0o700);
  const auditPath = join(root, "ssh-audit.jsonl");
  const fakeSsh = join(root, "fake-ssh.mjs");
  const helper = join(root, "zoterochat-helper");
  const socketPath = join(root, "bridge.sock");
  const tokenPath = join(root, "token");
  const nativeSource = resolve("native/src/zoterochat_helper.c");
  await writeFile(fakeSsh, `#!/usr/bin/env node
import { appendFileSync, readFileSync, unlinkSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { spawnSync } from "node:child_process";
const audit = ${JSON.stringify(auditPath)};
const args = process.argv.slice(2);
const record = (value) => appendFileSync(audit, JSON.stringify(value) + "\\n");
record({ event: "argv", args });
if (args.includes("-MN")) {
  const log = args[args.indexOf("-E") + 1];
  const control = args.find((value) => value.startsWith("ControlPath=")).slice(12);
  writeFileSync(log, "debug1: Server host key: ssh-ed25519 ${FINGERPRINT}\\n");
  writeFileSync(control + ".pid", String(process.pid));
  const server = createServer(() => {});
  server.listen(control);
  const finish = () => { record({ event: "master-exit" }); server.close(() => process.exit(0)); };
  process.on("SIGTERM", finish);
  process.on("SIGHUP", finish);
} else if (args.includes("-O") && args[args.indexOf("-O") + 1] === "exit") {
  const control = args[args.indexOf("-S") + 1];
  process.kill(Number(readFileSync(control + ".pid", "utf8")), "SIGTERM");
  record({ event: "control-exit" });
} else if (args.at(-1) === "uname -s; uname -m; uname -r") {
  process.stdout.write("Linux\\nx86_64\\n6.8.0-test\\n");
} else if (args[0] === "-tt") {
  const stty = spawnSync("/bin/stty", ["-a"], { encoding: "utf8", stdio: [0, "pipe", "pipe"] });
  record({ event: "setup-termios", value: stty.stdout, error: stty.stderr, status: stty.status });
  process.stdout.write("setup-ready\\n");
} else {
  process.exitCode = 2;
}
`);
  await chmod(fakeSsh, 0o700);
  await execFileAsync("cc", [
    "-O2", "-std=c17", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
    `-DZOTEROCHAT_TEST_SSH_EXECUTABLE=\"${fakeSsh}\"`, nativeSource, "-lutil", "-o", helper,
  ]);
  await writeFile(tokenPath, TOKEN + "\n", { mode: 0o600 });
  const daemon = (await import("node:child_process")).spawn(helper, [
    "--socket", socketPath, "--token-file", tokenPath,
  ], { stdio: ["ignore", "ignore", "pipe"] });
  try {
    await waitForPath(socketPath);
    const client = new NodeWebSocketClient();
    await client.connect(socketPath);
    const bridge = new NativeBridge("file:///unused/", "test");
    client.attach(bridge);
    const files = new NodeTransportFiles(root, auditPath);
    const installed: InstalledHelper = Object.freeze({
      helperVersion: "1.2.3",
      tuple: "linux-x86_64-static",
      executableSha256: "c".repeat(64),
      absoluteVersionedPath: "/home/alice/.qlab/bin/1.2.3/linux-x86_64-static/qlab-remote" as VerifiedRemoteHelperPath,
    });
    const profile: ResolvedOpenSshProfile = {
      alias: "qlab-gpu", hostname: "10.0.0.8", user: "alice", port: 22,
      identityFiles: [], proxyJump: null, proxyCommand: null, effectiveConfig: Object.freeze({}),
    };
    const runtime = new NativeBridgeSshTransportRuntime({
      profiles: { resolve: async () => profile }, bridge, files,
      installVerifiedHelper: async (_input: VerifiedHelperInstall) => installed,
    });
    const master = await new SshTargetTransport(runtime).connect("qlab-gpu");
    expect(master.acceptedHostKeyFingerprint).toBe(FINGERPRINT);
    expect(await master.probeRemotePlatform()).toEqual({
      os: "linux", arch: "x86_64", kernel: "6.8.0-test",
    });
    await master.installVerifiedHelper({
      manifest: {
        helperVersion: "1.2.3", tuple: "linux-x86_64-static",
        archiveSha256: "b".repeat(64), executableSha256: "c".repeat(64),
      },
      artifact: Uint8Array.of(1) as VerifiedHelperInstall["artifact"],
    });
    const setup = await master.openSetupAuth();
    await new Promise<void>((resolveExit) => setup.onExit(() => resolveExit()));
    await master.close();
    client.close();

    const events = (await readFile(auditPath, "utf8")).trim().split("\n").map((line) => JSON.parse(line));
    const argv = events.filter((event) => event.event === "argv").map((event) => event.args);
    expect(argv[0]).toEqual([
      "-v", "-E", expect.stringMatching(/\/master-[^/]+\/master\.log$/), "-MN",
      "-o", "FingerprintHash=sha256", "-o", "ControlMaster=yes", "-o", "ControlPersist=600",
      "-o", "BatchMode=yes", "-o", expect.stringMatching(/^ControlPath=.*\/master\.sock$/),
      "--", "qlab-gpu",
    ]);
    expect(argv[1]).toEqual([
      "-T", "-S", master.controlPath, "-o", "BatchMode=yes", "--", "qlab-gpu",
      "uname -s; uname -m; uname -r",
    ]);
    expect(argv[2]).toEqual([
      "-tt", "-S", master.controlPath, "-o", "BatchMode=yes", "--", "qlab-gpu",
      "'/home/alice/.qlab/bin/1.2.3/linux-x86_64-static/qlab-remote' 'setup' 'codex-device-auth'",
    ]);
    const termiosEvent = events.find((event) => event.event === "setup-termios");
    expect(termiosEvent).toMatchObject({ status: 0 });
    const termios = termiosEvent?.value || "";
    expect(termios).toMatch(/(?:^|\s)-icanon(?:\s|$)/);
    expect(termios).toMatch(/(?:^|\s)-echo(?:\s|$)/);
    expect(termios).toMatch(/(?:^|\s)-opost(?:\s|$)/);
    expect(events.findIndex((event) => event.event === "master-exit"))
      .toBeLessThan(events.findIndex((event) => event.event === "remove" && event.path.endsWith("master.log")));
  }
  finally {
    daemon.kill("SIGKILL");
    await new Promise<void>((resolveExit) => daemon.once("exit", () => resolveExit()));
  }
}, 20_000);
