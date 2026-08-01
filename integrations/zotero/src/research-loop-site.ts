import type { BridgeEvent, NativeBridge, SpawnOptions } from "./native-bridge";
import { sha256Bytes } from "./hashing";
import { profilePath, sleep } from "./platform";
import { knowledgeUrlToQmdPath } from "./editor-tree";
import {
  geckoTargetDigest,
  type LocalRepositoryTargetRuntime,
} from "./local-repository-target-resolver";
import {
  createGeckoQLabPrivateFileHost,
  createGeckoQLabPathHost,
  isQLabRepositoryShape,
  normalizeQLabRoot,
  qlabRepositoryState,
  QLAB_STARTER_MARKER,
  type QLabRepositoryState,
} from "./qlab-workspace";

export const RESEARCH_LOOP_SITE_URL = "http://127.0.0.1:4180/";
const SITE_SESSION_ID = "research-loop-site";
const INITIALIZE_SESSION_ID = "research-loop-initialize";
let repositoryIdentitySession = 0;
const START_SCRIPT = [
  'cd -- "$1"',
  'command -v npm >/dev/null 2>&1 || { echo "Research Loop requires Node.js and npm. Install Node.js 22 or newer, then try again." >&2; exit 127; }',
  'command -v quarto >/dev/null 2>&1 || { echo "Research Loop requires Quarto. Install Quarto, then try again." >&2; exit 127; }',
  'if [ ! -f "$1/node_modules/.package-lock.json" ]; then echo "[research-loop] installing dependencies"; npm ci; fi',
  'if [ ! -f "$1/dist/server/index.js" ]; then npm run build; fi',
  "exec npm run start -- --hostname 127.0.0.1 --port 4180",
].join(" && ");
const INITIALIZE_SCRIPT = [
  "set -eu",
  'unzip -n -q "$2" -d "$1"',
  '/bin/chmod 0700 "$1/qlab"',
  'if [ ! -d "$1/.git" ]; then /usr/bin/git -C "$1" init -q -b main; fi',
].join("\n");

export type ResearchLoopSiteProcessEvent =
  | { type: "output"; text: string }
  | { type: "exit"; exitCode: number | null };

export function researchLoopBuildProgress(output: string): string | null {
  if (/\[research-loop\] installing dependencies/u.test(output)) return "Installing main-site dependencies…";
  const pages = [...output.matchAll(/\[\s*(\d+)\/(\d+)\]/gu)].at(-1);
  if (pages) return `Building Knowledge ${Number(pages[1])}/${Number(pages[2])}…`;
  if (/\bknowledge:build\b|knowledge\.ts build/u.test(output)) return "Preparing the Knowledge build…";
  if (/\bbuild:app\b|vinext build/u.test(output)) return "Building the main-site application…";
  if (/Build complete\./u.test(output)) return "Build complete; starting the main site…";
  return null;
}

export interface ResearchLoopSiteRuntime extends LocalRepositoryTargetRuntime {
  check(url: string): Promise<boolean>;
  repositoryState(repositoryRoot: string): Promise<QLabRepositoryState>;
  initialize(repositoryRoot: string): Promise<void>;
  hasBuild(repositoryRoot: string): Promise<boolean>;
  startBridge(): Promise<void>;
  spawn(sessionId: string, options: SpawnOptions): Promise<void>;
  listen(sessionId: string, listener: (event: ResearchLoopSiteProcessEvent) => void): () => void;
  sleep(milliseconds: number): Promise<void>;
}

type ResearchLoopSiteBridge = Pick<
  NativeBridge,
  "start" | "spawnPipe" | "onEvent" | "decodeOutput" | "flushOutput"
>;

