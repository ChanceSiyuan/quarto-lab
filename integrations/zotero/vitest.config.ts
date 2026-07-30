import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    setupFiles: ["./test/setup-dom.ts"],
    // `test/visual/` runs under node:test in a real browser (`npm run
    // test:visual`). It measures layout, which no DOM shim provides, so it
    // cannot run here.
    exclude: ["**/node_modules/**", "**/build/**", "**/dist/**", "test/visual/**"],
  },
});
