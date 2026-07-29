// @vitest-environment happy-dom

import { beforeEach, describe, expect, it, vi } from "vitest";
import { EXTERNAL_EDITORS, type ExternalEditorApp } from "../src/external-editor";
import type { QmdIndexEntry } from "../src/qmd-index";
import { QmdWorkspaceView } from "../src/qmd-workspace";

const PAGE = "knowledge/Magic/Bell_magic.qmd";
const DRAFT = "drafts/Dynamics/floquet.qmd";

const CURSOR = EXTERNAL_EDITORS.find((editor) => editor.id === "cursor")!;
const VSCODE = EXTERNAL_EDITORS.find((editor) => editor.id === "vscode")!;

function entry(relativePath: string): QmdIndexEntry {
  const parts = relativePath.split("/");
  return {
    relativePath,
    treeId: relativePath.startsWith("knowledge/") ? "knowledge" : "drafts",
    name: parts[parts.length - 1]!.slice(0, -".qmd".length),
    segments: relativePath.toLowerCase().split("/"),
  };
}

function mount(editors: ExternalEditorApp[] = [CURSOR, VSCODE]) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const renderService = {
    open: vi.fn(async (_tree: unknown, _root: string, relativePath: string) =>
      `http://127.0.0.1:44100/${relativePath.split("/").slice(1).join("/").replace(".qmd", ".html")}`),
    stop: vi.fn(),
    diagnostic: vi.fn(() => null as string | null),
  };
  const openExternally = vi.fn(async () => {});
  const onActiveDocument = vi.fn();
  const onEditorChosen = vi.fn();
  const view = new QmdWorkspaceView(host, {
    onBack: vi.fn(),
    renderService: renderService as never,
    index: async () => [entry(PAGE), entry(DRAFT)],
    editors: async () => editors,
    openExternally,
    onEditorChosen,
    onActiveDocument,
  });
  view.repoRootHint = "/repo";
  return { host, view, renderService, openExternally, onActiveDocument, onEditorChosen };
}

async function settle(): Promise<void> {
  for (let index = 0; index < 4; index++) await new Promise((resolve) => setTimeout(resolve, 0));
}

