import type { BridgeEvent, NativeBridge, SpawnOptions } from "./native-bridge";
import { randomID } from "./platform";

const PROCESS_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin";

export interface QLabZoteroSyncRuntime {
  start(): Promise<void>;
  spawn(sessionId: string, options: SpawnOptions): Promise<void>;
  onEvent(listener: (event: BridgeEvent) => void): () => void;
}

export function createQLabZoteroSyncRuntime(bridge: NativeBridge): QLabZoteroSyncRuntime {
  return {
    start: () => bridge.start(),
    spawn: (sessionId, options) => bridge.spawnPipe(sessionId, options),
    onEvent: (listener) => bridge.onEvent(listener),
  };
}

function decodeBase64(value: string): Uint8Array {
  const binary = atob(value);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

/** Runs the repository-owned Zotero importer and waits for its real exit. */
export class QLabZoteroSyncService {
  constructor(
    private readonly runtime: QLabZoteroSyncRuntime,
    private readonly sessionID: () => string = () => randomID("qlab-zotero-sync").slice(0, 64),
  ) {}

  async sync(repositoryRoot: string): Promise<string> {
    const root = repositoryRoot.trim().replace(/[\\/]+$/u, "");
    if (!root) throw new Error("Choose a QLab repository first");
    await this.runtime.start();

    const sessionId = this.sessionID();
    const decoder = new TextDecoder();
    let output = "";
    let unsubscribe = () => {};
    const completion = new Promise<string>((resolve, reject) => {
      unsubscribe = this.runtime.onEvent((event) => {
        if (!("sessionId" in event) || event.sessionId !== sessionId) return;
        if (event.type === "output") {
          output += decoder.decode(decodeBase64(event.data), { stream: true });
          return;
        }
        if (event.type === "error") {
          reject(new Error(event.message));
          return;
        }
        if (event.type !== "exit") return;
        output += decoder.decode();
        const summary = output.trim();
        if (event.exitCode === 0) resolve(summary);
        else reject(new Error(summary || `QLab Zotero import exited with status ${event.exitCode ?? "unknown"}`));
      });
    });

    try {
      await this.runtime.spawn(sessionId, {
        argv: [`${root}/qlab`, "literature", "import", "zotero"],
        cwd: root,
        env: { PATH: PROCESS_PATH },
      });
      return await completion;
    }
    finally {
      unsubscribe();
    }
  }
}
