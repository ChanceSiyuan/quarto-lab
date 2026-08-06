import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";

import {
  BundledRemoteHelperAssets,
  type BundledRemoteHelperAssetReader,
} from "../src/remote-helper-assets";

const x86 = Uint8Array.of(1, 2, 3);
const arm = Uint8Array.of(4, 5, 6);
const digest = (bytes: Uint8Array): string => createHash("sha256").update(bytes).digest("hex");

function fixture(overrides: Record<string, Uint8Array> = {}): BundledRemoteHelperAssetReader {
  const manifest = new TextEncoder().encode(JSON.stringify({
    schemaVersion: 1,
    helperVersion: "1.0.0",
    artifacts: [
      {
        tuple: "linux-x86_64-static",
        path: "remote/linux-x86_64-static/qlab-remote",
        archiveSha256: digest(x86),
        executableSha256: digest(x86),
      },
      {
        tuple: "linux-aarch64-static",
        path: "remote/linux-aarch64-static/qlab-remote",
        archiveSha256: digest(arm),
        executableSha256: digest(arm),
      },
    ],
  }));
  const assets: Record<string, Uint8Array> = {
    "remote/remote-helper-manifest.json": manifest,
    "remote/linux-x86_64-static/qlab-remote": x86,
    "remote/linux-aarch64-static/qlab-remote": arm,
    ...overrides,
  };
  return { read: async (path) => assets[path] ?? Promise.reject(new Error("missing")) };
}

describe("bundled remote helper assets", () => {
  it("selects the immutable helper for each supported Linux architecture", async () => {
    const assets = new BundledRemoteHelperAssets(fixture(), digest);

    const x86Install = await assets.load("linux-x86_64-static");
    const armInstall = await assets.load("linux-aarch64-static");

    expect([...x86Install.artifact]).toEqual([...x86]);
    expect(x86Install.manifest).toMatchObject({
      helperVersion: "1.0.0",
      tuple: "linux-x86_64-static",
      archiveSha256: digest(x86),
    });
    expect([...armInstall.artifact]).toEqual([...arm]);
  });

  it("fails closed for a modified helper or malformed manifest", async () => {
    const tampered = new BundledRemoteHelperAssets(fixture({
      "remote/linux-x86_64-static/qlab-remote": Uint8Array.of(9),
    }), digest);
    await expect(tampered.load("linux-x86_64-static")).rejects.toThrow(/integrity/i);

    const malformed = new BundledRemoteHelperAssets({
      read: async () => new TextEncoder().encode("{}"),
    }, digest);
    await expect(malformed.load("linux-aarch64-static")).rejects.toThrow(/manifest/i);
  });
});
