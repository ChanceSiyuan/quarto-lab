export type OpenSshProfile = Readonly<{ alias: string }>;

export type OpenSshRunResult = Readonly<{
  exitCode: number | null;
  stdout: string;
  stderr: string;
}>;

export interface OpenSshProfileRuntime {
  readonly homeDirectory: string;
  readTextFile(path: string): Promise<string | null>;
  canonicalizePath(path: string): Promise<string>;
  expandGlob(pattern: string): Promise<readonly string[]>;
  run(argv: readonly string[]): Promise<OpenSshRunResult>;
}

export type ResolvedOpenSshProfile = Readonly<{
  alias: string;
  hostname: string;
  user: string;
  port: number;
  identityFiles: readonly string[];
  proxyJump: string | null;
  proxyCommand: string | null;
  effectiveConfig: Readonly<Record<string, readonly string[]>>;
}>;

const MAX_INCLUDE_DEPTH = 16;
const SSH_EXECUTABLE = "/usr/bin/ssh";

function normalizeAbsolutePath(path: string): string {
  if (!path.startsWith("/")) throw new Error("OpenSSH configuration path must be absolute");
  const parts: string[] = [];
  for (const part of path.split("/")) {
    if (!part || part === ".") continue;
    if (part === "..") parts.pop();
    else parts.push(part);
  }
  return `/${parts.join("/")}`;
}

function joinAbsolute(base: string, path: string): string {
  return normalizeAbsolutePath(path.startsWith("/") ? path : `${base}/${path}`);
}

function configTokens(line: string): string[] {
  const tokens: string[] = [];
  let current = "";
  let quote: "'" | "\"" | null = null;
  let escaped = false;
  const flush = () => {
    if (current) tokens.push(current);
    current = "";
  };
  for (const character of line) {
    if (escaped) {
      current += character;
      escaped = false;
      continue;
    }
    if (character === "\\" && quote !== "'") {
      escaped = true;
      continue;
    }
    if (quote) {
      if (character === quote) quote = null;
      else current += character;
      continue;
    }
    if (character === "'" || character === "\"") {
      quote = character;
      continue;
    }
    if (character === "#") break;
    if (/\s/u.test(character)) flush();
    else current += character;
  }
  if (escaped) current += "\\";
  flush();
  return tokens;
}

function configDirective(tokens: readonly string[]): Readonly<{
  keyword: string;
  values: readonly string[];
}> | null {
  const first = tokens[0];
  if (!first) return null;
  const equals = first.indexOf("=");
  if (equals >= 0) {
    const inline = first.slice(equals + 1);
    return {
      keyword: first.slice(0, equals).toLowerCase(),
      values: inline ? [inline, ...tokens.slice(1)] : tokens.slice(1),
    };
  }
  return {
    keyword: first.toLowerCase(),
    values: tokens[1] === "=" ? tokens.slice(2) : tokens.slice(1),
  };
}

function concreteAlias(value: string): boolean {
  return Boolean(value) && !/[\s*?!\[\]]/u.test(value);
}

function freezeConfig(values: Map<string, string[]>): Readonly<Record<string, readonly string[]>> {
  const result: Record<string, readonly string[]> = {};
  for (const [key, entries] of values) result[key] = Object.freeze([...entries]);
  return Object.freeze(result);
}

export class OpenSshProfileProvider {
  private readonly sshDirectory: string;

  constructor(private readonly runtime: OpenSshProfileRuntime) {
    if (!runtime.homeDirectory.startsWith("/")) {
      throw new Error("OpenSSH home directory must be absolute");
    }
    this.sshDirectory = joinAbsolute(runtime.homeDirectory, ".ssh");
  }

  async listConcreteAliases(): Promise<OpenSshProfile[]> {
    const aliases: string[] = [];
    const seenAliases = new Set<string>();
    const seenFiles = new Set<string>();
    await this.readConfigurationFile(
      joinAbsolute(this.sshDirectory, "config"),
      0,
      seenFiles,
      (alias) => {
        if (!seenAliases.has(alias)) {
          seenAliases.add(alias);
          aliases.push(alias);
        }
      },
    );
    return aliases.map((alias) => Object.freeze({ alias }));
  }

