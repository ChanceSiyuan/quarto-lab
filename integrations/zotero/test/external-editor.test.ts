// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest";
import {
  EXTERNAL_EDITORS,
  installedEditors,
  openInExternalEditor,
  preferredEditor,
  type ExternalEditorRuntime,
} from "../src/external-editor";

function runtime(
  present: readonly string[],
  resolved: Readonly<Record<string, string>> = {},
): ExternalEditorRuntime & {
  launched: { application: string; paths: readonly string[] }[];
} {
  const launched: { application: string; paths: readonly string[] }[] = [];
  return {
    launched,
    async exists(path) {
      return present.includes(path);
    },
    homeDirectory: () => "/Users/researcher",
    async realPath(path) {
      return resolved[path] ?? path;
    },
    async launch(application, paths) {
      launched.push({ application, paths });
    },
  };
}

const CURSOR = EXTERNAL_EDITORS.find((editor) => editor.id === "cursor")!;

describe("installedEditors", () => {
  it("finds an editor in /Applications and one in the user's own folder", async () => {
    const found = await installedEditors(runtime([
      "/Applications/Visual Studio Code.app",
      "/Users/researcher/Applications/Cursor.app",
    ]));
    expect(found.map((editor) => editor.id)).toEqual(["cursor", "vscode"]);
    expect(found[0]?.path).toBe("/Users/researcher/Applications/Cursor.app");
    expect(found[1]?.path).toBe("/Applications/Visual Studio Code.app");
  });

  it("returns nothing when no editor is installed", async () => {
    expect(await installedEditors(runtime([]))).toEqual([]);
  });

  it("keeps the declared preference order rather than the filesystem's", async () => {
    const found = await installedEditors(runtime([
      "/Applications/Zed.app",
      "/Applications/Cursor.app",
      "/Applications/Sublime Text.app",
    ]));
    expect(found.map((editor) => editor.id)).toEqual(["cursor", "zed", "sublime"]);
  });

  it("does not count the same editor twice when it exists in two places", async () => {
    const found = await installedEditors(runtime([
      "/Applications/Cursor.app",
      "/Users/researcher/Applications/Cursor.app",
    ]));
    expect(found.map((editor) => editor.id)).toEqual(["cursor"]);
  });
});

describe("openInExternalEditor", () => {
  it("opens the repository as the workspace and the file inside it, in one launch", async () => {
    const fake = runtime([]);
    await openInExternalEditor(fake, CURSOR, "/repo", "knowledge/Magic/Bell_magic.qmd");

    expect(fake.launched).toEqual([{
      application: "Cursor",
      paths: ["/repo", "/repo/knowledge/Magic/Bell_magic.qmd"],
    }]);
  });

  it("opens a draft the same way", async () => {
    const fake = runtime([]);
    await openInExternalEditor(fake, CURSOR, "/repo/", "drafts/Dynamics/floquet.qmd");

    expect(fake.launched[0]!.paths).toEqual(["/repo", "/repo/drafts/Dynamics/floquet.qmd"]);
  });

  it("refuses a path outside both trees before launching anything", async () => {
    const fake = runtime([]);
    const launch = vi.spyOn(fake, "launch");

    await expect(openInExternalEditor(fake, CURSOR, "/repo", "literature/ref.bib")).rejects.toThrow();
    await expect(openInExternalEditor(fake, CURSOR, "/repo", "knowledge/../../etc/x.qmd")).rejects.toThrow();
    expect(launch).not.toHaveBeenCalled();
  });

  it("refuses a QMD symlink that resolves outside its declared tree", async () => {
    const fake = runtime([], {
      "/repo": "/repo",
      "/repo/knowledge": "/repo/knowledge",
      "/repo/knowledge/linked.qmd": "/private/outside.qmd",
    });

    await expect(
      openInExternalEditor(fake, CURSOR, "/repo", "knowledge/linked.qmd"),
    ).rejects.toThrow(/symbolic link|outside/i);
    expect(fake.launched).toEqual([]);
  });
});

describe("preferredEditor", () => {
  it("uses the remembered editor while it is installed, and the best one otherwise", () => {
    const installed = [...EXTERNAL_EDITORS].filter((editor) => editor.id !== "cursor");
    expect(preferredEditor(installed, "zed")?.id).toBe("zed");
    expect(preferredEditor(installed, "cursor")?.id).toBe("vscode");
    expect(preferredEditor([], "cursor")).toBeNull();
  });
});
