# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a personal academic website/digital garden built with **Quarto**, focused on quantum computing research. The site contains theory notes, experimental documentation, and work-in-progress projects.

## Common Commands

```bash
# Build the static website (outputs to _site/)
quarto render

# Start local preview server on port 4200
quarto preview

# Render and deploy to remote server
./sync.sh
```

## Architecture

**Content Sections:**
- `theory/` - Research paper summaries (`Posts/`) and topic deep-dives (`Topics/`)
- `Experiments/` - Experimental notes (PDH locking, Rb87 MOT)
- `workspace/` - Active work-in-progress projects

**Key Files:**
- `_quarto.yml` - Main Quarto configuration (navigation, theme, bibliography settings)
- `references.bib` - Shared bibliography
- `aps.csl` - APS citation style
- `styles.css` - Custom styling

**Output:**
- `_site/` - Generated static website (do not edit directly)

## Content Format

All content is written in Quarto Markdown (`.qmd` files). Key features used:
- KaTeX for math rendering
- Bibliography citations via `references.bib`
- Jupyter integration for Python code cells

## Deployment

The site deploys via rsync to a remote Docker container. The `sync.sh` script handles both rendering and deployment in one step.
