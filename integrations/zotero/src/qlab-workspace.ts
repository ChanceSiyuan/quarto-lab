export interface QLabPathHost {
  exists(path: string): Promise<boolean>;
  realPath(path: string): Promise<string>;
  join(...parts: string[]): string;
}

const REQUIRED_ENTRIES = ["AGENTS.md", "qlab", "literature", "drafts", "knowledge"] as const;

export async function isQLabRepositoryShape(
  root: string,
  host: QLabPathHost,
): Promise<boolean> {
  if (!root.trim()) return false;
  const checks = await Promise.all(
    REQUIRED_ENTRIES.map((entry) => host.exists(host.join(root, entry))),
  );
  return checks.every(Boolean);
}

export async function normalizeQLabRoot(
  value: string,
  host: QLabPathHost,
): Promise<string> {
  const trimmed = value.trim().replace(/[\\/]+$/, "");
  if (!trimmed) return "";
  return (await host.realPath(trimmed)).replace(/[\\/]+$/, "");
}

export function createGeckoQLabPathHost(): QLabPathHost {
  return {
    exists: (path) => IOUtils.exists(path),
    realPath: async (path) => {
      const file = Components.classes["@mozilla.org/file/local;1"]
        .createInstance(Components.interfaces.nsIFile);
      file.initWithPath(path);
      file.normalize();
      return String(file.path || path);
    },
    join: (...parts) => PathUtils.join(...parts),
  };
}
