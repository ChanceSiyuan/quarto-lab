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
    "build/**",
    "next-env.d.ts",
  ]),
  // Generated output. ESLint 9's flat config does not read `.gitignore`, so
  // every directory a build writes has to be named here or `eslint .` lints
  // Quarto's bundled Bootstrap, Fuse, and Popper instead of this repository's
  // source. All of these are gitignored and reproducible: `dist/` is the
  // Worker bundle, `public/knowledge/` is the rendered knowledge site,
  // `drafts/.preview/` is the untrusted-draft preview, `work/` holds render
  // workspaces, and the rest are test and Wrangler artefacts.
  globalIgnores([
    "dist/**",
    "public/knowledge/**",
    "drafts/.preview/**",
    "drafts/.quarto/**",
    "work/**",
    ".wrangler/**",
    "playwright-report/**",
    "test-results/**",
    "tests/e2e/.screenshots-actual/**",
  ]),
  {
    // The dashboard under `app/` is preserved verbatim from the starter
    // (commit 425843c) and is frozen by plan constraint: the knowledge system
    // may add pages and tests around it, but may not edit its source. Its
    // hydration effect reads `localStorage` and calls `setState`, which
    // `react-hooks/set-state-in-effect` reports. The rule is disabled for this
    // one preserved file rather than repository-wide, so any *new* component
    // still gets the warning.
    files: ["app/page.tsx"],
    rules: {
      "react-hooks/set-state-in-effect": "off",
    },
  },
]);

export default eslintConfig;
