import { describe, expect, it } from "vitest";

import {
  NativeBridgeOpenSshProfileRuntime,
  OpenSshProfileProvider,
  type OpenSshProfileRuntime,
  type OpenSshRunResult,
} from "../src/openssh-profiles";
import type { NativeProcessExit, NativePtyProcessSession } from "../src/native-bridge";

function normalize(path: string): string {
  const absolute = path.startsWith("/") ? path : `/${path}`;
  const parts: string[] = [];
  for (const part of absolute.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") parts.pop();
    else parts.push(part);
  }
  return `/${parts.join("/")}`;
}

function globPattern(pattern: string): RegExp {
  const escaped = pattern.replace(/[.+^${}()|[\]\\]/g, "\\$&");
  return new RegExp(`^${escaped.replaceAll("*", "[^/]*").replaceAll("?", "[^/]")}$`);
}

class MemoryOpenSshRuntime implements OpenSshProfileRuntime {
  readonly homeDirectory = "/home/alice";
  readonly files = new Map<string, string>();
  readonly results = new Map<string, OpenSshRunResult>();
  readonly runs: string[][] = [];
  readonly canonicalAliases = new Map<string, string>();

  write(path: string, contents: string): void {
    this.files.set(normalize(path.replace(/^~/, this.homeDirectory)), contents);
  }

  sshG(alias: string, stdout: string, exitCode = 0, stderr = ""): void {
    this.results.set(alias, { exitCode, stdout, stderr });
  }

  async readTextFile(path: string): Promise<string | null> {
    return this.files.get(normalize(path)) ?? null;
  }

  async canonicalizePath(path: string): Promise<string> {
    const normalized = normalize(path);
    return this.canonicalAliases.get(normalized) ?? normalized;
  }

  async expandGlob(pattern: string): Promise<readonly string[]> {
    const matcher = globPattern(normalize(pattern));
    return [...this.files.keys()].filter((path) => matcher.test(path)).reverse();
  }

  async run(argv: readonly string[]): Promise<OpenSshRunResult> {
    this.runs.push([...argv]);
    return this.results.get(argv.at(-1) || "") ?? {
      exitCode: 255,
      stdout: "",
      stderr: "missing fake ssh -G result",
    };
  }
}

