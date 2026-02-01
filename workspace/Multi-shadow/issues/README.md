# GitHub-Style Issue Interface

This directory contains a hybrid GitHub Issue interface implementation using Quarto and Giscus.

## Overview

**Architecture:**
- **Main Post**: Custom GitHub-style CSS using Quarto divs
- **Comments**: Real Giscus integration (GitHub Discussions-based)
- **Theme**: Automatic light/dark mode support via CSS variables

## Files

- `issue1.qmd` - Example issue page with Quarto div structure
- `styles.css` - GitHub-style CSS for issue posts
- `README.md` - This file

## Setup Instructions

### Prerequisites

1. **GitHub Discussions** must be enabled on your repository
   - Go to repo Settings → Features → Enable Discussions

2. **Giscus App** must be installed
   - Visit https://github.com/apps/giscus
   - Install on your repository

3. **Repository must be public** (or users must have access)

4. **GitHub CLI (`gh`)** must be installed and authenticated
   ```bash
   gh auth login
   ```

### Configuration

1. **Run the Giscus setup script:**
   ```bash
   cd /home/chance/quarto-lab
   ./scripts/setup-giscus.sh
   ```

2. **Follow the prompts:**
   - Script will automatically fetch your repo ID
   - Select a discussion category (e.g., "General")
   - Copy the generated YAML configuration

3. **Update `_quarto.yml`:**
   - Replace the placeholder values in the `comments.giscus` section with the values from the script output
   - Current placeholders:
     ```yaml
     comments:
       giscus:
         repo: owner/repo  # Replace with your repo
         repo-id: "R_xxxxx"  # From script
         category: "General"
         category-id: "DIC_xxxxx"  # From script
     ```

4. **Verify configuration:**
   ```bash
   quarto render workspace/Multi-shadow/issues/issue1.qmd
   quarto preview
   ```
   Navigate to `/workspace/Multi-shadow/issues/issue1.html`

## Creating New Issues

Use the following template structure in `.qmd` files:

```markdown
---
title: "Your Issue Title"
date: 2026-01-31
categories: [Label1, Label2]
status: "Open"  # or "Closed"
css: styles.css
---

::: {.issue-container}
::: {.issue-title-section}
# [🔓 Open]{.status-open} Your Issue Title [#N]{.issue-number}

::: {.issue-meta}
[bug]{.label .label-bug} [enhancement]{.label .label-enhancement}
:::
:::

::: {.issue-post}
::: {.post-header}
::: {.post-author}
![Author Name](https://ui-avatars.com/api/?name=Author+Name&background=0D8ABC&color=fff&size=80){.post-avatar}
**Author Name** opened this issue on Jan 31, 2026
:::
:::

::: {.post-body}
## Problem Description

Your issue content here with full markdown support.

**Todo:**
- [ ] Task 1
- [ ] Task 2

### Code Example

\`\`\`python
# Your code
\`\`\`
:::
:::
:::

<!-- Giscus comments will automatically appear below -->
```

## Styling Customization

### Status Badges

- `.status-open` - Green badge for open issues
- `.status-closed` - Purple badge for closed issues

### Label Badges

Available label classes in `styles.css`:
- `.label-bug` - Red background
- `.label-enhancement` - Blue background
- `.label-documentation` - Dark blue background
- `.label-question` - Purple background
- `.label-wontfix` - White background with border

To add custom labels, add to `styles.css`:

```css
.label-custom {
  background: #yourcolor;
  color: #textcolor;
}
```

### Dark Mode

Dark mode is automatic via CSS variables:
- System preference: `@media (prefers-color-scheme: dark)`
- Quarto toggle: `.quarto-dark` and `.quarto-light` classes

Colors are defined in CSS variables at the top of `styles.css`:
```css
:root {
  --gh-canvas: #ffffff;
  --gh-border: #d0d7de;
  /* ... */
}
```

## Avatar Generation

Avatars use the UI Avatars API:
```
https://ui-avatars.com/api/?name=First+Last&background=0D8ABC&color=fff&size=80
```

Parameters:
- `name` - Person's name (spaces as +)
- `background` - Hex color (without #)
- `color` - Text color (without #)
- `size` - Image size in pixels

## Verification Checklist

### Visual Styling
- [ ] Issue title displays with status badge and number
- [ ] Labels render with correct colors
- [ ] Main post has GitHub-style borders and rounded corners
- [ ] Avatar displays properly (circular, 40px)
- [ ] Typography matches GitHub (system fonts, proper sizing)
- [ ] Spacing and padding are consistent

### Giscus Integration
- [ ] Comment box loads at bottom of page
- [ ] GitHub Discussions branding appears
- [ ] "Sign in with GitHub" button is present
- [ ] Theme matches page (light/dark auto-detection)

### Theme Consistency
**Light Mode:**
- [ ] Main post background is white (#ffffff)
- [ ] Borders are light gray (#d0d7de)
- [ ] Header is very light gray (#f6f8fa)
- [ ] Giscus uses light theme automatically

**Dark Mode:**
- [ ] Main post background is dark (#0d1117)
- [ ] Borders are medium gray (#30363d)
- [ ] Header is dark gray (#161b22)
- [ ] Text remains readable (white/light gray)
- [ ] Giscus switches to dark theme automatically

### Content Rendering
- [ ] Markdown formatting (bold, italic, links) renders correctly
- [ ] Task list checkboxes display and are interactive
- [ ] Code blocks have proper syntax highlighting
- [ ] Images display with correct sizing
- [ ] Headings have proper hierarchy

### Responsive Design
- [ ] Desktop (1200px+): Full width layout
- [ ] Tablet (768px-1199px): Adapts properly
- [ ] Mobile (< 768px): No horizontal scroll, readable text

## Troubleshooting

### Giscus Not Loading

1. **Check repository settings:**
   - GitHub Discussions enabled?
   - Repository is public?
   - Giscus app installed?

2. **Verify configuration:**
   ```bash
   grep -A 10 "comments:" _quarto.yml
   ```

3. **Check browser console:**
   - Open Developer Tools (F12)
   - Look for Giscus-related errors

### Styles Not Applying

1. **Verify CSS path:**
   - Ensure `css: styles.css` is in YAML front matter
   - Check file path is relative to the .qmd file

2. **Clear browser cache:**
   - Hard refresh: Ctrl+Shift+R (Linux/Windows) or Cmd+Shift+R (Mac)

3. **Re-render:**
   ```bash
   quarto render workspace/Multi-shadow/issues/issue1.qmd
   ```

### Dark Mode Not Working

1. **Check CSS variables:**
   - Ensure `@media (prefers-color-scheme: dark)` is in styles.css
   - Verify `.quarto-dark` class is defined

2. **Test system preference:**
   - Change OS theme to dark mode
   - Refresh browser

## Resources

- [Quarto Documentation](https://quarto.org/docs/)
- [Giscus](https://giscus.app/)
- [GitHub Discussions](https://docs.github.com/en/discussions)
- [GitHub Primer CSS](https://primer.style/css/) - Design reference
