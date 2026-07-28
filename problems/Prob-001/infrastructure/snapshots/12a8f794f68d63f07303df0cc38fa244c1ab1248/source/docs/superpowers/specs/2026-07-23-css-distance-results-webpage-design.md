# CSS Distance Results Webpage Design

## Goal

Create a polished, self-contained local webpage that summarizes the CSS
distance autoresearch evidence without exposing private benchmark material.
The page must make the established open-source comparison easy to read and
provide a complete, sortable view of all 100 proposal trials. Proposal 020 is
the only trial receiving visual emphasis.

## Deliverable

Write one standalone file at:

`results/css-distance-autoresearch-100/index.html`

The file embeds its styles, interaction code, and sanitized aggregate data. It
must work when opened directly from disk, without a server, network request,
build step, or external asset.

## Information Architecture

The page uses a compact research-report layout rather than generic dashboard
chrome.

1. A short title and methodology note explain that every reported witness is
   an upper-bound certificate, not an exact-distance result.
2. The first table compares only established open-source implementations from
   the public 19-instance ladder:
   - native `random-window-upper-bound`;
   - `codedistance/QDistRndMW`;
   - `codedistance/QDistEvol`; and
   - `codedistance/decoderDist`.
3. The second table contains exactly 100 rows, one for every proposal from 001
   through 100. Proposal 020 is the only highlighted row.
4. A compact footer records the source files, the 300-second per-invocation
   limit, and the fact that the sealed final holdout was not evaluated.

Proposal 020 must not appear in the open-source comparison table. This keeps
the public-ladder comparison scientifically separate from the blinded
development-trial table.

## Open-Source Comparison Table

The first table is computed from the checked-in public ladder comparison. It
contains these columns:

- implementation;
- cases;
- completed;
- target hits;
- timed out;
- total runtime;
- average runtime per case;
- median runtime per case; and
- short interpretation.

Timeout duration remains part of total and average runtime. Median is computed
over all 19 recorded invocations, including their observed timeout durations.
The table states this convention explicitly.

## One-Hundred-Trial Table

The second table contains these columns:

- proposal number;
- assigned method direction;
- decision;
- runs;
- completed/verified witnesses;
- target hits;
- timeouts;
- crashes;
- invalid claims;
- total runtime;
- average runtime per invocation;
- median runtime per invocation;
- 95th-percentile runtime; and
- normalized quality.

The page derives totals, decisions, counts, and quality from the committed
human-readable proposal reports. Median and 95th-percentile runtime are derived
from the evaluator's per-invocation records by an offline aggregation step. If
a proposal has no per-invocation timing records, the page displays an em dash;
it must never synthesize or estimate a quantile.

Proposal 020 receives a restrained accent background, a strong left rule, and
a `24/24 · fastest perfect` badge. No other row receives winner styling.

## Interaction

The standalone page provides lightweight, dependency-free JavaScript for:

- sorting both tables by clicking column headers;
- searching the proposal table by proposal number or method direction;
- filtering proposals by all, accepted, or rejected decision; and
- showing the current visible-row count.

The proposal table header remains visible while scrolling. Numeric cells use
tabular figures, and wide tables scroll horizontally on narrow screens. All
controls and sortable headers are keyboard accessible and have visible focus
states.

## Visual Direction

Use a restrained scientific-report aesthetic:

- warm off-white canvas;
- white table surfaces;
- charcoal and slate typography;
- navy headers;
- muted teal for successful status;
- muted red for rejected status; and
- amber/gold solely for proposal 020.

The first viewport prioritizes the open-source comparison table. Avoid large
hero artwork, gradients, decorative imagery, or excessive dashboard cards.
Use system fonts so the page remains offline-safe.

## Data Flow and Privacy

Generation reads only the sources required for aggregation:

- the public ladder comparison CSV for the first table;
- proposal `REPORT.md` files for public aggregate fields; and
- private evaluator result records only to calculate anonymous per-proposal
  runtime quantiles.

The generated HTML may contain only proposal-level and method-level aggregate
statistics. It must not contain case identifiers, split identifiers, matrix
dimensions from the private suite, source paths, seeds, witnesses, manifest
rows, target values, or private filenames. A leakage scan checks both visible
text and embedded JavaScript data.

## Error Handling

Generation fails rather than silently producing a partial page when:

- proposal numbering is not exactly 001 through 100;
- a required report is missing or malformed;
- the open-source comparison lacks any required method;
- a numeric field cannot be parsed consistently; or
- aggregate output contains a forbidden private marker.

Missing per-invocation timing data is the sole tolerated omission and renders
as an em dash for median and P95.

## Verification

Before delivery, verify that:

1. the output is one offline-safe HTML file with no remote assets;
2. the first table has exactly the four open-source implementations;
3. the proposal table has exactly 100 sequential rows;
4. proposal 020 is the only highlighted trial;
5. recomputed counts, averages, medians, and quantiles match their source data;
6. sorting, searching, and decision filtering work from keyboard and pointer;
7. the layout remains readable at desktop and narrow widths;
8. no private marker or case-level data appears in the HTML; and
9. the repository's unrelated files and existing user changes remain intact.

## Non-Goals

- Hosting or deploying the page.
- Opening the final holdout.
- Re-running algorithms or external baselines.
- Claiming an apples-to-apples comparison between proposal 020 and the public
  ladder packages.
- Presenting any randomized upper bound as an exact code distance.