describe("OpenSshProfileProvider", () => {
  it("discovers literal aliases through Include and lets ssh -G resolve them", async () => {
    const runtime = new MemoryOpenSshRuntime();
    runtime.write("~/.ssh/config", "Include conf.d/*.conf conf.d/cycle.conf\nHost *.wild\n  User ignored\n");
    runtime.write("~/.ssh/conf.d/a.conf", "Include nested/*.conf\nHost qlab-gpu qlab-gpu\n");
    runtime.write("~/.ssh/nested/profile.conf", "Host qlab-arm\n");
    runtime.write("~/.ssh/conf.d/cycle.conf", "Include conf.d/cycle.conf\nHost qlab-gpu\n");
    runtime.sshG("qlab-gpu", [
      "hostname 10.0.0.8",
      "user alice",
      "port 22",
      "identityfile ~/.ssh/id_ed25519",
      "identityfile ~/.ssh/id_backup",
      "proxyjump bastion",
      "proxycommand none",
      "",
    ].join("\n"));
    const provider = new OpenSshProfileProvider(runtime);

    expect((await provider.listConcreteAliases()).map((profile) => profile.alias))
      .toEqual(["qlab-arm", "qlab-gpu"]);
    await expect(provider.resolve("qlab-gpu")).resolves.toMatchObject({
      alias: "qlab-gpu",
      hostname: "10.0.0.8",
      user: "alice",
      port: 22,
      identityFiles: ["~/.ssh/id_ed25519", "~/.ssh/id_backup"],
      proxyJump: "bastion",
      proxyCommand: null,
    });
    expect(runtime.runs).toEqual([["/usr/bin/ssh", "-G", "--", "qlab-gpu"]]);
  });

  it("expands tilde and relative Include globs lexically while preserving first-seen aliases", async () => {
    const runtime = new MemoryOpenSshRuntime();
    runtime.write("~/.ssh/config", [
      "Include ~/.ssh/extra/*.conf",
      "Include conf.d/*.conf",
      "Host !negated bracket[0-9] question? star* repeated plain",
      "Host repeated final",
      "",
    ].join("\n"));
    runtime.write("~/.ssh/extra/z.conf", "Host zed\n");
    runtime.write("~/.ssh/extra/a.conf", "Host alpha\n");
    runtime.write("~/.ssh/conf.d/b.conf", "Host beta\n");
    runtime.write("~/.ssh/conf.d/a.conf", "Host alpha gamma\n");

    const aliases = await new OpenSshProfileProvider(runtime).listConcreteAliases();

    expect(aliases.map((profile) => profile.alias)).toEqual([
      "alpha", "zed", "gamma", "beta", "repeated", "plain", "final",
    ]);
  });

  it("parses OpenSSH Keyword=value and spaced equals forms without publishing equals as an alias", async () => {
    const runtime = new MemoryOpenSshRuntime();
    runtime.write("~/.ssh/config", "Include=conf.d/*.conf\nHost = direct\n");
    runtime.write("~/.ssh/conf.d/a.conf", "Host=included\n");

    expect((await new OpenSshProfileProvider(runtime).listConcreteAliases()).map((x) => x.alias))
      .toEqual(["included", "direct"]);
  });

  it("breaks canonical-file cycles and rejects Include trees beyond the depth cap", async () => {
    const runtime = new MemoryOpenSshRuntime();
    runtime.write("~/.ssh/config", "Include link.conf real.conf\nHost root\n");
    runtime.write("~/.ssh/link.conf", "Host from-link\n");
    runtime.write("~/.ssh/real.conf", "Include config\nHost from-real\n");
    runtime.canonicalAliases.set("/home/alice/.ssh/link.conf", "/home/alice/.ssh/real.conf");

    expect((await new OpenSshProfileProvider(runtime).listConcreteAliases()).map((x) => x.alias))
      .toEqual(["from-link", "root"]);

    const deep = new MemoryOpenSshRuntime();
    deep.write("~/.ssh/config", "Include depth-0.conf\n");
    for (let index = 0; index < 18; index++) {
      deep.write(`~/.ssh/depth-${index}.conf`, `Include depth-${index + 1}.conf\nHost h-${index}\n`);
    }
    deep.write("~/.ssh/depth-18.conf", "Host too-deep\n");
    await expect(new OpenSshProfileProvider(deep).listConcreteAliases())
      .rejects.toThrow(/Include depth/i);
  });

  it("rejects undiscovered or non-literal aliases before spawning ssh", async () => {
    const runtime = new MemoryOpenSshRuntime();
    runtime.write("~/.ssh/config", "Host qlab-gpu\n");
    const provider = new OpenSshProfileProvider(runtime);

    await expect(provider.resolve("missing")).rejects.toThrow(/concrete OpenSSH alias/i);
    await expect(provider.resolve("bad alias")).rejects.toThrow(/concrete OpenSSH alias/i);
    expect(runtime.runs).toEqual([]);
  });

  it("fails closed when ssh -G fails or omits required effective settings", async () => {
    const runtime = new MemoryOpenSshRuntime();
    runtime.write("~/.ssh/config", "Host qlab-gpu broken\n");
    runtime.sshG("qlab-gpu", "", 255, "Bad configuration option");
    runtime.sshG("broken", "hostname host\nuser alice\n");
    const provider = new OpenSshProfileProvider(runtime);

    await expect(provider.resolve("qlab-gpu")).rejects.toThrow(/ssh -G.*Bad configuration option/i);
    await expect(provider.resolve("broken")).rejects.toThrow(/effective port/i);
  });

  it("runs ssh -G through the structured NativeBridge production adapter", async () => {
    const opens: string[][] = [];
    const bridge = {
      async openPtyProcess(options: { argv: readonly string[] }): Promise<NativePtyProcessSession> {
        opens.push([...options.argv]);
        const bytesListeners: Array<(bytes: Uint8Array) => void> = [];
        const exitListeners: Array<(exit: NativeProcessExit) => void> = [];
        setTimeout(() => {
          for (const listener of bytesListeners) listener(new TextEncoder().encode("hostname host\n"));
          for (const listener of exitListeners) listener({ exitCode: 0, signal: null });
        }, 0);
        return {
          sessionId: "ssh-g",
          async write() {},
          onBytes(listener) { bytesListeners.push(listener); return () => {}; },
          onExit(listener) { exitListeners.push(listener); return () => {}; },
          resize() {},
          async close() {},
        };
      },
    };
    const runtime = new NativeBridgeOpenSshProfileRuntime(bridge, "/home/alice");

    await expect(runtime.run(["/usr/bin/ssh", "-G", "--", "qlab-gpu"]))
      .resolves.toMatchObject({ exitCode: 0, stdout: "hostname host\n" });
    expect(opens).toEqual([["/usr/bin/ssh", "-G", "--", "qlab-gpu"]]);
  });
});
