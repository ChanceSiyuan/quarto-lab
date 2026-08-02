import { sha256Bytes } from "./hashing";
import { REMOTE_HELPER_VERSION } from "./remote-helper-protocol";
import type {
  RemoteHelperTuple,
  VerifiedHelperInstall,
  VerifiedRemoteHelperArtifact,
} from "./ssh-target-transport";

const DIGEST = /^[a-f0-9]{64}$/u;
const TUPLES: readonly RemoteHelperTuple[] = [
  "linux-x86_64-static",
  "linux-aarch64-static",
];

type ManifestArtifact = Readonly<{
  tuple: RemoteHelperTuple;
  path: string;
  archiveSha256: string;
  executableSha256: string;
}>;

export interface BundledRemoteHelperAssetReader {
  read(path: string): Promise<Uint8Array>;
}

export class BundledRemoteHelperAssets {
  constructor(
    private readonly reader: BundledRemoteHelperAssetReader,
    private readonly digest: (bytes: Uint8Array) => string = sha256Bytes,
  ) {}

  async load(tuple: RemoteHelperTuple): Promise<VerifiedHelperInstall> {
    if (!TUPLES.includes(tuple)) throw new Error("Unsupported remote helper tuple");
    const manifest = this.parseManifest(await this.reader.read(
      "remote/remote-helper-manifest.json",
    ));
    const entry = manifest.find((artifact) => artifact.tuple === tuple);
    if (!entry) throw new Error("Bundled remote helper manifest is incomplete");
    const bytes = await this.reader.read(entry.path);
    const digest = this.digest(bytes);
    if (digest !== entry.archiveSha256 || digest !== entry.executableSha256) {
      throw new Error("The bundled remote helper failed its integrity check");
    }
    return Object.freeze({
      manifest: Object.freeze({
        helperVersion: REMOTE_HELPER_VERSION,
        tuple,
        archiveSha256: entry.archiveSha256,
        executableSha256: entry.executableSha256,
      }),
      artifact: bytes.slice() as VerifiedRemoteHelperArtifact,
    });
  }

  private parseManifest(bytes: Uint8Array): readonly ManifestArtifact[] {
    let value: unknown;
    try { value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
    catch { throw new Error("Bundled remote helper manifest is malformed"); }
    if (!isRecord(value) || !exactKeys(value, ["schemaVersion", "helperVersion", "artifacts"])
      || value.schemaVersion !== 1 || value.helperVersion !== REMOTE_HELPER_VERSION
      || !Array.isArray(value.artifacts) || value.artifacts.length !== TUPLES.length) {
      throw new Error("Bundled remote helper manifest is malformed");
    }
    const artifacts = value.artifacts.map((raw): ManifestArtifact => {
      if (!isRecord(raw) || !exactKeys(raw, [
        "tuple", "path", "archiveSha256", "executableSha256",
      ]) || !TUPLES.includes(raw.tuple as RemoteHelperTuple)
        || typeof raw.path !== "string"
        || raw.path !== `remote/${String(raw.tuple)}/qlab-remote`
        || typeof raw.archiveSha256 !== "string" || !DIGEST.test(raw.archiveSha256)
        || typeof raw.executableSha256 !== "string" || !DIGEST.test(raw.executableSha256)) {
        throw new Error("Bundled remote helper manifest is malformed");
      }
      return Object.freeze({
        tuple: raw.tuple as RemoteHelperTuple,
        path: raw.path,
        archiveSha256: raw.archiveSha256,
        executableSha256: raw.executableSha256,
      });
    });
    if (new Set(artifacts.map(({ tuple }) => tuple)).size !== TUPLES.length) {
      throw new Error("Bundled remote helper manifest is malformed");
    }
    return Object.freeze(artifacts);
  }
}

export function createGeckoRemoteHelperAssetReader(
  bundledRootURI: string,
): BundledRemoteHelperAssetReader {
  return {
    read: (path) => readBundledAsset(`${bundledRootURI}${path}`),
  };
}

async function readBundledAsset(uri: string): Promise<Uint8Array> {
  try {
    const response = await fetch(uri);
    if (response.ok || response.status === 0) return new Uint8Array(await response.arrayBuffer());
  }
  catch { /* jar: fetch can be unavailable on some Zotero builds */ }
  return new Promise<Uint8Array>((resolve, reject) => {
    try {
      const channel = NetUtil.newChannel({
        uri: Services.io.newURI(uri),
        loadUsingSystemPrincipal: true,
      });
      NetUtil.asyncFetch(channel, (stream: any, status: number) => {
        if (!Components.isSuccessCode(status)) {
          reject(new Error(`Could not read bundled remote helper (${status})`));
          return;
        }
        try {
          const binary = Components.classes["@mozilla.org/binaryinputstream;1"]
            .createInstance(Components.interfaces.nsIBinaryInputStream);
          binary.setInputStream(stream);
          resolve(Uint8Array.from(binary.readByteArray(binary.available())));
        }
        catch (error) { reject(error); }
      });
    }
    catch (error) { reject(error); }
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function exactKeys(value: Record<string, unknown>, expected: readonly string[]): boolean {
  const keys = Object.keys(value);
  return keys.length === expected.length && expected.every((key) => Object.hasOwn(value, key));
}
