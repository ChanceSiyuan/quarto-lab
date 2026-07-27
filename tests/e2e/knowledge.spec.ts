/**
 * The published knowledge site, in a browser.
 *
 * These tests run against `tests/fixtures/knowledge/valid`, rendered by
 * `npm run build:e2e`: the committed tree holds only what a user has actually
 * promoted, and the things worth checking in a browser — mathematics, a
 * citation resolved against the bibliography, an image beside its page, a
 * nested topic — are exactly what the fixture has and the real tree does not
 * yet.
 *
 * Two questions are being asked. Does everything the build published arrive at
 * its URL, stylesheets and search index included? And does everything the build
 * deliberately did *not* publish stay unreachable — the untrusted drafts, the
 * external literature, the local-only downloads under it, and the source pages
 * themselves? The second half is the point of the whole knowledge boundary, so
 * it is asserted against real 404s rather than against the absence of a file.
 */

import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { expect, test, type Page } from "@playwright/test";

const repoRoot = path.resolve(fileURLToPath(import.meta.url), "..", "..", "..");

/** The three generated category views, and the fixture page each one lists. */
const CATEGORY_VIEWS = [
  { slug: "theory", title: "Theory", page: "Proof of the critical temperature" },
  { slug: "experiment", title: "Experiment", page: "Proposal for a finite-size study" },
  { slug: "codes", title: "Codes", page: "Verified transfer-matrix code" },
] as const;

/**
 * The one 404 a healthy Quarto page still produces.
 *
 * `quarto-listing.js` probes for a site-wide listings index on every page it
 * runs on. This site generates no listings, the projection may not add files
 * Quarto did not render, and the page works without it — so it is tolerated by
 * name rather than by relaxing the check.
 */
const TOLERATED_MISSING = "/knowledge/listings.json";

/**
 * Records every response the page received that a browser would treat as a
 * broken asset. The knowledge pages link their stylesheets and scripts
 * relatively, so a route that resolves one directory too high still renders —
 * it just renders unstyled, which only a check like this notices.
 */
function trackBrokenRequests(page: Page): string[] {
  const broken: string[] = [];
  page.on("response", (response) => {
    const { pathname } = new URL(response.url());
    if (response.status() >= 400 && pathname !== TOLERATED_MISSING) {
      broken.push(`${response.status()} ${pathname}`);
    }
  });
  page.on("requestfailed", (request) => {
    const url = new URL(request.url());
    // Only same-origin failures are this site's business; MathJax is loaded
    // from a CDN that a sandboxed run may not reach.
    if (url.host === new URL(page.url() || "http://127.0.0.1:4173").host) {
      broken.push(`failed ${url.pathname}`);
    }
  });
  return broken;
}