export function createResearchLoopSiteRuntime(
  bridge: ResearchLoopSiteBridge,
  bundledRootURI: string,
  version: string,
): ResearchLoopSiteRuntime {
  const pathHost = createGeckoQLabPathHost();
  const privateFileHost = createGeckoQLabPrivateFileHost();
  return {
    async check(url) {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), 1_500);
      try {
        const response = await fetch(url, {
          cache: "no-store",
          signal: controller.signal,
        });
        return response.ok;
      }
      catch {
        return false;
      }
      finally {
        clearTimeout(timer);
      }
    },
    canonicalize: (repositoryRoot) => normalizeQLabRoot(repositoryRoot, pathHost),
    state: (repositoryRoot) => qlabRepositoryState(repositoryRoot, pathHost),
    repositoryState: (repositoryRoot) => qlabRepositoryState(repositoryRoot, pathHost),
    initialize: async (repositoryRoot) => {
      const markerDirectory = PathUtils.join(repositoryRoot, ".research-loop");
      await IOUtils.makeDirectory(markerDirectory, {
        createAncestors: true,
        ignoreExisting: true,
        permissions: 0o700,
      });
      const markerPath = PathUtils.join(repositoryRoot, QLAB_STARTER_MARKER);
      await IOUtils.writeUTF8(markerPath, `${JSON.stringify({
        schemaVersion: 1,
        state: "initializing",
        source: "research-loop-zotero-xpi",
      }, null, 2)}\n`, { tmpPath: `${markerPath}.tmp` });

      const archiveBytes = await readBundledAsset(
        `${bundledRootURI}starter/research-loop-starter.zip`,
      );
      const expectedDigest = new TextDecoder().decode(await readBundledAsset(
        `${bundledRootURI}starter/research-loop-starter.sha256`,
      )).trim();
      if (!/^[a-f0-9]{64}$/u.test(expectedDigest) || sha256Bytes(archiveBytes) !== expectedDigest) {
        throw new Error("The bundled Research Loop starter failed its integrity check");
      }
      const archiveDirectory = profilePath("starter", version);
      const archivePath = PathUtils.join(archiveDirectory, "research-loop-starter.zip");
      await IOUtils.makeDirectory(archiveDirectory, {
        createAncestors: true,
        ignoreExisting: true,
        permissions: 0o700,
      });
      await IOUtils.write(archivePath, archiveBytes, { tmpPath: `${archivePath}.tmp` });

      await bridge.start();
      await runInitializationProcess(bridge, repositoryRoot, archivePath);
      if (!await isQLabRepositoryShape(repositoryRoot, pathHost)) {
        throw new Error("Research Loop initialization did not produce the required repository structure");
      }
      await IOUtils.writeUTF8(markerPath, `${JSON.stringify({
        schemaVersion: 1,
        state: "ready",
        source: "research-loop-zotero-xpi",
        pluginVersion: version,
      }, null, 2)}\n`, { tmpPath: `${markerPath}.tmp` });
    },
    async gitPrivatePath(repositoryRoot) {
      await bridge.start();
      repositoryIdentitySession += 1;
      return runGitPrivatePathProcess(
        bridge,
        `repository-identity-${repositoryIdentitySession}`,
        repositoryRoot,
      );
    },
    readPrivate: (path) => privateFileHost.readPrivate(path),
    createPrivateIfAbsent: (path, value, mode) =>
      privateFileHost.createPrivateIfAbsent(path, value, mode),
    resolvePath: (root, path) => privateFileHost.resolvePath(root, path),
    isPathInside: (root, candidate) => privateFileHost.isPathInside(root, candidate),
    digest: geckoTargetDigest,
    hasBuild: (repositoryRoot) =>
      IOUtils.exists(PathUtils.join(repositoryRoot, "dist", "server", "index.js")),
    startBridge: () => bridge.start(),
    spawn: (sessionId, options) => bridge.spawnPipe(sessionId, options),
    listen(sessionId, listener) {
      return bridge.onEvent((event: BridgeEvent) => {
        if (!("sessionId" in event) || event.sessionId !== sessionId) return;
        if (event.type === "output") {
          listener({ type: "output", text: bridge.decodeOutput(sessionId, event.data) });
        }
        else if (event.type === "exit") {
          const tail = bridge.flushOutput(sessionId);
          if (tail) listener({ type: "output", text: tail });
          listener({ type: "exit", exitCode: event.exitCode });
        }
      });
    },
    sleep,
  };
}

async function runGitPrivatePathProcess(
  bridge: ResearchLoopSiteBridge,
  sessionId: string,
  repositoryRoot: string,
): Promise<string> {
  let output = "";
  let settle: ((event: { exitCode: number | null }) => void) | null = null;
  const exited = new Promise<{ exitCode: number | null }>((resolve) => { settle = resolve; });
  const unsubscribe = bridge.onEvent((event: BridgeEvent) => {
    if (!("sessionId" in event) || event.sessionId !== sessionId) return;
    if (event.type === "output") {
      output = `${output}${bridge.decodeOutput(event.sessionId, event.data)}`.slice(-4_096);
    }
    else if (event.type === "exit") {
      output = `${output}${bridge.flushOutput(event.sessionId)}`.slice(-4_096);
      settle?.({ exitCode: event.exitCode });
    }
  });
  try {
    await bridge.spawnPipe(sessionId, {
      argv: [
        "/usr/bin/git",
        "-C",
        repositoryRoot,
        "rev-parse",
        "--git-path",
        "qlab/repository-id",
      ],
      cwd: repositoryRoot,
      env: { PATH: "/usr/bin:/bin:/usr/sbin:/sbin" },
    });
    const { exitCode } = await exited;
    if (exitCode !== 0) throw new Error("Git-private repository identity is unavailable");
    return output;
  }
  finally {
    unsubscribe();
  }
}

