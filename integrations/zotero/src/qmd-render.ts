import type { BridgeEvent, NativeBridge, SpawnOptions } from "./native-bridge";
import { previewPathFor, type EditorTree } from "./editor-tree";
import { sleep } from "./platform";

const PROCESS_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin";
const PREVIEW_PORT_MIN = 43_000;
const PREVIEW_PORT_SPAN = 1_500;

export interface QmdRenderProcess {
  /** Origin the preview is serving from, with a trailing slash. */
  url: string;
  stop(): void;
  /** The last render failure, or null while the last render succeeded. */
  diagnostic(): string | null;
  /** Whether this process still serves the requested page. */
  ready(relativePath: string): Promise<boolean>;
}

export interface QmdValidation {
  ok: boolean;
  output: string;
}

export interface QmdRenderRuntime {
  start(
    tree: EditorTree,
    repoRoot: string,
    relativePath: string,
    port: number,
  ): Promise<QmdRenderProcess>;
  validate(repoRoot: string, command: string): Promise<QmdValidation>;
  diff(repoRoot: string, relativePath: string): Promise<string>;
}

/** A stable but non-colliding starting port for one document. */
export function nextPreviewPort(seed: number): number {
  return PREVIEW_PORT_MIN + (Math.abs(seed) % PREVIEW_PORT_SPAN);
}

function hash(value: string): number {
  return [...value].reduce((total, character) => ((total * 33) ^ character.charCodeAt(0)) >>> 0, 5381);
}

/**
 * The render tab's process.
 *
 * At most one preview runs at a time. It is started when the user first asks
 * to see a rendered page rather than when a document is opened, because a
 * single-page Quarto preview takes several seconds to serve its first byte and
 * most editing never needs one.
 */
export class QmdRenderService {
  private current: QmdRenderProcess | null = null;
  private currentKey = "";
  private generation = 0;

  constructor(
    private readonly runtime: QmdRenderRuntime,
    private readonly port: (seed: number) => number = nextPreviewPort,
  ) {}

  async open(tree: EditorTree, repoRoot: string, relativePath: string): Promise<string> {
    const generation = ++this.generation;
    const key = `${tree.id}:${repoRoot}:${relativePath}`;
    const previewPath = previewPathFor(tree, relativePath);
    const current = this.current;
    if (current && this.currentKey === key) {
      const ready = await current.ready(previewPath).catch(() => false);
      if (generation !== this.generation || this.current !== current || this.currentKey !== key) {
        throw new Error("QMD preview request was superseded by a newer document");
      }
      if (ready) return new URL(previewPath, current.url).href;
      this.stopCurrent();
    }
    else this.stopCurrent();
    const started = await this.runtime.start(tree, repoRoot, relativePath, this.port(hash(key)));
    if (generation !== this.generation) {
      started.stop();
      throw new Error("QMD preview request was superseded by a newer document");
    }
    this.current = started;
    this.currentKey = key;
    return new URL(previewPath, started.url).href;
  }

  running(): boolean {
    return this.current !== null;
  }

  diagnostic(): string | null {
    return this.current?.diagnostic() ?? null;
  }

  /** The tree's own check, or null when the tree has none. */
  validate(tree: EditorTree, repoRoot: string): Promise<QmdValidation> | null {
    if (!tree.validateCommand) return null;
    return this.runtime.validate(repoRoot, tree.validateCommand);
  }

  diff(repoRoot: string, relativePath: string): Promise<string> {
    return this.runtime.diff(repoRoot, relativePath);
  }

  stop(): void {
    this.generation += 1;
    this.stopCurrent();
  }

  private stopCurrent(): void {
    this.current?.stop();
    this.current = null;
    this.currentKey = "";
  }
}

/**
 * A unified diff of one file, for when Git cannot produce one.
 *
 * Only the changed run and three lines of context on either side, because the
 * panel this feeds is a review aid rather than a patch.
 */
export function createQmdDiff(path: string, before: string, after: string): string {
  if (before === after) return `No changes in ${path}.`;
  const oldLines = before.replace(/\n$/, "").split("\n");
  const newLines = after.replace(/\n$/, "").split("\n");
  let prefix = 0;
  while (prefix < oldLines.length && prefix < newLines.length && oldLines[prefix] === newLines[prefix]) {
    prefix += 1;
  }
  let suffix = 0;
  while (
    suffix < oldLines.length - prefix &&
    suffix < newLines.length - prefix &&
    oldLines[oldLines.length - 1 - suffix] === newLines[newLines.length - 1 - suffix]
  ) suffix += 1;
  const contextStart = Math.max(0, prefix - 3);
  const oldEnd = oldLines.length - suffix;
  const newEnd = newLines.length - suffix;
  const contextEndOld = Math.min(oldLines.length, oldEnd + 3);
  const contextEndNew = Math.min(newLines.length, newEnd + 3);
  return [
    `--- a/${path}`,
    `+++ b/${path}`,
    `@@ -${contextStart + 1},${contextEndOld - contextStart} +${contextStart + 1},${contextEndNew - contextStart} @@`,
    ...oldLines.slice(contextStart, prefix).map((line) => ` ${line}`),
    ...oldLines.slice(prefix, oldEnd).map((line) => `-${line}`),
    ...newLines.slice(prefix, newEnd).map((line) => `+${line}`),
    ...newLines.slice(newEnd, contextEndNew).map((line) => ` ${line}`),
  ].join("\n") + "\n";
}

