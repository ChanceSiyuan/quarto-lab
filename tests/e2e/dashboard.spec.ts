/**
 * The dashboard, in a browser.
 *
 * `app/` is preserved verbatim from the starter and may not be edited by this
 * project, so these tests are a fence around it: they describe what it does
 * today — the pipeline advances, the run is remembered on the device, and Reset
 * puts it back — and the visual baseline pins what it looks like while doing it.
 * Nothing here may be "fixed" by changing the dashboard.
 *
 * The clock is deliberately never asserted. Every advance stamps the audit
 * entry with the local time, so its value is the one part of this page that a
 * test cannot own.
 */

import { expect, test } from "@playwright/test";

/** The persisted demo state, and the only storage this page uses. */
const STORAGE_KEY = "research-loop-demo";

/** The audit entries the dashboard starts with. */
const INITIAL_ACTIVITY = [
  "Executable interval-arithmetic gate created",
  "Candidate accepted by automatic quality rubric",
  "Literature mining completed across 18 papers",
];

/** What advancing out of Verify writes to the audit trail. */
const VERIFY_AUDIT_ENTRY = "Novelty check passed against the challenge catalog";

/** Waits for the client to have hydrated and applied any stored state. */
async function ready(page: import("@playwright/test").Page, stage: string) {
  await expect(page.locator(".stage-card.active h3")).toHaveText(stage);
}

test.describe("research dashboard", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("renders the signed-off layout", async ({ page }) => {
    await ready(page, "Verify");
    await expect(page.locator("h1")).toContainText("Turn open literature into");
    await expect(page).toHaveScreenshot("dashboard.png", {
      fullPage: true,
      animations: "disabled",
    });
  });

  test("starts on Verify with the default audit trail", async ({ page }) => {
    await ready(page, "Verify");

    await expect(page.locator(".stage-card").nth(0)).toHaveClass(/complete/);
    await expect(page.locator(".stage-card").nth(1)).toHaveClass(/active/);
    await expect(page.locator(".stage-card").nth(2)).toHaveClass(/pending/);
    await expect(page.locator(".stage-card").nth(3)).toHaveClass(/pending/);
    await expect(page.locator(".progress-label")).toHaveText("50% complete");
    await expect(page.locator(".command-card h2")).toHaveText("Launch solver run");

    const entries = page.locator(".activity-item p");
    await expect(entries).toHaveText(INITIAL_ACTIVITY);
  });

  test("advances to Solve, persists across a reload, and resets", async ({ page }) => {
    await ready(page, "Verify");

    await page.getByRole("button", { name: "Launch solver run" }).click();

    await ready(page, "Solve");
    await expect(page.locator(".command-card h2")).toHaveText("Prepare review packet");
    await expect(page.locator(".activity-item p").first()).toHaveText(VERIFY_AUDIT_ENTRY);
    await expect(page.locator(".activity-item p")).toHaveText([
      VERIFY_AUDIT_ENTRY,
      ...INITIAL_ACTIVITY,
    ]);

    // The audit entry is timestamped, but the time is the clock's business.
    await expect(page.locator(".activity-item span").first()).toHaveText(/^\d{1,2}:\d{2}/);

    const stored = JSON.parse(
      (await page.evaluate((key) => window.localStorage.getItem(key), STORAGE_KEY)) ?? "null",
    ) as { stage: number; activity: { text: string }[] };
    expect(stored.stage).toBe(2);
    expect(stored.activity.map((entry) => entry.text)).toEqual([
      VERIFY_AUDIT_ENTRY,
      ...INITIAL_ACTIVITY,
    ]);

    await page.reload();

    await ready(page, "Solve");
    await expect(page.locator(".activity-item p")).toHaveText([
      VERIFY_AUDIT_ENTRY,
      ...INITIAL_ACTIVITY,
    ]);

    await page.getByRole("button", { name: "Reset demo" }).click();

    await ready(page, "Verify");
    await expect(page.locator(".command-card h2")).toHaveText("Launch solver run");
    await expect(page.locator(".activity-item p")).toHaveText(INITIAL_ACTIVITY);
  });
});
