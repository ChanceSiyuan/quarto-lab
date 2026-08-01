import { afterEach, describe, expect, it, vi } from "vitest";
import { copyToClipboard, homePath, readTextFromClipboard } from "../src/platform";

describe("platform paths", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("resolves the home directory through Gecko's directory service", () => {
    const nsIFile = Symbol("nsIFile");
    const get = vi.fn(() => ({ path: "/Users/researcher" }));
    vi.stubGlobal("Services", { dirsvc: { get } });
    vi.stubGlobal("Components", { interfaces: { nsIFile } });
    vi.stubGlobal("PathUtils", { join: (...parts: string[]) => parts.join("/") });

    expect(homePath("Documents", "papers")).toBe("/Users/researcher/Documents/papers");
    expect(get).toHaveBeenCalledWith("Home", nsIFile);
  });
});

describe("copyToClipboard", () => {
  afterEach(() => {
    delete (globalThis as any).Components;
    vi.unstubAllGlobals();
  });

  it("copies via nsIClipboardHelper and falls back to navigator.clipboard", () => {
    const copyString = vi.fn();
    (globalThis as any).Components = {
      classes: { "@mozilla.org/widget/clipboardhelper;1": { getService: () => ({ copyString }) } },
      interfaces: { nsIClipboardHelper: {} },
    };
    expect(copyToClipboard("hello")).toBe(true);
    expect(copyString).toHaveBeenCalledWith("hello");
    delete (globalThis as any).Components;
    const writeText = vi.fn(() => Promise.resolve());
    vi.stubGlobal("navigator", { clipboard: { writeText } });
    expect(copyToClipboard("world")).toBe(true);
    expect(writeText).toHaveBeenCalledWith("world");
    vi.unstubAllGlobals();
  });

  it("returns false when neither the privileged helper nor navigator.clipboard is available", () => {
    vi.stubGlobal("navigator", {});
    expect(copyToClipboard("nowhere")).toBe(false);
  });
});

describe("readTextFromClipboard", () => {
  afterEach(() => {
    delete (globalThis as any).Components;
    vi.unstubAllGlobals();
  });

  it("reads Unicode only through Gecko's privileged clipboard APIs when explicitly invoked", () => {
    const getData = vi.fn((transferable) => {
      transferable.value = { QueryInterface: () => ({ data: "核心 🧪" }) };
    });
    const transferable = {
      init: vi.fn(),
      addDataFlavor: vi.fn(),
      getTransferData: vi.fn((_flavor, data) => { data.value = transferable.value; }),
      value: null as unknown,
    };
    (globalThis as any).Components = {
      classes: {
        "@mozilla.org/widget/clipboard;1": { getService: () => ({ getData, kGlobalClipboard: 1 }) },
        "@mozilla.org/widget/transferable;1": { createInstance: () => transferable },
      },
      interfaces: { nsIClipboard: {}, nsITransferable: {}, nsISupportsString: {} },
    };

    expect(getData).not.toHaveBeenCalled();
    expect(readTextFromClipboard()).toBe("核心 🧪");
    expect(transferable.init).toHaveBeenCalledWith(null);
    expect(transferable.addDataFlavor).toHaveBeenCalledWith("text/unicode");
    expect(getData).toHaveBeenCalledWith(transferable, 1);
  });

  it("returns null when the privileged clipboard service is unavailable without browser fallback", () => {
    const readText = vi.fn(() => Promise.resolve("must not be read"));
    vi.stubGlobal("navigator", { clipboard: { readText } });

    expect(readTextFromClipboard()).toBeNull();
    expect(readText).not.toHaveBeenCalled();
  });
});