describe("QmdWorkspaceView", () => {
  beforeEach(() => {
    document.body.replaceChildren();
    delete (document as unknown as { createXULElement?: unknown }).createXULElement;
  });

  it("previews a page and never mounts an editor of its own", async () => {
    const { host, view, renderService } = mount();
    view.show();
    await view.open(PAGE);

    expect(renderService.open).toHaveBeenCalledOnce();
    expect(host.querySelector(".zc-qmd-path")!.textContent).toBe(PAGE);
    expect(host.querySelector(".zc-qmd-tree-badge")!.textContent).toBe("Trusted Knowledge");
    // Writing belongs to a real editor; nothing here takes keystrokes.
    expect(host.querySelector(".cm-content")).toBeNull();
    expect(host.querySelector("[data-editor-mode]")).toBeNull();
    view.destroy();
  });

  it("collapses the file tree toward the left and restores it from the edge handle", async () => {
    const { host, view } = mount();
    view.show();
    await view.open(PAGE);

    const root = host.querySelector<HTMLElement>(".zc-qmd-workspace")!;
    const toggle = host.querySelector<HTMLButtonElement>(".zc-qmd-file-toggle")!;
    expect(toggle.textContent).toBe("‹");
    expect(toggle.getAttribute("aria-expanded")).toBe("true");

    toggle.click();
    expect(root.classList.contains("is-files-collapsed")).toBe(true);
    expect(toggle.textContent).toBe("›");
    expect(toggle.getAttribute("aria-expanded")).toBe("false");

    toggle.click();
    expect(root.classList.contains("is-files-collapsed")).toBe(false);
    expect(toggle.textContent).toBe("‹");
    expect(toggle.getAttribute("aria-expanded")).toBe("true");
    view.destroy();
  });

  it("previews a draft too, and says it will not be published", async () => {
    const { host, view } = mount();
    view.show();
    await view.open(DRAFT);

    expect(host.querySelector(".zc-qmd-tree-badge")!.textContent).toBe("Draft");
    expect(host.querySelector(".zc-qmd-status")!.textContent).toContain("Draft");
    view.destroy();
  });

  it("hands the repository and the file to the chosen editor", async () => {
    const { host, view, openExternally } = mount();
    view.show();
    await view.open(PAGE);

    const button = host.querySelector<HTMLButtonElement>(".zc-qmd-edit-external")!;
    expect(button.disabled).toBe(false);
    expect(button.textContent).toBe("Edit in Cursor");
    button.click();
    await settle();

    expect(openExternally).toHaveBeenCalledWith(CURSOR, PAGE);
    view.destroy();
  });

  it("uses the editor picked from the list and remembers the choice", async () => {
    const { host, view, openExternally, onEditorChosen } = mount();
    view.show();
    await view.open(PAGE);

    const picker = host.querySelector<HTMLSelectElement>(".zc-qmd-editor-picker")!;
    expect(picker.hidden).toBe(false);
    expect([...picker.options].map((option) => option.value)).toEqual(["cursor", "vscode"]);
    picker.value = "vscode";
    picker.dispatchEvent(new Event("change"));
    expect(onEditorChosen).toHaveBeenCalledWith("vscode");
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-edit-external")!.textContent)
      .toBe("Edit in VS Code");

    host.querySelector<HTMLButtonElement>(".zc-qmd-edit-external")!.click();
    await settle();
    expect(openExternally).toHaveBeenCalledWith(VSCODE, PAGE);
    view.destroy();
  });

  it("hides the picker when only one editor is installed", async () => {
    const { host, view } = mount([CURSOR]);
    view.show();
    await view.open(PAGE);
    expect(host.querySelector<HTMLSelectElement>(".zc-qmd-editor-picker")!.hidden).toBe(true);
    view.destroy();
  });

  it("says so plainly when no editor is installed, and stays disabled", async () => {
    const { host, view, openExternally } = mount([]);
    view.show();
    await view.open(PAGE);

    const button = host.querySelector<HTMLButtonElement>(".zc-qmd-edit-external")!;
    expect(button.disabled).toBe(true);
    expect(button.textContent).toBe("No Editor Found");
    button.click();
    await settle();
    expect(openExternally).not.toHaveBeenCalled();
    view.destroy();
  });

  it("reports a launch failure instead of pretending it worked", async () => {
    const { host, view } = mount();
    view.show();
    await view.open(PAGE);
    // Replace the launcher with one that fails, the way a missing app would.
    (view as unknown as { options: { openExternally: () => Promise<void> } }).options.openExternally =
      () => Promise.reject(new Error("无法启动 Cursor"));

    host.querySelector<HTMLButtonElement>(".zc-qmd-edit-external")!.click();
    await settle();

    expect(host.querySelector(".zc-qmd-status")!.textContent).toContain("无法启动 Cursor");
    view.destroy();
  });

  it("lists both trees and opens the file a quick-open row names", async () => {
    const { host, view } = mount();
    view.show();
    await view.open(PAGE);

    const roots = [...host.querySelectorAll<HTMLElement>(".zc-qmd-filecolumn > .zc-qmd-folder > .zc-qmd-file-row")]
      .map((row) => row.dataset.tree);
    expect(roots).toEqual(["knowledge", "drafts"]);

    host.querySelector<HTMLButtonElement>(".zc-qmd-quickopen-button")!.click();
    await settle();
    const input = host.querySelector<HTMLInputElement>(".zc-qmd-quickopen-input")!;
    input.value = "floq";
    input.dispatchEvent(new Event("input"));
    const rows = [...host.querySelectorAll<HTMLButtonElement>(".zc-qmd-quickopen-row")];
    expect(rows.length).toBe(1);
    rows[0]!.click();
    await settle();

    expect(host.querySelector(".zc-qmd-path")!.textContent).toBe(DRAFT);
    view.destroy();
  });

  it("refuses a path outside both trees without starting a render", async () => {
    const { host, view, renderService } = mount();
    view.show();
    await view.open("literature/ref.qmd");

    expect(renderService.open).not.toHaveBeenCalled();
    expect(host.querySelector(".zc-qmd-status")!.textContent).toContain("Only QMD files");
    view.destroy();
  });

  it("tells the assistant which file is open, and that none is on teardown", async () => {
    const { view, onActiveDocument, renderService } = mount();
    view.show();
    await view.open(PAGE);
    expect(onActiveDocument).toHaveBeenCalledWith(PAGE);

    view.hide();
    expect(onActiveDocument).toHaveBeenLastCalledWith(null);
    view.show();
    expect(onActiveDocument).toHaveBeenLastCalledWith(PAGE);

    view.destroy();
    expect(onActiveDocument).toHaveBeenLastCalledWith(null);
    expect(renderService.stop).toHaveBeenCalled();
  });

  it("does not expose a document as active until its preview opens successfully", async () => {
    const { view, onActiveDocument, renderService } = mount();
    let rejectRender!: (error: Error) => void;
    renderService.open.mockImplementation(() => new Promise((_resolve, reject) => { rejectRender = reject; }));
    view.show();

    const opening = view.open(PAGE);
    expect(onActiveDocument).not.toHaveBeenCalled();
    await settle();
    rejectRender(new Error("preview failed"));
    await opening;
    expect(onActiveDocument).not.toHaveBeenCalledWith(PAGE);
    view.destroy();
  });

  it("surfaces a render diagnostic instead of showing a stale page as fresh", async () => {
    const { host, view, renderService } = mount();
    renderService.diagnostic.mockReturnValue("knowledge/x.qmd: frontmatter is not valid YAML");
    view.show();
    await view.open(PAGE);

    expect(host.querySelector(".zc-qmd-status")!.textContent).toContain("frontmatter is not valid YAML");
    expect(host.querySelector<HTMLElement>(".zc-qmd-status")!.dataset.state).toBe("error");
    view.destroy();
  });

  it("reopens the render service before refreshing a refused preview URL", async () => {
    const reload = vi.fn();
    (document as unknown as { createXULElement(name: string): HTMLElement }).createXULElement =
      vi.fn(() => {
        const browser = document.createElement("div") as unknown as HTMLElement & { reload(): void };
        browser.reload = reload;
        return browser;
      });
    const { host, view, renderService } = mount();
    view.show();
    await view.open(DRAFT);

    host.querySelector<HTMLButtonElement>(".zc-qmd-refresh")!.click();
    await settle();

    expect(renderService.open).toHaveBeenCalledTimes(2);
    expect(reload).toHaveBeenCalledOnce();
    view.destroy();
  });
});