  async resolve(alias: string): Promise<ResolvedOpenSshProfile> {
    if (!concreteAlias(alias)) throw new Error("Not a concrete OpenSSH alias");
    const aliases = await this.listConcreteAliases();
    if (!aliases.some((profile) => profile.alias === alias)) {
      throw new Error(`Not a discovered concrete OpenSSH alias: ${alias}`);
    }
    const result = await this.runtime.run([SSH_EXECUTABLE, "-G", "--", alias]);
    if (result.exitCode !== 0) {
      const detail = result.stderr.trim();
      throw new Error(`ssh -G failed for ${alias}${detail ? `: ${detail}` : ""}`);
    }
    const values = new Map<string, string[]>();
    for (const line of result.stdout.split(/\r?\n/u)) {
      if (!line) continue;
      const separator = line.search(/\s/u);
      if (separator < 1) continue;
      const key = line.slice(0, separator).toLowerCase();
      const value = line.slice(separator).trimStart();
      if (!value) continue;
      const entries = values.get(key) || [];
      entries.push(value);
      values.set(key, entries);
    }
    const hostname = values.get("hostname")?.[0];
    const user = values.get("user")?.[0];
    const portText = values.get("port")?.[0];
    if (!hostname) throw new Error("ssh -G omitted the effective hostname");
    if (!user) throw new Error("ssh -G omitted the effective user");
    if (!portText || !/^\d+$/u.test(portText)) {
      throw new Error("ssh -G omitted the effective port");
    }
    const port = Number(portText);
    if (!Number.isSafeInteger(port) || port < 1 || port > 65535) {
      throw new Error("ssh -G returned an invalid effective port");
    }
    const proxyJump = values.get("proxyjump")?.[0];
    const proxyCommand = values.get("proxycommand")?.[0];
    return Object.freeze({
      alias,
      hostname,
      user,
      port,
      identityFiles: Object.freeze([...(values.get("identityfile") || [])]),
      proxyJump: proxyJump && proxyJump.toLowerCase() !== "none" ? proxyJump : null,
      proxyCommand: proxyCommand && proxyCommand.toLowerCase() !== "none" ? proxyCommand : null,
      effectiveConfig: freezeConfig(values),
    });
  }

  private async readConfigurationFile(
    requestedPath: string,
    depth: number,
    seenFiles: Set<string>,
    addAlias: (alias: string) => void,
  ): Promise<void> {
    if (depth > MAX_INCLUDE_DEPTH) throw new Error(`OpenSSH Include depth exceeds ${MAX_INCLUDE_DEPTH}`);
    const path = normalizeAbsolutePath(requestedPath);
    const source = await this.runtime.readTextFile(path);
    if (source === null) return;
    const canonical = await this.runtime.canonicalizePath(path);
    if (seenFiles.has(canonical)) return;
    seenFiles.add(canonical);

    for (const line of source.split(/\r?\n/u)) {
      const tokens = configTokens(line);
      const directive = configDirective(tokens);
      if (directive?.keyword === "include") {
        for (const include of directive.values) {
          const expanded = include === "~"
            ? this.runtime.homeDirectory
            : include.startsWith("~/")
              ? joinAbsolute(this.runtime.homeDirectory, include.slice(2))
              : joinAbsolute(this.sshDirectory, include);
          const matches = [...await this.runtime.expandGlob(expanded)].sort((left, right) =>
            left < right ? -1 : left > right ? 1 : 0
          );
          for (const match of matches) {
            await this.readConfigurationFile(match, depth + 1, seenFiles, addAlias);
          }
        }
      }
      else if (directive?.keyword === "host") {
        for (const alias of directive.values) if (concreteAlias(alias)) addAlias(alias);
      }
    }
  }
}

