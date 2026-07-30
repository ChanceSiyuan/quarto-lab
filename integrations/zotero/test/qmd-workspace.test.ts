// @vitest-environment happy-dom

import { beforeEach, describe, expect, it, vi } from "vitest";
import { EXTERNAL_EDITORS, type ExternalEditorApp } from "../src/external-editor";
import type { QmdIndexEntry } from "../src/qmd-index";
import {
  QmdWorkspaceView,
  qmdDiffForPath,
} from "../src/qmd-workspace";

const PAGE = "knowledge/Magic/Bell_magic.qmd";
const DRAFT = "drafts/Dynamics/floquet.qmd";
const CHANGE = "work/qlab-zotero/draft-changes/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/draft.qmd";
const CHANGE_PREVIEW = "drafts/Dynamics/floquet.qlab-preview-aaaaaaaaaaaa.qmd";

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

function mount(
  editors: ExternalEditorApp[] = [CURSOR, VSCODE],
  options: { pending?: boolean; indexedPending?: boolean } = {},
) {
  const host = document.createElement("div");
  document.body.appendChild(host);
  const renderService = {
    open: vi.fn(async (_tree: unknown, _root: string, relativePath: string) =>
      `http://127.0.0.1:44100/${relativePath.split("/").slice(1).join("/").replace(".qmd", ".html")}`),
    stop: vi.fn(),
    diagnostic: vi.fn(() => null as string | null),
    checkDraft: vi.fn(async () => ({
      ok: true,
      diagnostics: [] as Array<{ code: string; message: string; line: number }>,
    })),
  };
  const changeRenderService = {
    open: vi.fn(async (_tree: unknown, _root: string, relativePath: string) =>
      `http://127.0.0.1:44200/${relativePath.split("/").slice(1).join("/").replace(".qmd", ".html")}`),
    stop: vi.fn(),
    diagnostic: vi.fn(() => null as string | null),
  };
  const openExternally = vi.fn(async () => {});
  const onActiveDocument = vi.fn();
  const onEditorChosen = vi.fn();
  const onReviewDraft = vi.fn(async () => {});
  let pending = Boolean(options.pending);
  let revision = pending ? "pending-revision" : "original-revision";
  const prepareChange = vi.fn(async () => ({
    changePath: CHANGE,
    previewPath: CHANGE_PREVIEW,
    changed: pending,
    revision,
  }));
  const refreshChangePreview = vi.fn(async () => {});
  const keepChange = vi.fn(async () => {
    pending = false;
    return {
      changePath: CHANGE,
      previewPath: CHANGE_PREVIEW,
      changed: false,
      revision: "kept-revision",
    };
  });
  const draftEntry = entry(DRAFT);
  draftEntry.pendingChange = Boolean(options.indexedPending);
  const view = new QmdWorkspaceView(host, {
    onBack: vi.fn(),
    renderService: renderService as never,
    changeRenderService: changeRenderService as never,
    index: async () => [entry(PAGE), draftEntry],
    editors: async () => editors,
    openExternally,
    onEditorChosen,
    onActiveDocument,
    onReviewDraft,
    prepareChange,
    refreshChangePreview,
    keepChange,
  });
  view.repoRootHint = "/repo";
  return {
    host,
    view,
    renderService,
    changeRenderService,
    openExternally,
    onActiveDocument,
    onEditorChosen,
    onReviewDraft,
    prepareChange,
    refreshChangePreview,
    keepChange,
    setPending(value: boolean, nextRevision = revision) {
      pending = value;
      revision = nextRevision;
    },
  };
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
    expect(host.querySelector(".zc-qmd-compliance")!.getAttribute("aria-label")).toContain("checks passed");
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-review")!.hidden).toBe(false);
    view.destroy();
  });

  it("shows draft compliance problems without hiding the review action", async () => {
    const { host, view, renderService } = mount();
    renderService.checkDraft.mockResolvedValue({
      ok: false,
      diagnostics: [{ code: "DESCRIPTION_REQUIRED", message: "description is missing", line: 1 }],
    });
    view.show();
    await view.open(DRAFT);

    const compliance = host.querySelector<HTMLButtonElement>(".zc-qmd-compliance")!;
    expect(compliance.getAttribute("aria-label")).toContain("1 issue");
    compliance.click();
    expect(host.querySelector(".zc-qmd-compliance-details")!.textContent)
      .toContain("DESCRIPTION_REQUIRED · line 1 · description is missing");
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-review")!.disabled).toBe(false);
    view.destroy();
  });

  it("starts a review for the open draft without leaving its preview", async () => {
    const { host, view, onReviewDraft } = mount();
    view.show();
    await view.open(DRAFT);

    host.querySelector<HTMLButtonElement>(".zc-qmd-review")!.click();
    await settle();

    expect(onReviewDraft).toHaveBeenCalledWith(DRAFT);
    expect(view.isVisible()).toBe(true);
    expect(host.querySelector(".zc-qmd-path")!.textContent).toBe(DRAFT);
    view.destroy();
  });

  it("rechecks compliance when Quarto reloads the saved Draft preview", async () => {
    (document as unknown as { createXULElement(name: string): HTMLElement }).createXULElement =
      vi.fn(() => document.createElement("div"));
    const { host, view, renderService } = mount();
    view.show();
    await view.open(DRAFT);
    expect(host.querySelector(".zc-qmd-compliance")!.getAttribute("aria-label")).toContain("checks passed");

    renderService.checkDraft.mockResolvedValue({
      ok: false,
      diagnostics: [{ code: "CITATION_MISSING", message: "citation is missing", line: 12 }],
    });
    host.querySelector(".zc-qmd-render-browser")!.dispatchEvent(new Event("load"));
    await settle();

    expect(host.querySelector(".zc-qmd-compliance")!.getAttribute("aria-label")).toContain("1 issue");
    expect(renderService.checkDraft).toHaveBeenLastCalledWith("/repo", DRAFT);
    view.destroy();
  });

  it("hides draft-only review controls for trusted Knowledge", async () => {
    const { host, view, renderService } = mount();
    view.show();
    await view.open(PAGE);

    expect(renderService.checkDraft).not.toHaveBeenCalled();
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-compliance")!.hidden).toBe(true);
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-review")!.hidden).toBe(true);
    view.destroy();
  });

  it("hands the repository and the file to the chosen editor", async () => {
    const { host, view, openExternally } = mount();
    view.show();
    await view.open(PAGE);

    const button = host.querySelector<HTMLButtonElement>(".zc-qmd-edit-external")!;
    expect(button.disabled).toBe(false);
    const icon = button.querySelector<HTMLImageElement>(".zc-qmd-editor-icon")!;
    expect(icon).not.toBeNull();
    expect(icon.getAttribute("src")).toBe("chrome://zotkit/content/icons/cursor.png");
    expect(icon.alt).toBe("");
    expect(button.getAttribute("aria-label")).toBe("Edit in Cursor");
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
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-edit-external")!.getAttribute("aria-label"))
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
    expect(button.textContent).toBe("∅");
    expect(button.getAttribute("aria-label")).toBe("No Editor Found");
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
    expect(onActiveDocument).toHaveBeenCalledWith(PAGE, null);

    view.hide();
    expect(onActiveDocument).toHaveBeenLastCalledWith(null);
    view.show();
    expect(onActiveDocument).toHaveBeenLastCalledWith(PAGE, null);

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

  it("uses compact icon controls with hover and accessible labels", async () => {
    const { host, view } = mount();
    view.show();
    await view.open(DRAFT);

    const expected = new Map([
      [".zc-qmd-back", "Back to AI"],
      [".zc-qmd-quickopen-button", "Open a QMD"],
      [".zc-qmd-compliance", "Draft checks passed"],
      [".zc-qmd-review", "Add to Knowledge"],
      [".zc-qmd-compare", "No AI version to compare"],
      [".zc-qmd-change-keep", "No AI changes to keep"],
      [".zc-qmd-edit-external", "Edit in Cursor"],
      [".zc-qmd-refresh", "Refresh Preview"],
    ]);
    for (const [selector, label] of expected) {
      const button = host.querySelector<HTMLButtonElement>(selector)!;
      expect(button.textContent!.length).toBeLessThanOrEqual(2);
      expect(button.getAttribute("aria-label")).toContain(label);
      expect(button.title).toContain(label);
    }
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-compliance")!.textContent)
      .not.toBe(host.querySelector<HTMLButtonElement>(".zc-qmd-change-keep")!.textContent);
    view.destroy();
  });

  it("switches the compiled preview between the original and the one latest AI version", async () => {
    (document as unknown as { createXULElement(name: string): HTMLElement }).createXULElement =
      vi.fn(() => document.createElement("div"));
    const { host, view, changeRenderService, refreshChangePreview, setPending } = mount();
    view.show();
    await view.open(DRAFT);
    view.syncAgentChanges({ activeTurnId: "turn-1", diffs: [] });
    await settle();

    setPending(true, "first-edit");
    view.syncAgentChanges({
      activeTurnId: "turn-1",
      diffs: [{
        turnId: "turn-1",
        diff: `diff --git a/${CHANGE} b/${CHANGE}\n--- a/${CHANGE}\n+++ b/${CHANGE}\n@@ -7 +7 @@\n-Old paragraph.\n+New paragraph.`,
      }],
    });
    await settle();

    const eye = host.querySelector<HTMLButtonElement>(".zc-qmd-compare")!;
    const browser = host.querySelector<HTMLElement>(".zc-qmd-render-browser")!;
    expect(eye.disabled).toBe(false);
    expect(refreshChangePreview).toHaveBeenCalledWith(DRAFT, CHANGE, CHANGE_PREVIEW);
    expect(changeRenderService.open).toHaveBeenCalledWith(
      expect.objectContaining({ id: "drafts" }),
      "/repo",
      CHANGE_PREVIEW,
    );
    expect(browser.getAttribute("src")).toContain("127.0.0.1:44100");

    eye.click();
    await settle();
    expect(browser.getAttribute("src")).toContain("127.0.0.1:44200");
    expect(eye.getAttribute("aria-pressed")).toBe("true");
    eye.click();
    await settle();
    expect(browser.getAttribute("src")).toContain("127.0.0.1:44100");
    expect(eye.getAttribute("aria-pressed")).toBe("false");
    view.destroy();
  });

  it("Keep promotes only the latest cumulative AI version and clears review state", async () => {
    (document as unknown as { createXULElement(name: string): HTMLElement }).createXULElement =
      vi.fn(() => document.createElement("div"));
    const { host, view, keepChange, refreshChangePreview, setPending } = mount();
    view.show();
    await view.open(DRAFT);
    view.syncAgentChanges({ activeTurnId: "turn-2", diffs: [] });
    await settle();
    setPending(true, "first-edit");
    view.syncAgentChanges({
      activeTurnId: "turn-2",
      diffs: [{
        turnId: "turn-2",
        diff: `diff --git a/${CHANGE} b/${CHANGE}\n--- a/${CHANGE}\n+++ b/${CHANGE}\n@@\n-Old paragraph.\n+First edit.`,
      }],
    });
    await settle();
    setPending(true, "latest-edit");
    view.syncAgentChanges({
      activeTurnId: "turn-2",
      diffs: [{
        turnId: "turn-2",
        diff: `diff --git a/${CHANGE} b/${CHANGE}\n--- a/${CHANGE}\n+++ b/${CHANGE}\n@@\n-Old paragraph.\n+Latest edit.`,
      }],
    });
    await settle();

    expect(refreshChangePreview.mock.calls.length).toBeGreaterThanOrEqual(2);
    host.querySelector<HTMLButtonElement>(".zc-qmd-change-keep")!.click();
    await settle();
    expect(keepChange).toHaveBeenCalledOnce();
    expect(keepChange).toHaveBeenCalledWith(DRAFT, CHANGE);
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-compare")!.disabled).toBe(true);
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-change-keep")!.disabled).toBe(true);
    expect(host.querySelector(`[data-path="${DRAFT}"] .zc-qmd-pending-dot`)).toBeNull();
    view.destroy();
  });

  it("restores a persisted pending version and marks its Draft tree with green dots", async () => {
    (document as unknown as { createXULElement(name: string): HTMLElement }).createXULElement =
      vi.fn(() => document.createElement("div"));
    const { host, view, changeRenderService } = mount(
      [CURSOR, VSCODE],
      { pending: true, indexedPending: true },
    );
    view.show();
    await view.open(DRAFT);
    await settle();

    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-compare")!.disabled).toBe(false);
    expect(changeRenderService.open).toHaveBeenCalledWith(
      expect.objectContaining({ id: "drafts" }),
      "/repo",
      CHANGE_PREVIEW,
    );
    expect(host.querySelector(`[data-path="drafts"] .zc-qmd-pending-dot`)).not.toBeNull();
    expect(host.querySelector(`[data-path="drafts/Dynamics"] .zc-qmd-pending-dot`)).not.toBeNull();
    view.destroy();
  });

  it("does nothing when the eye is clicked without a pending AI version", async () => {
    (document as unknown as { createXULElement(name: string): HTMLElement }).createXULElement =
      vi.fn(() => document.createElement("div"));
    const { host, view, changeRenderService } = mount();
    view.show();
    await view.open(DRAFT);
    const eye = host.querySelector<HTMLButtonElement>(".zc-qmd-compare")!;
    expect(eye.disabled).toBe(true);
    eye.click();
    await settle();
    expect(changeRenderService.open).not.toHaveBeenCalled();
    view.destroy();
  });

  it("detects a saved Git-ignored working copy from its content fingerprint", async () => {
    (document as unknown as { createXULElement(name: string): HTMLElement }).createXULElement =
      vi.fn(() => document.createElement("div"));
    const { host, view, setPending, refreshChangePreview } = mount();
    view.show();
    await view.open(DRAFT);
    view.syncAgentChanges({ activeTurnId: "turn-hidden", diffs: [] });
    await settle();

    setPending(true, "changed-without-git-diff");
    view.syncAgentChanges({ activeTurnId: "turn-hidden", diffs: [] });
    await settle();

    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-compare")!.disabled).toBe(false);
    expect(refreshChangePreview).toHaveBeenCalledWith(DRAFT, CHANGE, CHANGE_PREVIEW);
    expect(host.querySelector(`[data-path="drafts"] .zc-qmd-pending-dot`)).not.toBeNull();
    view.destroy();
  });

  it("clears pending dots when the working copy returns to the Draft baseline", async () => {
    (document as unknown as { createXULElement(name: string): HTMLElement }).createXULElement =
      vi.fn(() => document.createElement("div"));
    const { host, view, setPending } = mount();
    view.show();
    await view.open(DRAFT);

    setPending(true, "changed-revision");
    view.syncAgentChanges({ activeTurnId: "turn-restore", diffs: [] });
    await settle();
    expect(host.querySelector('[data-path="drafts"] .zc-qmd-pending-dot')).not.toBeNull();

    setPending(false, "original-revision-again");
    view.syncAgentChanges({ activeTurnId: "turn-restore", diffs: [] });
    await settle();
    expect(host.querySelector('[data-path="drafts"] .zc-qmd-pending-dot')).toBeNull();
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-compare")!.disabled).toBe(true);
    view.destroy();
  });

  it("does not attach another paper or Draft's Agent diff to the visible Draft", async () => {
    const { host, view, changeRenderService } = mount();
    view.show();
    await view.open(DRAFT);
    view.syncAgentChanges({ activeTurnId: "turn-other", diffs: [] });
    await settle();
    view.syncAgentChanges({
      activeTurnId: "turn-other",
      diffs: [{
        turnId: "turn-other",
        diff: "diff --git a/drafts/other.qmd b/drafts/other.qmd\n--- a/drafts/other.qmd\n+++ b/drafts/other.qmd\n-old\n+new",
      }],
    });
    await settle();
    expect(host.querySelector<HTMLButtonElement>(".zc-qmd-compare")!.disabled).toBe(true);
    expect(changeRenderService.open).not.toHaveBeenCalled();
    view.destroy();
  });
});

describe("QMD Agent diff helpers", () => {
  it("extracts only the active Draft from a multi-file turn diff", () => {
    const diff = [
      "diff --git a/drafts/other.qmd b/drafts/other.qmd",
      "--- a/drafts/other.qmd",
      "+++ b/drafts/other.qmd",
      "-other old",
      "+other new",
      `diff --git a/${DRAFT} b/${DRAFT}`,
      `--- a/${DRAFT}`,
      `+++ b/${DRAFT}`,
      "-Old paragraph.",
      "+New paragraph.",
    ].join("\n");
    const selected = qmdDiffForPath(diff, DRAFT)!;
    expect(selected).toContain("New paragraph.");
    expect(selected).not.toContain("other new");
  });
});
