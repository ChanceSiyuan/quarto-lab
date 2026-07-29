import assert from "node:assert/strict";
import { describe, it } from "node:test";

import config, {
  ASSESSMENT_CODEX_BIN,
  FAKE_CODEX_EXECUTABLE,
} from "../../../playwright.assessment.config";

describe("assessment Playwright safety", () => {
  it("resolves codex to the repository fixture before the server can start", () => {
    assert.equal(ASSESSMENT_CODEX_BIN, FAKE_CODEX_EXECUTABLE);
    assert.ok(config.webServer);
  });
});
