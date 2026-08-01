# Shared Layouts

## Next.js RootLayout

- Source: `src/app/layout.tsx`
- Description: Global HTML shell with Geist Sans/Mono and `globals.css`.

```tsx
import type { Metadata } from "next";
import { headers } from "next/headers";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${geistSans.variable} ${geistMono.variable}`}>
        {children}
      </body>
    </html>
  );
}
```

Metadata is generated from request headers in the same file and has no visual
effect on the target surface.

## Standalone QLab Workbench window

- Source: `integrations/zotero/standalone-workbench.xhtml`
- Description: XUL window hosting the same Workbench view as the Zotero tab.

```xml
<?xml version="1.0"?>
<?xml-stylesheet href="chrome://global/skin/" type="text/css"?>
<?xml-stylesheet href="chrome://zotero/skin/zotero.css" type="text/css"?>
<!DOCTYPE window>
<window
  id="qlab-standalone-workbench-window"
  orient="vertical"
  width="980"
  height="780"
  minwidth="560"
  minheight="520"
  title="Research Loop · Local Codex"
  persist="screenX screenY width height"
  windowtype="qlab:standalone-workbench"
  xmlns="http://www.mozilla.org/keymaster/gatekeeper/there.is.only.xul"
  xmlns:html="http://www.w3.org/1999/xhtml"
>
  <html:div
    id="qlab-standalone-workbench-host"
    style="display:flex;width:100%;height:100%;min-width:0;min-height:0;"
  />
</window>
```

## QLab Workbench shell

- Assembly: `integrations/zotero/src/plugin.ts:1238-1402`
- Native tab host: `integrations/zotero/src/workbench-tab.ts`
- Workbench DOM shell: `integrations/zotero/src/sidebar.ts:287-989`
- QMD workspace: `integrations/zotero/src/qmd-workspace.ts:103-330`
- Layout CSS: `integrations/zotero/src/styles.css:983-1303`

The rendered desktop layout is:

```text
optional 224px history rail
  | chat pane | 6px split handle | Main Site or QMD Workspace |
                               bottom terminal drawer overlays the shell
```

When QMD Workspace is open, its body is currently:

```text
176px QMD file column | 18px collapse handle | preview or Visual Edit
```

The target of this design task is the real QMD workspace render branch, not a
dashboard route or a generic web-app sidebar.