async function readBundledAsset(uri: string): Promise<Uint8Array> {
  try {
    const response = await fetch(uri);
    if (response.ok || response.status === 0) return new Uint8Array(await response.arrayBuffer());
  }
  catch { /* jar: fetch can be unavailable on some Zotero builds */ }

  return new Promise<Uint8Array>((resolve, reject) => {
    try {
      const channel = NetUtil.newChannel({
        uri: Services.io.newURI(uri),
        loadUsingSystemPrincipal: true,
      });
      NetUtil.asyncFetch(channel, (stream: any, status: number) => {
        if (!Components.isSuccessCode(status)) {
          reject(new Error(`Could not read bundled Research Loop starter (${status})`));
          return;
        }
        try {
          const binary = Components.classes["@mozilla.org/binaryinputstream;1"]
            .createInstance(Components.interfaces.nsIBinaryInputStream);
          binary.setInputStream(stream);
          resolve(Uint8Array.from(binary.readByteArray(binary.available())));
        }
        catch (error) {
          reject(error);
        }
      });
    }
    catch (error) {
      reject(error);
    }
  });
}

async function runInitializationProcess(
  bridge: ResearchLoopSiteBridge,
  repositoryRoot: string,
  archivePath: string,
): Promise<void> {
  let output = "";
  let settle: ((event: { exitCode: number | null }) => void) | null = null;
  const exited = new Promise<{ exitCode: number | null }>((resolve) => { settle = resolve; });
  const unsubscribe = bridge.onEvent((event: BridgeEvent) => {
    if (!("sessionId" in event) || event.sessionId !== INITIALIZE_SESSION_ID) return;
    if (event.type === "output") output = `${output}${bridge.decodeOutput(event.sessionId, event.data)}`.slice(-12_000);
    if (event.type === "exit") {
      output = `${output}${bridge.flushOutput(event.sessionId)}`.slice(-12_000);
      settle?.({ exitCode: event.exitCode });
    }
  });
  try {
    await bridge.spawnPipe(INITIALIZE_SESSION_ID, {
      argv: ["/bin/zsh", "-lc", INITIALIZE_SCRIPT, INITIALIZE_SESSION_ID, repositoryRoot, archivePath],
      cwd: repositoryRoot,
      env: { PATH: "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" },
    });
    const { exitCode } = await exited;
    if (exitCode !== 0) {
      const detail = output.trim().split("\n").slice(-8).join("\n");
      throw new Error(detail || `Research Loop initialization failed (code ${exitCode ?? "unknown"})`);
    }
  }
  finally {
    unsubscribe();
  }
}

export class ResearchLoopSiteService {
  constructor(private readonly runtime: ResearchLoopSiteRuntime) {}

  isAvailable(): Promise<boolean> {
    return this.runtime.check(RESEARCH_LOOP_SITE_URL);
  }

  repositoryState(repositoryRoot: string): Promise<QLabRepositoryState> {
    return this.runtime.repositoryState(repositoryRoot);
  }

