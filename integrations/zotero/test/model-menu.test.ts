// @vitest-environment happy-dom

import { describe, expect, it } from "vitest";
import { defaultSelectableModel, renderModelOptions } from "../src/model-menu";

describe("renderModelOptions", () => {
  it("groups every model under the local Codex runtime", () => {
    const select = document.createElement("select");
    renderModelOptions(select, [
      { id: "gpt-5", label: "GPT-5" },
    ], "gpt-5");
    const groups = [...select.querySelectorAll("optgroup")].map((group) => group.label);
    expect(groups).toEqual(["Local Codex"]);
    expect(select.value).toBe("gpt-5");
  });

  it("omits an empty group", () => {
    const select = document.createElement("select");
    renderModelOptions(select, [], "");
    expect([...select.querySelectorAll("optgroup")]).toEqual([]);
  });
});

describe("defaultSelectableModel", () => {
  it("accepts a model literally named codex when the local CLI reports it", () => {
    expect(defaultSelectableModel([
      { id: "codex", label: "Codex(订阅)" },
      { id: "gpt-5", label: "GPT-5" },
    ])).toBe("codex");
  });

  it("prefers the isDefault entry over plain first-match", () => {
    expect(defaultSelectableModel([
      { id: "gpt-5", label: "GPT-5" },
      { id: "gpt-5-mini", label: "GPT-5 mini", isDefault: true },
    ])).toBe("gpt-5-mini");
  });

  it("falls back to the first non-placeholder model when none is isDefault", () => {
    expect(defaultSelectableModel([
      { id: "gpt-5", label: "GPT-5" },
      { id: "gpt-5-mini", label: "GPT-5 mini" },
    ])).toBe("gpt-5");
  });

  it("returns \"\" for an empty model list", () => {
    expect(defaultSelectableModel([])).toBe("");
  });
});
