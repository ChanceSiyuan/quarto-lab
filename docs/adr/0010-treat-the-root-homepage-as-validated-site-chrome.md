# Treat the root homepage as validated site chrome

`theory/**/*.qmd` remains the sole Trusted Knowledge authority and the sole
input to agent resolution. The repository-root `index.qmd` is site chrome: it
may provide a human landing page, but it is not learned knowledge and never
enters a Reading Bundle.

Because Quarto still renders that page, the safe projector validates it under
a separate, narrow homepage contract before copying it. Homepage frontmatter,
active HTML, URL schemes, and local links cannot bypass the same publication
boundary. The projector also reconstructs `_quarto.yml` from an explicit safe
schema instead of copying arbitrary project or Pandoc options. Thus a
non-knowledge page may shape the public shell without becoming an alternate
content authority or an execution hook.