interface CommandResult {
  exitCode: number | null;
  output: string;
}

/** What each tree runs to serve one file, as a `zsh -lc` script plus arguments. */
const RENDER_SCRIPTS: Record<EditorTree["renderCommand"], string> = {
  "knowledge-preview": 'exec npm run knowledge:preview -- --port "$1" --watch-source "$2"',
  "draft-preview": 'exec npm run draft:preview -- --port "$1" --file "$2"',
};

export function createQmdRenderRuntime(bridge: NativeBridge): QmdRenderRuntime {
  let sequence = 0;
  const processID = (prefix: string) => `${prefix}-${Date.now()}-${++sequence}`.slice(0, 64);

  const run = async (sessionId: string, options: SpawnOptions): Promise<CommandResult> => {
    let output = "";
    let resolveExit!: (result: CommandResult) => void;
    const completed = new Promise<CommandResult>((resolve) => { resolveExit = resolve; });
    const unsubscribe = bridge.onEvent((event: BridgeEvent) => {
      if (!("sessionId" in event) || event.sessionId !== sessionId) return;
      if (event.type === "output") output += bridge.decodeOutput(sessionId, event.data);
      if (event.type === "exit") {
        output += bridge.flushOutput(sessionId);
        unsubscribe();
        resolveExit({ exitCode: event.exitCode, output });
      }
    });
    try {
      await bridge.start();
      await bridge.spawnPipe(sessionId, options);
    }
    catch (error) {
      unsubscribe();
      throw error;
    }
    return completed;
  };

  const serves = async (url: string): Promise<boolean> => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 750);
    try {
      const response = await fetch(url, { cache: "no-store", signal: controller.signal });
      return response.ok;
    }
    catch {
      return false;
    }
    finally {
      clearTimeout(timer);
    }
  };

  return {
    async start(tree, repoRoot, relativePath, port) {
      const sessionId = processID("qmd-preview");
      let output = "";
      let exited = false;
      let diagnostic: string | null = null;
      const unsubscribe = bridge.onEvent((event) => {
        if (!("sessionId" in event) || event.sessionId !== sessionId) return;
        if (event.type === "output") {
          output += bridge.decodeOutput(sessionId, event.data);
          const tail = output.slice(-32_000);
          const failureMarker = "knowledge preview: source not rendered; ";
          const failureAt = tail.lastIndexOf(failureMarker);
          const refreshedAt = tail.lastIndexOf("knowledge preview: refreshed ");
          if (failureAt > refreshedAt) {
            diagnostic = tail.slice(failureAt + failureMarker.length)
              .split("\nknowledge preview:", 1)[0]!.trim();
          }
          else if (refreshedAt >= 0) diagnostic = null;
          output = tail;
        }
        if (event.type === "exit") {
          exited = true;
          output += bridge.flushOutput(sessionId);
          unsubscribe();
        }
      });

      await bridge.start();
      await bridge.spawnPipe(sessionId, {
        argv: [
          "/bin/zsh", "-lc",
          RENDER_SCRIPTS[tree.renderCommand],
          "qmd-preview", String(port), relativePath,
        ],
        cwd: repoRoot,
        env: { PATH: PROCESS_PATH },
      });

      const url = `http://127.0.0.1:${port}/`;
      const readyUrl = new URL(previewPathFor(tree, relativePath), url).href;
      for (let attempt = 0; attempt < 240; attempt++) {
        if (exited) throw new Error(output.trim() || "Quarto preview exited");
        if (await serves(readyUrl)) {
          return {
            url,
            diagnostic: () => diagnostic,
            ready: (relativePreviewPath) =>
              exited
                ? Promise.resolve(false)
                : serves(new URL(relativePreviewPath, url).href),
            stop: () => {
              unsubscribe();
              bridge.closeSession(sessionId);
            },
          };
        }
        await sleep(250);
      }
      bridge.closeSession(sessionId);
      unsubscribe();
      throw new Error(`Quarto preview startup timed out${output.trim() ? `: ${output.trim()}` : ""}`);
    },

    async validate(repoRoot, command) {
      const result = await run(processID("qmd-check"), {
        argv: ["/bin/zsh", "-lc", command, "qmd-check"],
        cwd: repoRoot,
        env: { PATH: PROCESS_PATH },
      });
      return { ok: result.exitCode === 0, output: result.output.trim() };
    },

    async diff(repoRoot, relativePath) {
      const result = await run(processID("qmd-diff"), {
        argv: [
          "/bin/zsh", "-lc",
          '/usr/bin/git -C "$1" --no-pager diff --no-color -- "$2"',
          "qmd-diff", repoRoot, relativePath,
        ],
        cwd: repoRoot,
        env: { PATH: PROCESS_PATH },
      });
      const output = result.output.trim();
      if (result.exitCode !== 0) return output || "Unable to read Git diff";
      return output || `${relativePath} matches the last commit.`;
    },
  };
}
