import { describe, expect, it } from "vitest";

import {
  QLabZoteroSyncService,
  type QLabZoteroSyncRuntime,
} from "../src/qlab-zotero-sync";

function encoded(value: string): string {
  return Buffer.from(value, "utf8").toString("base64");
}

describe("one-click Zotero to QLab sync", () => {
  it("runs the repository qlab importer and returns its summary", async () => {
    let listener: Parameters<QLabZoteroSyncRuntime["onEvent"]>[0] = () => {};
    const calls: unknown[] = [];
    const runtime: QLabZoteroSyncRuntime = {
      start: async () => { calls.push("start"); },
      onEvent(next) { listener = next; return () => calls.push("unsubscribe"); },
      async spawn(sessionId, options) {
        calls.push({ sessionId, options });
        listener({ type: "output", sessionId, encoding: "base64", data: encoded("Updated ref.bib\n") });
        listener({ type: "exit", sessionId, exitCode: 0, signal: null });
      },
    };
    const service = new QLabZoteroSyncService(runtime, () => "sync-1");

    await expect(service.sync("/repo")).resolves.toBe("Updated ref.bib");
    expect(calls).toContainEqual({
      sessionId: "sync-1",
      options: {
        argv: ["/repo/qlab", "literature", "import", "zotero"],
        cwd: "/repo",
        env: { PATH: "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" },
      },
    });
    expect(calls.at(-1)).toBe("unsubscribe");
  });

  it("surfaces command output when the importer fails", async () => {
    let listener: Parameters<QLabZoteroSyncRuntime["onEvent"]>[0] = () => {};
    const runtime: QLabZoteroSyncRuntime = {
      start: async () => {},
      onEvent(next) { listener = next; return () => {}; },
      async spawn(sessionId) {
        listener({ type: "output", sessionId, encoding: "base64", data: encoded("Zotero API unavailable") });
        listener({ type: "exit", sessionId, exitCode: 1, signal: null });
      },
    };

    await expect(new QLabZoteroSyncService(runtime, () => "sync-2").sync("/repo"))
      .rejects.toThrow(/Zotero API unavailable/);
  });
});