  async deploy(repositoryRoot: string, onProgress: (message: string) => void = () => {}): Promise<void> {
    if (!repositoryRoot.trim()) throw new Error("Choose a Research Loop repository first");
    const state = await this.repositoryState(repositoryRoot);
    if (state === "incompatible") {
      throw new Error("This folder contains files but is not a Research Loop repository. Choose an empty folder, or a folder containing only knowledge/, drafts/, and literature/.");
    }
    if (state === "missing") throw new Error("Choose a Research Loop repository first");
    if (state === "empty" || state === "partial") {
      onProgress(state === "empty" ? "Initializing Research Loop…" : "Completing the Research Loop structure…");
      await this.runtime.initialize(repositoryRoot);
    }
    if (await this.isAvailable()) return;

    const hasBuild = await this.runtime.hasBuild(repositoryRoot);
    onProgress(hasBuild ? "Starting the existing main site…" : "Preparing the first main-site build…");
    await this.runtime.startBridge();
    let output = "";
    let exitCode: number | null | undefined;
    const unsubscribe = this.runtime.listen(SITE_SESSION_ID, (event) => {
      if (event.type === "exit") {
        exitCode = event.exitCode;
        return;
      }
      output = `${output}${event.text}`.slice(-24_000);
      const progress = researchLoopBuildProgress(output);
      if (progress) onProgress(progress);
    });
    try {
      await this.runtime.spawn(SITE_SESSION_ID, {
        argv: ["/bin/zsh", "-lc", START_SCRIPT, SITE_SESSION_ID, repositoryRoot],
        cwd: repositoryRoot,
        env: {
          PATH: "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin",
        },
      });

      // A clean checkout needs time to build both Quarto knowledge and Vinext.
      // Poll the actual endpoint instead of guessing when the process is ready.
      for (let attempt = 0; attempt < 180; attempt++) {
        if (await this.isAvailable()) {
          onProgress("Main site started");
          return;
        }
        if (exitCode !== undefined) {
          const detail = output.trim().split("\n").slice(-8).join("\n");
          throw new Error(detail || `The main-site process exited (code ${exitCode ?? "unknown"})`);
        }
        await this.runtime.sleep(1_000);
      }
      throw new Error("Main site startup timed out; check repository dependencies and build logs");
    }
    finally {
      unsubscribe();
    }
  }
}

export interface ResearchLoopSiteViewOptions {
  onBack(): void;
  /** Opens the workspace on the knowledge page the browser is showing. */
  onOpenDocument?(relativePath: string): void;
}

/**
 * The local Research Loop site, in a native Zotero browser.
 *
 * This view browses; it does not edit. The Source button hands the knowledge page
 * the browser is showing to the workspace, which owns everything about editing
 * it. Keeping the two apart is what lets the site stay readable on its own —
 * `drafts/` is never published, so it has no URL here and never will.
 */
export class ResearchLoopSiteView {
  readonly root: HTMLElement;
  private browser: (HTMLElement & {
    reload?(): void;
    currentURI?: { spec?: string };
    webNavigation?: { currentURI?: { spec?: string } };
    addProgressListener?(listener: unknown, flags?: number): void;
    removeProgressListener?(listener: unknown): void;
  }) | null = null;
  private readonly content: HTMLElement;
  private readonly address: HTMLElement;
  private readonly sourceButton: HTMLButtonElement;
  private lastKnownUrl = RESEARCH_LOOP_SITE_URL;
  private currentPage: string | null = null;
  private locationListener: unknown = null;
  private destroyed = false;

  constructor(host: HTMLElement, private readonly options: ResearchLoopSiteViewOptions) {
    const doc = host.ownerDocument;
    this.root = doc.createElement("section");
    this.root.className = "zc-main-site-view";
    this.root.hidden = true;
    this.root.setAttribute("aria-label", "Research Loop Main Site");

    const toolbar = doc.createElement("header");
    toolbar.className = "zc-main-site-toolbar";
    const back = doc.createElement("button");
    back.type = "button";
    back.className = "zc-main-site-back";
    back.textContent = "← Back to AI";
    back.addEventListener("click", () => this.options.onBack());
    this.address = doc.createElement("span");
    this.address.className = "zc-main-site-address";
    this.address.textContent = RESEARCH_LOOP_SITE_URL;
    this.sourceButton = doc.createElement("button");
    this.sourceButton.type = "button";
    this.sourceButton.className = "zc-main-site-source";
    this.sourceButton.textContent = "Source";
    this.sourceButton.title = "Open the QMD source for the current Knowledge page";
    // One rule for the disabled state. Remote <browser> navigation
    // notifications are not delivered in every Zotero window, so the URL is
    // resolved again on click rather than leaving a silently disabled button.
    this.sourceButton.disabled = !this.options.onOpenDocument;
    this.sourceButton.addEventListener("click", () => this.openSource());
    const refresh = doc.createElement("button");
    refresh.type = "button";
    refresh.className = "zc-main-site-refresh";
    refresh.textContent = "Refresh";
    refresh.addEventListener("click", () => this.reload());
    toolbar.append(back, this.address, this.sourceButton, refresh);

    this.content = doc.createElement("div");
    this.content.className = "zc-main-site-content";
    this.root.append(toolbar, this.content);
    host.appendChild(this.root);
  }

  isVisible(): boolean {
    return !this.root.hidden;
  }

  show(): void {
    this.ensureBrowser();
    this.root.hidden = false;
  }

  hide(): void {
    this.root.hidden = true;
  }

