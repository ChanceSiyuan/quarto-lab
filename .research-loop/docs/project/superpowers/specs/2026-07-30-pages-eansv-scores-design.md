# GitHub Pages Research Evaluation Cards Design

## Goal

Publish the agreed research-evaluation results on the GitHub Pages detail pages
for `Prob-124` through `Prob-128`, while keeping the presentation identical to
the existing `Prob-000` three-card assessment panel. Correct the middle card on
`Prob-000` so every public detail page uses the same three measures:

1. Scientific Demand Score
2. Expected Attributable Net Social Value (EANSV)
3. Autoresearch Fit

The displayed values are external-evidence scenario estimates, not completed
local assessments or frozen valuation snapshots.

## Scope

- Update the static GitHub Pages assessment component used by `Prob-000` so its
  middle card is EANSV rather than the legacy broad industry/social proxy.
- Render that same component and visual treatment on the Pages-only detail
  routes for `Prob-124` through `Prob-128`.
- Keep the existing dashboard, global styling, layout, problem manifests,
  trusted knowledge tree, drafts, literature, and local assessment workflow
  unchanged.
- Do not write generated `out/` files by hand; the Pages build remains their
  only author.

## Data and calculation model

One read-only source module will hold the public scenario inputs for all six
Pages examples. The UI will calculate displayed point values from those inputs
instead of duplicating final values in page markup.

### Scientific Demand Score

Use the repository's current active-component formula:

```text
Scientific Demand Score
  = 100 * (0.45 * influence
         + 0.30 * recent_momentum
         + 0.15 * research_breadth)
        / 0.90
```

The reserved citation-network weight is excluded and active weights are
renormalized. For `Prob-124` through `Prob-128`, the public values are
low-confidence external-evidence scenarios. Each card will show the estimate,
range, component inputs, formula substitution, and the main evidence caveat.

### Expected Attributable Net Social Value

Use a five-year, 2026-USD scenario model that explicitly removes the
without-research counterfactual:

```text
incremental_success_probability
  = P(useful outcome with this research)
  - P(useful outcome without this research)

EANSV
  = incremental_success_probability * conditional_social_value
  + expected_information_value
  - expected_research_cost
```

The base-case inputs are recorded per problem. Low/high outputs are coherent
scenario bounds, so a negative low case is allowed. Broad quantum-market value
is not credited to an individual problem. The card will display the base value,
range, unit/year, substituted base formula, and the dominant counterfactual or
cost caveat.

### Autoresearch Fit

Use the existing seven-dimension weighted calculation:

```text
A = 100 * weighted_average(dimension scores on 0--5 scale) / 5
```

Weights remain 20/20/15/15/10/10/10 for modifiable search object, executable
objective, correctness and anti-gaming, incremental feedback, fresh evaluation,
reproducibility and auditability, and attempt runtime. Each card will list the
dimension inputs and exact weighted calculation.

## Public values

| Problem | Scientific Demand | EANSV base (range, USD 2026) | Autoresearch Fit |
|---|---:|---:|---:|
| Prob-124 | 79 | $0.3M (-$0.7M to $9M) | 71 |
| Prob-125 | 85 | $0.0M (-$1.1M to $5M) | 85 |
| Prob-126 | 70 | $0.8M (-$0.8M to $26M) | 65 |
| Prob-127 | 81 | $3.0M (-$0.2M to $60M) | 98 |
| Prob-128 | 79 | $1.4M (-$0.6M to $40M) | 92 |

`Prob-000` keeps its existing Scientific Demand and Autoresearch Fit example
inputs. Its middle card becomes a clearly labeled synthetic EANSV example using
the same formula and disclosure rules.

## Page behavior and presentation

- Preserve the current `Prob-000` three-column card layout, typography, borders,
  responsive one-column collapse, and native `<details>` interaction.
- On each detail page, show the problem identity and summary first, followed by
  the three assessment cards.
- Card summaries show the metric name and point/base result. Expanding a card
  shows the formula, substituted inputs, range where applicable, and concise
  reasoning.
- Add a visible note that the numbers are low-confidence external-evidence
  scenarios and are not frozen local assessment snapshots.
- Retain the methodology-documentation link.
- Keep the static Pages output script-free and free of local assessment routes,
  agent launchers, private paths, and runtime controls.

## Code boundaries

- A focused static-score module owns scenario inputs, calculations, formatting
  data, and problem-ID lookup.
- The existing static assessment component accepts a problem ID and renders the
  matching three cards. It remains the only visual implementation.
- The Pages-only branch of the problem detail route invokes the component for
  `Prob-124` through `Prob-128`; local problem pages continue to use the local
  assessment service.
- Component styling reuses the existing static assessment stylesheet, with only
  small additions needed for the scenario disclosure.

## Validation

Tests will be written before production changes and will prove:

- all six public detail pages contain exactly the three intended metric labels;
- the legacy `Industry / social proxy` label is absent;
- all five official problem pages show their agreed point/base values;
- formula text includes counterfactual subtraction and research cost for EANSV;
- calculation helpers reproduce every published Scientific Demand,
  EANSV-base, and Autoresearch Fit value from inputs;
- Pages output remains static, base-path-correct, and free of local/private
  markers; and
- the full Pages build and relevant rendered-output tests pass.

## Non-goals

- Calibrating these scenarios as investment-grade forecasts.
- Creating or freezing local assessment artifacts.
- Updating problem lifecycle states or autoresearch infrastructure.
- Adding a portfolio comparison page or changing the homepage.
- Publishing broad quantum-market forecasts as problem-attributable value.
