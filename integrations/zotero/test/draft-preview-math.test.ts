import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

// Visual Edit renders math with the plugin's bundled KaTeX. The compiled
// draft preview must use the same engine or formula metrics diverge
// (spec: Design 2, component 1).
describe("draft preview math engine", () => {
  it("compiles draft previews with KaTeX, the engine Visual Edit bundles", () => {
    const config = readFileSync(join(process.cwd(), "..", "..", "drafts", "_quarto.yml"), "utf8");
    expect(config).toMatch(/html-math-method:\s*katex/);
  });

  it("leaves the published knowledge site's math pipeline unchanged", () => {
    const config = readFileSync(join(process.cwd(), "..", "..", "knowledge", "_quarto.yml"), "utf8");
    expect(config).not.toMatch(/html-math-method/);
  });
});
