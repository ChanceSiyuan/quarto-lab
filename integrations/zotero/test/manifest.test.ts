import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

interface ZoteroManifest {
  version?: string;
  applications?: {
    zotero?: {
      id?: string;
      update_url?: string;
      strict_min_version?: string;
      strict_max_version?: string;
    };
  };
}

describe("Zotero add-on manifest", () => {
  it("ships AI Context as Zotero integration 0.12.0", () => {
    const manifest = JSON.parse(
      readFileSync(join(process.cwd(), "manifest.json"), "utf8"),
    ) as ZoteroManifest;
    const packageJson = JSON.parse(
      readFileSync(join(process.cwd(), "package.json"), "utf8"),
    ) as { version?: string };
    const packageLock = JSON.parse(
      readFileSync(join(process.cwd(), "package-lock.json"), "utf8"),
    ) as { version?: string; packages?: { ""?: { version?: string } } };

    expect(manifest.version).toBe("0.12.0");
    expect(packageJson.version).toBe("0.12.0");
    expect(packageLock.version).toBe("0.12.0");
    expect(packageLock.packages?.[""]?.version).toBe("0.12.0");
  });

  it("declares the Zotero 9 install contract, including an update URL", () => {
    const manifest = JSON.parse(
      readFileSync(join(process.cwd(), "manifest.json"), "utf8"),
    ) as ZoteroManifest;
    const zotero = manifest.applications?.zotero;

    expect(manifest.version).toBe("0.12.0");
    expect(zotero?.id).toBe("qlab-zotero@quarto-lab.local");
    expect(zotero?.update_url).toBe("https://qlab.invalid/updates.json");
    expect(zotero?.strict_min_version).toBe("9.0");
    expect(zotero?.strict_max_version).toBe("9.0.*");
  });

  it("uses Research Loop branding in both bundled locales", () => {
    for (const locale of ["en-US", "zh-CN"]) {
      const messages = readFileSync(
        join(process.cwd(), "locale", locale, "zoterochat.ftl"),
        "utf8",
      );
      expect(messages).toContain("Research Loop · Local Codex");
      expect(messages).not.toContain("Zotkit Research Chat");
    }
  });
});
