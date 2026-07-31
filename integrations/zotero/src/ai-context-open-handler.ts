export interface AIContextOpenHandler {
  readonly supported: boolean;
  dispose(): void;
}

export function installAIContextOpenHandler(
  fileHandlers: { open?: (...args: any[]) => any } | null | undefined,
  callbacks: {
    isCandidate(item: unknown): boolean;
    openAIContext(item: unknown): unknown;
  },
): AIContextOpenHandler {
  const original = fileHandlers?.open;
  if (!fileHandlers || typeof original !== "function") {
    return { supported: false, dispose() {} };
  }

  let active = true;
  const wrapper = function (this: unknown, ...args: any[]): any {
    if (!active) return original.apply(this, args);

    let candidate: boolean;
    try {
      candidate = callbacks.isCandidate(args[0]);
    } catch {
      return original.apply(this, args);
    }
    if (!candidate) return original.apply(this, args);
    return callbacks.openAIContext(args[0]);
  };
  fileHandlers.open = wrapper;

  return {
    supported: true,
    dispose(): void {
      if (!active) return;
      active = false;
      if (fileHandlers.open === wrapper) fileHandlers.open = original;
    },
  };
}
