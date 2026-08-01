# Theme

## Compact token summary

### QLab Workbench

The target UI inherits the Zotero plugin's adaptive light/dark chrome.

| Token | Light | Dark |
|---|---|---|
| accent | `#007aff` | `#0a84ff` |
| accent strong | `#0066d6` | `#409cff` |
| background | `#ffffff` | `#1e1e1e` |
| raised | `#ffffff` | `#2c2c2e` |
| subtle | `#f5f5f7` | `#252527` |
| hover | `#ececee` | `#3a3a3c` |
| text | `#1d1d1f` | `#f5f5f7` |
| muted | `#86868b` | `#98989d` |
| danger | `#ff3b30` | `#ff453a` |
| warning | `#ff9500` | `#ff9f0a` |
| success | `#34c759` | `#30d158` |

- UI font: Apple system / SF Pro Text / Helvetica Neue.
- Monospace: SFMono-Regular / Menlo / Monaco / Consolas.
- Workbench file row: 10.5px, `3px 6px` padding, 4px radius.
- Current QMD file column: 176px plus an 18px collapse handle.
- Workbench right-pane toolbar: minimum 40px high.
- Workbench shell uses square tab edges; floating/sidebar surfaces use 7–12px
  radii and the `--zc-shadow` token.

### Dashboard

The dashboard is a separate visual namespace and must not bleed into Workbench:
`ink #17211d`, `paper #f3f0e8`, `surface #fbfaf6`, `green #174c3b`,
`lime #c8f06f`, Geist Sans/Mono.

## Raw Workbench theme source

Source: `integrations/zotero/src/styles.css:1-53`

```css
:root {
  --zc-accent: #007aff;
  --zc-accent-strong: #0066d6;
  --zc-accent-soft: color-mix(in srgb, var(--zc-accent) 12%, transparent);
  --zc-bg: #ffffff;
  --zc-bg-raised: #ffffff;
  --zc-bg-subtle: #f5f5f7;
  --zc-bg-hover: #ececee;
  --zc-border: rgba(0, 0, 0, .1);
  --zc-text: #1d1d1f;
  --zc-muted: #86868b;
  --zc-danger: #ff3b30;
  --zc-warning: #ff9500;
  --zc-success: #34c759;
  --zc-code-bg: #1d1d1f;
  --zc-shadow: 0 10px 30px rgba(0, 0, 0, .1), 0 2px 8px rgba(0, 0, 0, .06);
}

@media (prefers-color-scheme: dark) {
  :root {
    --zc-accent: #0a84ff;
    --zc-accent-strong: #409cff;
    --zc-bg: #1e1e1e;
    --zc-bg-raised: #2c2c2e;
    --zc-bg-subtle: #252527;
    --zc-bg-hover: #3a3a3c;
    --zc-border: rgba(255, 255, 255, .14);
    --zc-text: #f5f5f7;
    --zc-muted: #98989d;
    --zc-danger: #ff453a;
    --zc-warning: #ff9f0a;
    --zc-success: #30d158;
    --zc-shadow: 0 12px 38px rgba(0, 0, 0, .45), 0 2px 10px rgba(0, 0, 0, .3);
  }
}
```

## Raw dashboard variables

Source: `src/app/globals.css:1-16`

```css
@import "tailwindcss";

:root {
  --ink: #17211d;
  --muted: #65716c;
  --paper: #f3f0e8;
  --surface: #fbfaf6;
  --line: #d9d7ce;
  --green: #174c3b;
  --lime: #c8f06f;
  --amber: #9a6a18;
  --red: #9f342c;
  --blue: #315b8f;
}
```

There is no Tailwind config override. Tailwind 4 is imported by the dashboard,
but the visible UI primarily uses handwritten global CSS and CSS Modules.
