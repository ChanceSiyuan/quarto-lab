import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "next-env.d.ts",
  ]),
  // Generated output. ESLint 9's flat config does not read `.gitignore`, so
  // every directory a build writes has to be named here or `eslint .` lints
  // Quarto's bundled Bootstrap, Fuse, and Popper instead of this repository's
  // source. All of these are gitignored and reproducible: `dist/` is the
  // Worker bundle, `public/knowledge/` is the rendered knowledge site,
  // `.generated/` is the problem index the console reads, `drafts/.preview/`
  // is the untrusted-draft preview, `work/` holds render workspaces, and
  // `integrations/zotero/` is a standalone add-on with its own type-check and
  // test configuration. The rest are test and Wrangler artefacts.
  globalIgnores([
    "dist/**",
    "public/knowledge/**",
    ".generated/**",
    "drafts/.preview/**",
    "drafts/.quarto/**",
    "work/**",
    "integrations/zotero/**",
    ".wrangler/**",
    "playwright-report/**",
    "test-results/**",
    ".research-loop/tests/e2e/.screenshots-actual/**",
  ]),
]);

export default eslintConfig;
