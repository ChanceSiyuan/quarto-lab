import { describe, expect, it } from "vitest";

import { sha256Text } from "../src/text-sha256";

describe("pure text SHA-256", () => {
  it("matches the SHA-256 abc known vector", () => {
    expect(sha256Text("abc")).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
  });
});