test.describe("published knowledge site", () => {
  test("the index names the site and offers search", async ({ page }) => {
    const broken = trackBrokenRequests(page);
    await page.goto("/knowledge/");

    await expect(page).toHaveTitle("Research Loop Knowledge");
    await expect(page.locator(".sidebar-title")).toHaveText("Research Loop Knowledge");
    await expect(page.locator("#quarto-search")).toBeVisible();
    await expect(page.locator("#quarto-search").locator("input, button").first()).toBeVisible();

    // The curated reading map, and the generated category section beneath it.
    await expect(page.locator("#quarto-sidebar")).toContainText("Ising model");
    await expect(page.locator("#quarto-sidebar")).toContainText("Categories");
    expect(broken).toEqual([]);
  });

  test("the ising topic renders its mathematics, citation, and figure", async ({ page }) => {
    const broken = trackBrokenRequests(page);
    await page.goto("/knowledge/ising/");

    await expect(page.locator("h1.title")).toHaveText("Ising model");
    await expect(page.locator("#reading-map")).toContainText("Proof of the critical temperature");

    await page.getByRole("link", { name: "Proof of the critical temperature" }).first().click();
    await expect(page).toHaveURL(/\/knowledge\/ising\/proof\.html$/);

    // The citation was resolved against the fixture bibliography, and the
    // entry it points at is rendered on the page.
    const citation = page.locator('.citation[data-cites="fixture2026"]');
    await expect(citation).toBeVisible();
    await expect(citation).toContainText("Fixture and Sample 2026");
    await expect(page.locator("#ref-fixture2026")).toContainText("Journal of Fixtures");

    // The figure is an asset copied next to its page, and the browser fetched
    // it: a broken relative path would leave the image with no intrinsic size.
    const figure = page.locator("figure img");
    await expect(figure).toBeVisible();
    await expect(page.locator("figcaption")).toContainText(
      "Phase diagram of the two-dimensional Ising model",
    );
    expect(await figure.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0);

    await page.goto("/knowledge/ising/proposal.html");
    await expect(page.locator("#quarto-document-content")).toContainText(
      "Measuring the Binder cumulant",
    );
    // Whether or not MathJax reaches its CDN, the mathematics is on the page:
    // as the TeX Quarto emitted, or as the container MathJax replaces it with.
    await expect(page.locator(".math.inline, mjx-container").first()).toBeVisible();
    const source = await (await page.request.get("/knowledge/ising/proposal.html")).text();
    expect(source).toContain("\\(L = 128\\)");

    expect(broken).toEqual([]);
  });

  test("every category view lists its curated pages", async ({ page }) => {
    for (const view of CATEGORY_VIEWS) {
      const broken = trackBrokenRequests(page);
      await page.goto(`/knowledge/categories/${view.slug}/`);

      await expect(page.locator("h1.title")).toHaveText(view.title);
      await expect(page.locator("#quarto-document-content")).toContainText(view.page);
      await expect(page.getByRole("link", { name: view.page })).toHaveCount(2);
      expect(broken).toEqual([]);
    }
  });

  test("a page alias redirects to the page it names", async ({ page }) => {
    // Quarto publishes every alias as its own redirect directory, including one
    // whose name contains a space; both land on the topic they alias.
    for (const alias of ["/knowledge/ising/ising/", "/knowledge/ising/2d ising/"]) {
      await page.goto(alias);
      await expect(page).toHaveURL(/\/knowledge\/ising\/index\.html$/);
      await expect(page.locator("h1.title")).toHaveText("Ising model");
    }
  });

  test("nested stylesheets and the search index are served", async ({ page }) => {
    const stylesheet = await page.request.get(
      "/knowledge/site_libs/bootstrap/bootstrap-icons.css",
    );
    expect(stylesheet.status()).toBe(200);
    expect(stylesheet.headers()["content-type"]).toMatch(/text\/css/);

    const search = await page.request.get("/knowledge/search.json");
    expect(search.status()).toBe(200);
    const documents = (await search.json()) as { title: string; href: string }[];
    expect(documents.map((entry) => entry.title)).toContain("Ising model");

    // The deepest published page still reaches the site libraries above it.
    const broken = trackBrokenRequests(page);
    await page.goto("/knowledge/categories/theory/");
    const stylesheets = await page.evaluate(() =>
      [...document.querySelectorAll<HTMLLinkElement>('link[rel="stylesheet"]')].map(
        (link) => new URL(link.href).pathname,
      ),
    );
    expect(stylesheets.some((href) => href.startsWith("/knowledge/site_libs/"))).toBe(true);
    expect(broken).toEqual([]);
  });

  test("nothing outside the published site is reachable", async ({ page }) => {
    /**
     * Each entry is a path someone might guess, and a string that only appears
     * in the file behind it. The marker is checked against the real file first,
     * so "the response did not contain it" cannot pass by the marker having
     * gone stale.
     */
    const forbidden = [
      { url: "/drafts/", file: null, marker: null },
      {
        url: "/drafts/imported-quantum-harness/method-property-map.md",
        file: "drafts/imported-quantum-harness/method-property-map.md",
        marker: "Method ↔ Property Map",
      },
      {
        url: "/drafts/.preview/smoke/imported-quantum-harness/conventions.html",
        file: null,
        marker: null,
      },
      { url: "/literature/", file: null, marker: null },
      { url: "/literature/ref.bib", file: "literature/ref.bib", marker: "@article" },
      { url: "/literature/ed/.raw/", file: null, marker: null },
      { url: "/literature/ed/.raw/weinberg_2016_quspin/source.tar.gz", file: null, marker: null },
      { url: "/literature/ed/.figures/weinberg_2016_quspin/", file: null, marker: null },
      {
        url: "/knowledge/ising/proof.qmd",
        file: "tests/fixtures/knowledge/valid/ising/proof.qmd",
        marker: "[@fixture2026]",
      },
      { url: "/knowledge/references/ref.bib", file: null, marker: "@article" },
    ];

    for (const { url, file, marker } of forbidden) {
      if (file !== null && marker !== null) {
        const contents = await readFile(path.join(repoRoot, file), "utf8");
        expect(contents, `${file} no longer contains ${marker}`).toContain(marker);
      }

      const response = await page.request.get(url);
      expect(response.status(), `${url} is not a 404`).toBe(404);

      const body = await response.text();
      expect(body.length).toBeLessThan(2048);
      if (marker !== null) {
        expect(body, `${url} leaked file contents`).not.toContain(marker);
      }
    }
  });
});
