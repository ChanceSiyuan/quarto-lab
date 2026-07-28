# GitHub Pages Showcase Design

Date: 2026-07-27
Status: Approved in conversation

## Purpose

Publish the existing static `QMB-001` research example as a GitHub Pages
showcase for `https://nzy1997.github.io/research-loop/`.

The Pages version is a static demonstration of the current repository-backed
example. It must not run research, start agents, create worktrees, import
AutoQEC, read datasets, or add a separate hosting service.

## Approach

Use a GitHub Pages-specific snapshot build instead of changing the main
vinext/Next runtime:

- keep the existing local/dev app unchanged;
- run the normal problem index build and vinext production build;
- render the known showcase routes through the built worker;
- emit static HTML files under `out/`;
- copy client assets from `dist/client`;
- rewrite root-relative links for the repository Pages base path
  `/research-loop`;
- strip runtime scripts from the snapshot so Pages navigation is plain static
  HTML; and
- deploy `out/` with the official GitHub Pages Actions flow.

GitHub's Pages documentation recommends building static files, uploading them
with `actions/upload-pages-artifact`, and deploying with `actions/deploy-pages`.

Reference: <https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site>

## Routes

The showcase publishes these static routes:

- `/`
- `/problems/QMB-001`
- `/problems/QMB-001/attempts/ATT-001`
- `/problems/QMB-001/attempts/ATT-002`
- `/problems/QMB-001/attempts/ATT-003`
- `/problems/QMB-001/attempts/ATT-004`
- `/problems/QMB-001/attempts/ATT-005`

The static output writes each route as an `index.html` file so GitHub Pages can
serve clean paths.

## Files

- `scripts/build-pages-showcase.mjs`: builds vinext output, snapshots the known
  routes, copies client assets, rewrites links, and writes `out/.nojekyll`.
- `.github/workflows/pages.yml`: installs dependencies, runs tests/build,
  creates the static showcase, uploads `out/`, and deploys Pages.
- `package.json`: adds a `pages:build` script.
- `tests/pages-showcase.test.mjs`: verifies the snapshot builder output shape,
  base-path rewrites, script stripping, and static route files.
- `README.md`: records the Pages command and deployment target.

## Testing

Automated checks:

- `npm test` keeps the app, data helpers, build, and rendered routes green.
- `npm run pages:build` creates the GitHub Pages artifact.
- `node --test tests/pages-showcase.test.mjs` verifies static output.
- `npm run lint` verifies source quality.

Manual smoke:

- serve `out/` locally;
- open `/research-loop/`;
- click `QMB-001`;
- click an attempt, especially `ATT-004` or `ATT-005`.

## Completion

The work is complete when:

- the static artifact is generated in `out/`;
- GitHub Actions workflow for Pages exists;
- tests and lint pass;
- changes are committed and pushed; and
- the user can enable or view Pages at
  `https://nzy1997.github.io/research-loop/`.
