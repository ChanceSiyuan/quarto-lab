import { expect, it, vi } from "vitest";
import { installAIContextOpenHandler } from "../src/ai-context-open-handler";

it("intercepts only linked qmd candidates and delegates everything else exactly", async () => {
  const candidate = { key: "A1", path: "/repo/drafts/ai-contexts/ctx.qmd" };
  const other = { key: "PDF1", path: "/repo/literature/paper.pdf" };
  const original = vi.fn(function (this: unknown, ...args: unknown[]) {
    return { receiver: this, args };
  });
  const fileHandlers: { open: (...args: unknown[]) => unknown } = { open: original };
  const openAIContext = vi.fn(async () => "qlab-opened");
  const installed = installAIContextOpenHandler(fileHandlers, {
    isCandidate: (item) => item === candidate,
    openAIContext,
  });
  const receiver = { fileHandlers };

  expect(await fileHandlers.open.call(receiver, candidate, { page: 2 })).toBe("qlab-opened");
  expect(fileHandlers.open.call(receiver, other, { page: 2 })).toEqual({
    receiver,
    args: [other, { page: 2 }],
  });
  installed.dispose();
  expect(fileHandlers.open).toBe(original);
});

it("becomes inert beneath a later plugin wrapper and stays safe across reload", () => {
  const original = vi.fn((..._args: unknown[]) => "native");
  const fileHandlers: { open: (...args: unknown[]) => unknown } = { open: original };
  const callbacks = { isCandidate: vi.fn(() => true), openAIContext: vi.fn(() => "qlab") };
  const first = installAIContextOpenHandler(fileHandlers, callbacks);
  const qlabWrapper = fileHandlers.open;
  fileHandlers.open = function laterWrapper(...args: unknown[]) {
    return qlabWrapper.apply(this, args);
  };

  first.dispose();
  expect(fileHandlers.open({})).toBe("native");
  expect(callbacks.openAIContext).not.toHaveBeenCalled();
  const second = installAIContextOpenHandler(fileHandlers, callbacks);
  second.dispose();
  expect(fileHandlers.open({})).toBe("native");
});

it.each([
  [undefined],
  [null],
  [{}],
])("degrades safely when FileHandlers.open is unavailable", (fileHandlers) => {
  const callbacks = { isCandidate: vi.fn(() => true), openAIContext: vi.fn(() => "qlab") };
  const installed = installAIContextOpenHandler(fileHandlers as any, callbacks);

  expect(installed.supported).toBe(false);
  installed.dispose();
  installed.dispose();
  expect(callbacks.isCandidate).not.toHaveBeenCalled();
});

it("preserves original sync return, this, and every argument", () => {
  const receiver = { name: "receiver" };
  const original = vi.fn(function (this: unknown, ...args: unknown[]) {
    return { receiver: this, args };
  });
  const fileHandlers = { open: original };
  installAIContextOpenHandler(fileHandlers, {
    isCandidate: () => false,
    openAIContext: () => "qlab",
  });

  expect(fileHandlers.open.call(receiver, "pdf", { page: 4 }, 17)).toEqual({
    receiver,
    args: ["pdf", { page: 4 }, 17],
  });
});

it("preserves the original rejection object", async () => {
  const rejection = new Error("native failure");
  const original = vi.fn((..._args: unknown[]) => Promise.reject(rejection));
  const fileHandlers = { open: original };
  installAIContextOpenHandler(fileHandlers, {
    isCandidate: () => false,
    openAIContext: () => "qlab",
  });

  await expect(fileHandlers.open({ key: "PDF" })).rejects.toBe(rejection);
});

it("delegates safely when candidate detection throws", () => {
  const original = vi.fn((..._args: unknown[]) => "native");
  const fileHandlers = { open: original };
  const openAIContext = vi.fn(() => "qlab");
  installAIContextOpenHandler(fileHandlers, {
    isCandidate: () => { throw new Error("predicate failure"); },
    openAIContext,
  });

  expect(fileHandlers.open({})).toBe("native");
  expect(original).toHaveBeenCalledOnce();
  expect(openAIContext).not.toHaveBeenCalled();
});

it("dispose is idempotent and restores only this installation by identity", () => {
  const original = vi.fn(() => "native");
  const fileHandlers = { open: original };
  const installed = installAIContextOpenHandler(fileHandlers, {
    isCandidate: () => true,
    openAIContext: () => "qlab",
  });

  installed.dispose();
  installed.dispose();
  expect(fileHandlers.open).toBe(original);
});