  destroy(): void {
    this.destroyed = true;
    this.detachLocationListener();
    this.browser = null;
    this.root.remove();
  }

  private ensureBrowser(): void {
    if (this.browser || this.content.childElementCount) return;
    const createXULElement = (this.root.ownerDocument as unknown as {
      createXULElement?: (name: string) => HTMLElement;
    }).createXULElement;
    if (typeof createXULElement !== "function") {
      const unavailable = this.root.ownerDocument.createElement("div");
      unavailable.className = "zc-main-site-unavailable";
      unavailable.textContent = "The native Zotero browser is unavailable";
      this.content.appendChild(unavailable);
      return;
    }
    this.browser = createXULElement.call(this.root.ownerDocument, "browser") as HTMLElement & {
      reload?(): void;
    };
    this.browser.classList.add("zc-main-site-browser");
    this.browser.setAttribute("type", "content");
    this.browser.setAttribute("remote", "true");
    this.browser.setAttribute("maychangeremoteness", "true");
    this.browser.setAttribute("src", RESEARCH_LOOP_SITE_URL);
    this.trackBrowserLocation();
    this.content.appendChild(this.browser);
  }

  private reload(): void {
    if (typeof this.browser?.reload === "function") {
      this.browser.reload();
      return;
    }
    this.browser?.setAttribute("src", RESEARCH_LOOP_SITE_URL);
  }

  private trackBrowserLocation(): void {
    if (!this.browser) return;
    const update = (value?: string) => {
      const url = this.browserUrl(value);
      this.lastKnownUrl = url;
      this.address.textContent = url;
      this.currentPage = knowledgeUrlToQmdPath(url);
      this.sourceButton.title = this.currentPage
        ? `Edit ${this.currentPage}`
        : "Open a Knowledge page on the right first";
    };
    const listener = {
      onLocationChange: (_progress: unknown, _request: unknown, location: { spec?: string } | null) => {
        update(location?.spec);
      },
      onStateChange() {},
      onProgressChange() {},
      onStatusChange() {},
      onSecurityChange() {},
      onContentBlockingEvent() {},
      QueryInterface: (globalThis as { ChromeUtils?: { generateQI?: (names: string[]) => unknown } })
        .ChromeUtils?.generateQI?.(["nsIWebProgressListener", "nsISupportsWeakReference"]),
    };
    this.locationListener = listener;
    try {
      const flags = (globalThis as {
        Components?: { interfaces?: { nsIWebProgress?: { NOTIFY_LOCATION?: number } } };
      }).Components?.interfaces?.nsIWebProgress?.NOTIFY_LOCATION;
      this.browser.addProgressListener?.(listener, flags);
    }
    catch { /* fall through to the load listener below */ }
    // Registered even when the progress listener was accepted: a remote
    // browser can accept one without delivering location callbacks to a view
    // an extension created.
    this.browser.addEventListener("load", () => update(), true);
    update();
  }

  private detachLocationListener(): void {
    if (!this.locationListener) return;
    try { this.browser?.removeProgressListener?.(this.locationListener); }
    catch { /* the remote browser may already be gone */ }
    this.locationListener = null;
  }

  private openSource(): void {
    if (!this.options.onOpenDocument) return;
    this.currentPage = knowledgeUrlToQmdPath(this.browserUrl());
    if (!this.currentPage) {
      this.showSourceFeedback("Open a Knowledge page first", "The current page has no corresponding QMD source");
      return;
    }
    this.options.onOpenDocument(this.currentPage);
  }

  private showSourceFeedback(label: string, detail: string): void {
    this.sourceButton.textContent = label;
    this.sourceButton.title = detail;
    this.address.textContent = detail;
    this.root.ownerDocument.defaultView?.setTimeout(() => {
      if (this.destroyed) return;
      this.sourceButton.textContent = "Source";
      this.address.textContent = this.browserUrl();
      this.sourceButton.title = this.currentPage
        ? `Edit ${this.currentPage}`
        : "Open a Knowledge page on the right first";
    }, 2_500);
  }

  private browserUrl(preferred = ""): string {
    if (preferred) return preferred;
    try {
      const current = this.browser?.currentURI?.spec;
      if (current) return current;
    }
    catch { /* the remote browser getter may be temporarily unavailable */ }
    try {
      const current = this.browser?.webNavigation?.currentURI?.spec;
      if (current) return current;
    }
    catch { /* the remote browser getter may be temporarily unavailable */ }
    return this.lastKnownUrl || this.browser?.getAttribute("src") || "";
  }
}