const MAX_SSH_G_OUTPUT = 1024 * 1024;

function globSegmentPattern(segment: string): RegExp {
  let source = "^";
  for (let index = 0; index < segment.length; index++) {
    const character = segment[index]!;
    if (character === "*") source += "[^/]*";
    else if (character === "?") source += "[^/]";
    else if (character === "[") {
      const end = segment.indexOf("]", index + 1);
      if (end > index + 1) {
        const content = segment.slice(index + 1, end).replace(/^!/u, "^");
        source += `[${content.replace(/\\/gu, "\\\\")}]`;
        index = end;
      }
      else source += "\\[";
    }
    else source += character.replace(/[\\^$.*+?()[\]{}|]/gu, "\\$&");
  }
  return new RegExp(`${source}$`, "u");
}

function defaultHomeDirectory(): string {
  return Services.dirsvc.get("Home", Ci.nsIFile).path;
}

/** Production OpenSSH profile runtime backed by Gecko files and NativeBridge processes. */
export class NativeBridgeOpenSshProfileRuntime implements OpenSshProfileRuntime {
  readonly homeDirectory: string;

  constructor(
    private readonly bridge: Pick<NativeBridge, "openPtyProcess">,
    homeDirectory = defaultHomeDirectory(),
  ) {
    this.homeDirectory = normalizeAbsolutePath(homeDirectory);
  }

  async readTextFile(path: string): Promise<string | null> {
    if (!await IOUtils.exists(path)) return null;
    return IOUtils.readUTF8(path);
  }

  async canonicalizePath(path: string): Promise<string> {
    const file = makeLocalFile(path);
    file.normalize();
    return file.path;
  }

  async expandGlob(pattern: string): Promise<readonly string[]> {
    const parts = normalizeAbsolutePath(pattern).split("/").filter(Boolean);
    let candidates = ["/"];
    for (const part of parts) {
      const magic = /[*?[]/u.test(part);
      const next: string[] = [];
      for (const parent of candidates) {
        if (!magic) {
          next.push(joinAbsolute(parent, part));
          continue;
        }
        if (!await IOUtils.exists(parent)) continue;
        const matcher = globSegmentPattern(part);
        for (const child of await IOUtils.getChildren(parent)) {
          const name = child.slice(child.lastIndexOf("/") + 1);
          if (matcher.test(name)) next.push(child);
        }
      }
      candidates = next;
    }
    const existing: string[] = [];
    for (const candidate of candidates) if (await IOUtils.exists(candidate)) existing.push(candidate);
    return existing.sort((left, right) => left < right ? -1 : left > right ? 1 : 0);
  }

  async run(argv: readonly string[]): Promise<OpenSshRunResult> {
    const process = await this.bridge.openPtyProcess({ argv, cwd: this.homeDirectory });
    const chunks: Uint8Array[] = [];
    let size = 0;
    let overflowed = false;
    process.onBytes((bytes) => {
      if (size + bytes.length > MAX_SSH_G_OUTPUT) {
        overflowed = true;
        return;
      }
      chunks.push(bytes.slice());
      size += bytes.length;
    });
    const exit = await new Promise<NativeProcessExit>((resolve) => process.onExit(resolve));
    if (overflowed) throw new Error("ssh -G output exceeded 1 MiB");
    const output = new Uint8Array(size);
    let offset = 0;
    for (const chunk of chunks) {
      output.set(chunk, offset);
      offset += chunk.length;
    }
    const text = new TextDecoder().decode(output).replaceAll("\r\n", "\n");
    return exit.exitCode === 0 && exit.signal === null
      ? { exitCode: 0, stdout: text, stderr: "" }
      : { exitCode: exit.exitCode, stdout: "", stderr: text };
  }
}
import type { NativeBridge, NativeProcessExit, NativePtyProcessSession } from "./native-bridge";
import { makeLocalFile } from "./platform";
