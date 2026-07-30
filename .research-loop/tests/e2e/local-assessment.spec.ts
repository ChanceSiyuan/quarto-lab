import { expect, test } from "@playwright/test";

import {
  LOCAL_ASSESSMENT_AMBIGUOUS_PROBLEM_ID,
  LOCAL_ASSESSMENT_COMPLETE_PROBLEM_ID,
  LOCAL_ASSESSMENT_QUANTUM_PROBLEM_ID,
} from "./local-assessment-fixture";

test("runs local assessment and opens generated report", async ({ context, page }) => {
  await page.goto(`/problems/${LOCAL_ASSESSMENT_COMPLETE_PROBLEM_ID}`);
  await expect(page.getByRole("heading", { name: "No assessment yet" })).toBeVisible();

  await page.getByRole("button", { name: "Run assessment" }).click();
  await expect(
    page.getByRole("heading", { name: /Assessment queued|Assessment running|Assessment complete/ }),
  ).toBeVisible();
  await expect(page.getByText("Recommendation", { exact: true })).toBeVisible({ timeout: 120_000 });

  const reportLink = page.getByRole("link", { name: /Open detailed report/ });
  await expect(reportLink).toBeVisible();
  const reportHref = await reportLink.getAttribute("href");
  expect(reportHref).toMatch(/^\/__local\/assessments\/reports\//);

  const report = await context.newPage();
  await report.goto(reportHref ?? "");
  await expect(report.getByRole("heading", { name: /Research Problem Assessment/ })).toBeVisible();
  await expect(report.getByRole("heading", { name: "Research Value Audit" })).toBeVisible();
  await expect(report.getByText(`Fake Codex completed assessment for ${LOCAL_ASSESSMENT_COMPLETE_PROBLEM_ID}.`)).toBeVisible();
});

test("requires explicit resolver selection for ambiguous knowledge", async ({ page }) => {
  await page.goto(`/problems/${LOCAL_ASSESSMENT_AMBIGUOUS_PROBLEM_ID}`);
  await page.getByRole("button", { name: "Run assessment" }).click();

  await expect(page.getByRole("heading", { name: "Knowledge match needs input" })).toBeVisible({ timeout: 120_000 });
  await page.getByLabel(/knowledge\/quantum_complexity\/counting_complexity\.qmd/).check();
  await page.getByRole("button", { name: "Continue assessment" }).click();

  await expect(page.getByRole("heading", { name: /Assessment complete|Assessment may be stale/ })).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("Recommendation", { exact: true })).toBeVisible();
});

test("researches quantum valuation evidence, freezes a snapshot, and runs v2 assessment", async ({ context, page }) => {
  test.setTimeout(120_000);
  await page.goto(`/problems/${LOCAL_ASSESSMENT_QUANTUM_PROBLEM_ID}`);

  await page.getByRole("button", { name: "Research evidence" }).click();
  await expect(page.getByRole("heading", { name: "Review valuation assumptions" })).toBeVisible({ timeout: 120_000 });
  await page.getByLabel(/Selected reference paper/).first().check();
  await page.getByRole("button", { name: "Confirm and freeze snapshot" }).click();
  await expect(page.getByText("Evidence ready")).toBeVisible({ timeout: 120_000 });

  await page.getByRole("button", { name: "Run assessment" }).click();
  await expect(page.getByRole("heading", { name: "Knowledge match needs input" })).toBeVisible();
  await page.getByLabel(/Continue with external valuation evidence only/).check();
  await page.getByRole("button", { name: "Continue assessment" }).click();
  await expect(page.getByText("Scientific Demand Score", { exact: true })).toBeVisible({ timeout: 120_000 });
  await expect(page.getByText("Industry \/ social proxy", { exact: true })).toBeVisible();

  const reportHref = await page.getByRole("link", { name: /Open detailed report/ }).getAttribute("href");
  const report = await context.newPage();
  await report.goto(reportHref ?? "");
  await expect(report.getByText("External valuation evidence")).toBeVisible();
  await expect(report.getByText(/\d{8}T\d{6}Z-[a-f0-9]{12}/)).toBeVisible();
  await expect(report.getByText("Formula audit")).toBeVisible();
  await expect(report.getByText("Scientific Demand Score", { exact: true })).toBeVisible();
  await expect(report.getByText("Problem Literature Set", { exact: true })).toBeVisible();
  await expect(report.getByText(/0 citations/)).toHaveCount(0);
  await expect(report.getByText("4242424242")).toHaveCount(0);
});
