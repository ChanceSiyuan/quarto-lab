import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import type { NativeBridge } from "./native-bridge";
import { renderMarkdown } from "./markdown";
import { findExecutable, findLoginShell, randomID } from "./platform";

export type TerminalAgent = "shell" | "codex";

export const MAX_TERMINAL_SESSIONS = 4;
export const TERMINAL_SESSION_IDLE_MS = 15 * 60 * 1000;
export const TERMINAL_SCROLLBACK_LINES = 5_000;
export const TERMINAL_READY_TIMEOUT_MS = 60_000;
export const MAX_PENDING_TERMINAL_INPUT = 128 * 1_024;
export const MATH_PREVIEW_DEBOUNCE_MS = 260;
export const MAX_MATH_PREVIEW_FORMULAS = 3;
const MATH_PREVIEW_BUFFER_LINES = 160;
const MATH_PREVIEW_BUFFER_CHARS = 16_000;
const MATH_DETECTION_TAIL_CHARS = 4_000;
const MAX_MATH_EXPRESSION_CHARS = 2_000;
export const CODEX_READER_DEVELOPER_INSTRUCTIONS = [
  "You are the research assistant embedded in Zotero's PDF Reader by Zotkit.",
  "For ordinary questions about the open PDF, call zotero_reader.get_reader_context once; it returns the active-paper metadata, current page, and current selection together.",
  "For questions that require details beyond the visible page, call zotero_reader.search_current_pdf first, then zotero_reader.read_pdf_pages for the relevant one-based page range.",
  "Never use textutil, pdftotext, Python PDF libraries, OCR, shell commands, or direct filesystem reads to inspect the active PDF; if the Reader MCP reports that text is unavailable, say so instead of falling back to the shell.",
  "Never call tools from the same zotero_reader MCP server concurrently or through Promise.all. Await get_active_paper, get_current_page, get_current_selection, search_current_pdf, read_pdf_pages, list_library_files, or search_library_files calls serially.",
  "The built-in zotkit_library MCP server exposes exactly four read-only tools: zotkit_find_items, zotkit_get_item, zotkit_list_collections, and zotkit_list_tags.",
  "A bundled read-only zotkit CLI with find, get, collections, and tags commands is also on PATH and its absolute path is in ZOTKIT_CLI; it needs no Python install, API key, or external configuration.",
  "Treat the original PDF and its containing directory as read-only. Never create, edit, rename, move, or delete files there.",
  "Never alter Zotero items, collections, tags, attachment links, annotations, notes, indexes, or storage. The bundled Zotkit and Reader tools are query-only.",
  "For references such as this, here, or the selected passage, consult zotero_reader before answering and cite the one-based PDF page.",
].join(" ");

export interface TerminalPaperOptions {
  host: HTMLElement;
  paperKey: string;
  paperTitle: string;
  workspace: string;
  workingDirectory: string;
  pdfPath?: string | null;
  librarySnapshotPath?: string | null;
  pageLabel?: string;
  agent?: TerminalAgent;
}

export interface TerminalPanelCallbacks {
  onPasteSelection?(): void;
  onRefreshContext?(): void;
  onOpenChat?(): void;
}

interface TerminalSession {
  key: string;
  sessionId: string;
  agent: TerminalAgent;
  paperKey: string;
  paperTitle: string;
  workspace: string;
  workingDirectory: string;
  pdfPath: string | null;
  librarySnapshotPath: string | null;
  terminal: Terminal;
  fit: FitAddon;
  element: HTMLElement;
  started: boolean;
  ready: boolean;
  exited: boolean;
  disposed: boolean;
  startPromise: Promise<void> | null;
  readyTimer: ReturnType<typeof setTimeout> | null;
  startupOutput: string;
  pendingInput: string;
  zotkitAvailable: boolean | null;
  lastUsed: number;
  mathExpressions: string[];
  mathFingerprint: string;
  mathDetectionTail: string;
  mathCandidatePending: boolean;
  mathPreviewCollapsed: boolean;
  mathPreviewDismissed: boolean;
  mathScanTimer: ReturnType<typeof setTimeout> | null;
}

/**
 * A real PTY-backed terminal mounted directly in Zotero's right Item Pane.
 *
 * `mount()` is intentionally presentation-only. The native helper and Codex
 * are not started until `open()` is called after the user expands the section.
 */
export class TerminalPanel {
  private root: HTMLElement | null = null;
  private host: HTMLElement | null = null;
  private surface: HTMLElement | null = null;
  private title: HTMLElement | null = null;
  private paperTitle: HTMLElement | null = null;
  private contextMeta: HTMLElement | null = null;
  private zotkitStatus: HTMLElement | null = null;
  private status: HTMLElement | null = null;
  private agentPicker: HTMLSelectElement | null = null;
  private mathPreview: HTMLElement | null = null;
  private mathPreviewBody: HTMLElement | null = null;
  private mathPreviewTitle: HTMLElement | null = null;
  private mathPreviewCollapse: HTMLButtonElement | null = null;
  private mathPreviewToggle: HTMLButtonElement | null = null;
  private current: TerminalSession | null = null;
  private currentOptions: TerminalPaperOptions | null = null;
  private sessions = new Map<string, TerminalSession>();
  private resizeObserver: ResizeObserver | null = null;
  private idleCleanupTimer: ReturnType<typeof setTimeout> | null = null;
  private activationSequence = 0;
  private visible = false;
  private readonly unsubscribe: () => void;

  constructor(
    private readonly bridge: NativeBridge,
    _legacyDrawerHeight = 420,
    private readonly callbacks: TerminalPanelCallbacks = {},
  ) {
    this.unsubscribe = bridge.onEvent((event) => {
      if (event.type === "output") {
        const session = this.sessionByID(event.sessionId);
        if (session) {
          // Process redraws (notably spinners) are not user activity. Hidden
          // sessions are therefore still eligible for idle cleanup.
          const output = this.bridge.decodeOutput(event.sessionId, event.data);
          session.terminal.write(output, () => this.observeMathOutput(session, output));
          this.observeStartupOutput(session, output);
        }
      }
      else if (event.type === "exit") {
        const session = this.sessionByID(event.sessionId);
        if (session) {
          const remaining = this.bridge.flushOutput(event.sessionId);
          if (remaining) {
            session.terminal.write(
              remaining,
              () => this.observeMathOutput(session, remaining),
            );
          }
          this.clearReadyTimer(session);
          this.clearMathScanTimer(session);
          session.pendingInput = "";
          session.exited = true;
          session.terminal.writeln(
            `\r\n\x1b[90m[process exited${event.exitCode === null ? "" : ` with code ${event.exitCode}`} ]\x1b[0m`,
          );
          this.scheduleIdleCleanup();
        }
      }
      else if (event.type === "error") {
        // Input and resize failures happen after spawn and must remain visible;
        // otherwise a rejected or truncated paste looks like a frozen terminal.
        if (event.sessionId) {
          const session = this.sessionByID(event.sessionId);
          if (session) this.showSessionError(session, event.message);
        }
        else this.showError(event.message);
      }
    });
  }

  get isOpen(): boolean {
    return this.visible
      && Boolean(this.root?.isConnected)
      && Boolean(this.current?.started)
      && !Boolean(this.current?.exited);
  }

  get hasLiveSessions(): boolean {
    return [...this.sessions.values()].some((session) => !session.exited);
  }

  /** Render the lightweight Mac-style frame without launching any process. */
  mount(host: HTMLElement): void {
    if (this.host === host && this.root?.isConnected) return;
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.root?.remove();
    this.host = host;
    host.classList.add("zc-pane-host");
    const doc = host.ownerDocument;

    const root = doc.createElement("section");
    root.className = "zc-terminal-sidebar";

    const bar = doc.createElement("header");
    bar.className = "zc-terminal-titlebar";
    const traffic = doc.createElement("div");
    traffic.className = "zc-traffic-lights";
    const stop = this.trafficButton(doc, "close", "Collapse Terminal (keep session)", () => {
      this.callbacks.onOpenChat?.();
    });
    const clear = this.trafficButton(doc, "minimize", "Clear Terminal", () => this.current?.terminal.clear());
    const focus = this.trafficButton(doc, "expand", "Focus Terminal", () => this.focus());
    traffic.append(stop, clear, focus);

    this.title = doc.createElement("div");
    this.title.className = "zc-terminal-title";
    this.title.textContent = "QLab — Terminal";

    this.agentPicker = doc.createElement("select");
    this.agentPicker.className = "zc-agent-picker";
    this.agentPicker.title = "Choose Local CLI";
    for (const [value, label] of [["shell", "Terminal"], ["codex", "Codex"]] as const) {
      const option = doc.createElement("option");
      option.value = value;
      option.textContent = label;
      this.agentPicker.appendChild(option);
    }
    this.agentPicker.addEventListener("change", () => {
      if (!this.currentOptions) return;
      const agent = this.agentPicker!.value as TerminalAgent;
      void this.activate({ ...this.currentOptions, agent }).catch((error) => this.showError(error));
    });
    const terminalTools = doc.createElement("div");
    terminalTools.className = "zc-terminal-tools";
    const chatButton = doc.createElement("button");
    chatButton.type = "button";
    chatButton.className = "zc-terminal-chat-button";
    chatButton.textContent = "Collapse";
    chatButton.title = "Collapse Terminal and keep the current session";
    chatButton.addEventListener("click", () => this.callbacks.onOpenChat?.());
    this.mathPreviewToggle = doc.createElement("button");
    this.mathPreviewToggle.type = "button";
    this.mathPreviewToggle.className = "zc-math-preview-toggle";
    this.mathPreviewToggle.textContent = "ƒx";
    this.mathPreviewToggle.title = "Open Formula Preview";
    this.mathPreviewToggle.setAttribute("aria-label", "Open Formula Preview");
    this.mathPreviewToggle.addEventListener("click", () => {
      if (!this.current?.mathExpressions.length) return;
      this.current.mathPreviewDismissed = false;
      this.current.mathPreviewCollapsed = false;
      this.renderMathPreview(this.current);
      requestAnimationFrame(() => this.fitCurrent());
    });
    terminalTools.append(chatButton, this.mathPreviewToggle, this.agentPicker);
    bar.append(traffic, this.title, terminalTools);

    const context = doc.createElement("div");
    context.className = "zc-terminal-context";
    const paperMark = doc.createElement("div");
    paperMark.className = "zc-terminal-paper-mark";
    paperMark.textContent = "PDF";
    paperMark.setAttribute("aria-hidden", "true");
    const contextCopy = doc.createElement("div");
    contextCopy.className = "zc-terminal-context-copy";
    this.paperTitle = doc.createElement("div");
    this.paperTitle.className = "zc-terminal-paper-title";
    this.paperTitle.textContent = "QLab Repository";
    this.contextMeta = doc.createElement("div");
    this.contextMeta.className = "zc-terminal-context-meta";
    this.contextMeta.textContent = "Real local shell · run commands or start Codex";
    contextCopy.append(this.paperTitle, this.contextMeta);
    this.zotkitStatus = doc.createElement("span");
    this.zotkitStatus.className = "zc-zotkit-status is-checking";
    this.zotkitStatus.textContent = "Built-in Zotkit: preparing…";
    this.zotkitStatus.title = "Built-in read-only Zotkit CLI and library tools";
    const actions = doc.createElement("div");
    actions.className = "zc-terminal-context-actions";
    const paste = doc.createElement("button");
    paste.type = "button";
    paste.textContent = "Paste Selection";
    paste.title = "Insert the current PDF selection into the terminal without sending it";
    paste.addEventListener("click", () => this.callbacks.onPasteSelection?.());
    const refresh = doc.createElement("button");
    refresh.type = "button";
    refresh.textContent = "Refresh";
    refresh.title = "Refresh the current paper, page, and selection";
    refresh.addEventListener("click", () => this.callbacks.onRefreshContext?.());
    actions.append(paste, refresh);
    context.append(paperMark, contextCopy, this.zotkitStatus, actions);

    this.mathPreview = doc.createElement("aside");
    this.mathPreview.className = "zc-math-preview";
    this.mathPreview.hidden = true;
    const mathHeader = doc.createElement("header");
    const mathIdentity = doc.createElement("div");
    mathIdentity.className = "zc-math-preview-identity";
    const mathGlyph = doc.createElement("span");
    mathGlyph.className = "zc-math-preview-glyph";
    mathGlyph.textContent = "ƒx";
    this.mathPreviewTitle = doc.createElement("strong");
    this.mathPreviewTitle.textContent = "Formula Preview";
    mathIdentity.append(mathGlyph, this.mathPreviewTitle);
    const mathActions = doc.createElement("div");
    mathActions.className = "zc-math-preview-actions";
    this.mathPreviewCollapse = doc.createElement("button");
    this.mathPreviewCollapse.type = "button";
    this.mathPreviewCollapse.textContent = "Collapse";
    this.mathPreviewCollapse.title = "Collapse Formula Preview";
    this.mathPreviewCollapse.addEventListener("click", () => {
      if (!this.current) return;
      this.current.mathPreviewCollapsed = !this.current.mathPreviewCollapsed;
      this.renderMathPreview(this.current);
      requestAnimationFrame(() => this.fitCurrent());
    });
    const mathClose = doc.createElement("button");
    mathClose.type = "button";
    mathClose.className = "zc-math-preview-close";
    mathClose.textContent = "×";
    mathClose.title = "Close Formula Preview";
    mathClose.setAttribute("aria-label", "Close Formula Preview");
    mathClose.addEventListener("click", () => {
      if (!this.current) return;
      this.current.mathPreviewDismissed = true;
      this.renderMathPreview(this.current);
      requestAnimationFrame(() => this.fitCurrent());
    });
    mathActions.append(this.mathPreviewCollapse, mathClose);
    mathHeader.append(mathIdentity, mathActions);
    this.mathPreviewBody = doc.createElement("div");
    this.mathPreviewBody.className = "zc-math-preview-body";
    this.mathPreview.append(mathHeader, this.mathPreviewBody);

    this.surface = doc.createElement("div");
    this.surface.className = "zc-terminal-surface";
    this.status = doc.createElement("div");
    this.status.className = "zc-terminal-status";
    this.status.textContent = "Opening starts a local Terminal in the QLab repository root";
    this.surface.appendChild(this.status);
    root.append(bar, context, this.mathPreview, this.surface);
    host.replaceChildren(root);
    this.root = root;

    const ResizeObserverConstructor = doc.defaultView?.ResizeObserver;
    if (ResizeObserverConstructor) {
      this.resizeObserver = new ResizeObserverConstructor(() => {
        if (this.visible) this.fitCurrent();
      });
      this.resizeObserver.observe(root);
    }
  }

  unmount(host: HTMLElement): void {
    if (this.host !== host) return;
    this.setVisible(false);
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.root?.remove();
    this.root = null;
    this.surface = null;
    this.title = null;
    this.paperTitle = null;
    this.contextMeta = null;
    this.zotkitStatus = null;
    this.status = null;
    this.agentPicker = null;
    this.mathPreview = null;
    this.mathPreviewBody = null;
    this.mathPreviewTitle = null;
    this.mathPreviewCollapse = null;
    this.mathPreviewToggle = null;
    this.host = null;
  }

  setVisible(visible: boolean): void {
    this.visible = visible;
    if (this.current && !this.current.disposed) {
      this.current.terminal.options.cursorBlink = visible;
    }
    if (!visible) {
      for (const session of this.sessions.values()) this.clearMathScanTimer(session);
    }
    else {
      if (this.current?.mathCandidatePending) this.scheduleMathScan(this.current);
      requestAnimationFrame(() => this.fitCurrent());
    }
    this.scheduleIdleCleanup();
  }

  async open(options: TerminalPaperOptions): Promise<void> {
    this.mount(options.host);
    this.currentOptions = { ...options };
    this.setVisible(true);
    this.setZotkitStatus("checking");
    this.showStatus("Connecting to the local CLI…");
    // This is the deliberate lazy-start boundary. `mount()` never gets here.
    if (!this.bridge.connected) await this.bridge.start();
    await this.activate(options);
  }

  async switchPaper(options: TerminalPaperOptions): Promise<void> {
    if (!this.hasLiveSessions) return;
    this.mount(options.host);
    this.currentOptions = { ...options };
    this.setVisible(true);
    await this.activate({
      ...options,
      agent: (this.agentPicker?.value as TerminalAgent) || options.agent || "shell",
    });
  }

  /** Insert text into the live TUI. No carriage return is added by default. */
  insert(text: string, submit = false): void {
    if (!this.current || this.current.exited || !this.current.started) return;
    this.touchSession(this.current);
    const input = text + (submit ? "\r" : "");
    if (!this.current.ready) {
      const available = MAX_PENDING_TERMINAL_INPUT - this.current.pendingInput.length;
      if (available <= 0) {
        this.showError("Text queued while the CLI was starting is too long; retry after the terminal is ready");
        return;
      }
      this.current.pendingInput += input.slice(0, available);
      if (input.length > available) {
        this.showError("Text inserted while the CLI was starting was limited to 128 KiB");
      }
    }
    else this.bridge.input(this.current.sessionId, input);
    this.focus();
  }

  focus(): void {
    this.current?.terminal.focus();
  }

  showError(error: unknown): void {
    const message = error instanceof Error ? error.message : String(error);
    if (this.current?.started && !this.current.exited) {
      this.showSessionError(this.current, message);
      return;
    }
    this.showStatus(message, true);
  }

  private showSessionError(session: TerminalSession, message: string): void {
    if (session.disposed) return;
    session.terminal.writeln(`\r\n\x1b[31m[Zotkit] ${message}\x1b[0m`);
  }

  destroy(): void {
    if (this.host) this.unmount(this.host);
    if (this.idleCleanupTimer) clearTimeout(this.idleCleanupTimer);
    this.idleCleanupTimer = null;
    for (const session of [...this.sessions.values()]) this.disposeSession(session, true);
    this.unsubscribe();
  }

  private async activate(options: TerminalPaperOptions): Promise<void> {
    const activationSequence = ++this.activationSequence;
    const agent = options.agent || "shell";
    const key = `${options.paperKey}:${agent}`;
    let session = this.sessions.get(key);
    if (
      session
      && (session.workspace !== options.workspace
        || session.workingDirectory !== options.workingDirectory
        || session.pdfPath !== (options.pdfPath || null)
        || session.librarySnapshotPath !== (options.librarySnapshotPath || null))
    ) {
      // A linked attachment can be relinked while Zotero remains open. Never
      // label an existing PTY with a cwd it does not actually have.
      this.disposeSession(session, true);
      session = undefined;
    }
    if (!session || session.exited) {
      if (session) {
        session.terminal.dispose();
        this.sessions.delete(key);
      }
      this.evictOldestSession();
      session = this.createSession(key, options, agent);
      this.sessions.set(key, session);
    }
    if (this.current && this.current !== session && !this.current.disposed) {
      this.current.terminal.options.cursorBlink = false;
      this.clearMathScanTimer(this.current);
    }
    session.lastUsed = Date.now();
    this.current = session;
    session.terminal.options.cursorBlink = this.visible;
    this.surface!.replaceChildren(session.element);
    this.agentPicker!.value = agent;
    this.updateHeader(options, agent);
    this.renderMathPreview(session);
    if (session.mathCandidatePending) this.scheduleMathScan(session);
    if (!session.started) await this.ensureSessionStarted(session);
    else this.setZotkitStatus(session.zotkitAvailable ? "enabled" : "missing");
    if (
      activationSequence !== this.activationSequence
      || this.current !== session
      || session.disposed
    ) return;
    this.scheduleIdleCleanup();
    requestAnimationFrame(() => {
      this.fitCurrent();
      session!.terminal.focus();
    });
  }

  private createSession(
    key: string,
    options: TerminalPaperOptions,
    agent: TerminalAgent,
  ): TerminalSession {
    const doc = this.root!.ownerDocument;
    const element = doc.createElement("div");
    element.className = "zc-terminal-instance";
    const terminal = new Terminal({
      allowProposedApi: false,
      cursorBlink: this.visible,
      cursorStyle: "bar",
      fontFamily: '"SFMono-Regular", "SF Mono", Menlo, Monaco, monospace',
      fontSize: 12,
      lineHeight: 1.22,
      scrollback: TERMINAL_SCROLLBACK_LINES,
      macOptionIsMeta: true,
      convertEol: false,
      theme: {
        background: "#151419",
        foreground: "#e9e7ed",
        cursor: "#7ba8ff",
        selectionBackground: "#0a84ff66",
        black: "#25232a",
        red: "#ff6b67",
        green: "#61d887",
        yellow: "#f3c969",
        blue: "#7ba8ff",
        magenta: "#b792ff",
        cyan: "#66d9d0",
        white: "#e9e7ed",
      },
    });
    const fit = new FitAddon();
    terminal.loadAddon(fit);
    terminal.loadAddon(new WebLinksAddon((_event, uri) => Zotero.launchURL(uri)));
    // xterm measures its character cell while `open()` runs. Opening a
    // detached element leaves the renderer at 0 x 0 in Zotero even after the
    // surrounding pane becomes visible, so attach it to the flexible terminal
    // surface before asking xterm to initialize.
    this.surface!.replaceChildren(element);
    terminal.open(element);
    const session: TerminalSession = {
      key,
      sessionId: randomID("term").slice(0, 64),
      agent,
      paperKey: options.paperKey,
      paperTitle: options.paperTitle,
      workspace: options.workspace,
      workingDirectory: options.workingDirectory,
      pdfPath: options.pdfPath || null,
      librarySnapshotPath: options.librarySnapshotPath || null,
      terminal,
      fit,
      element,
      started: false,
      ready: false,
      exited: false,
      disposed: false,
      startPromise: null,
      readyTimer: null,
      startupOutput: "",
      pendingInput: "",
      zotkitAvailable: null,
      lastUsed: Date.now(),
      mathExpressions: [],
      mathFingerprint: "",
      mathDetectionTail: "",
      mathCandidatePending: false,
      mathPreviewCollapsed: false,
      mathPreviewDismissed: false,
      mathScanTimer: null,
    };
    terminal.onData((data) => {
      if (!session.disposed && !session.exited && session.started) {
        this.touchSession(session);
        this.bridge.input(session.sessionId, data);
      }
    });
    terminal.onResize(({ rows, cols }) => {
      if (!session.exited && session.started) this.bridge.resize(session.sessionId, rows, cols);
    });
    return session;
  }

  private async startSession(session: TerminalSession): Promise<void> {
    session.terminal.writeln("\x1b[90mStarting QLab terminal…\x1b[0m");
    session.zotkitAvailable = Boolean(session.librarySnapshotPath);
    this.setZotkitStatus(session.zotkitAvailable ? "enabled" : "missing");
    let argv: string[];
    if (session.agent === "shell") {
      const shell = await findLoginShell();
      if (!shell) throw new Error("No local shell was found");
      argv = [shell, "-l"];
    }
    else {
      const readerServer = {
        command: this.bridge.helperPath,
        args: ["--mcp-stdio", "--context", session.workspace],
      };
      const zotkitServer = {
        command: this.bridge.helperPath,
        args: ["--zotkit-mcp", "--context", session.workspace],
      };
      const executable = await findExecutable("codex");
      if (!executable) throw new Error("Codex CLI Not Found");
      const readerArguments = session.pdfPath
        ? [
            "-c", `developer_instructions=${tomlString(CODEX_READER_DEVELOPER_INSTRUCTIONS)}`,
            ...codexMcpArguments("zotero_reader", readerServer),
            ...codexMcpArguments("zotkit_library", zotkitServer),
          ]
        : [];
      argv = [
        executable,
        "--no-alt-screen",
        "--disable", "code_mode_host",
        "--sandbox", "read-only",
        "--ask-for-approval", "untrusted",
        "--cd", session.workingDirectory,
        ...readerArguments,
      ];
    }
    await this.bridge.spawn(session.sessionId, {
      argv,
      cwd: session.workingDirectory,
      env: {
        TERM: "xterm-256color",
        COLORTERM: "truecolor",
        PATH: prependExecutableDirectory(this.bridge.zotkitPath),
        ZOTKIT_PAPER_KEY: session.paperKey,
        ZOTKIT_CLI: this.bridge.zotkitPath,
        ZOTKIT_READER_CONTEXT: PathUtils.join(session.workspace, "context.json"),
        ZOTKIT_SNAPSHOT: session.librarySnapshotPath || "",
        ZOTKIT_PDF_PATH: session.pdfPath || "",
        QLAB_ROOT: session.workingDirectory,
        // Compatibility for users who referenced the original variables.
        ZOTEROCHAT_PAPER_KEY: session.paperKey,
        ZOTEROCHAT_CONTEXT: PathUtils.join(session.workspace, "context.json"),
      },
      rows: session.terminal.rows || 24,
      cols: session.terminal.cols || 52,
    });
    session.started = true;
    if (session.agent === "shell") this.markSessionReady(session);
    if (session.disposed) {
      this.bridge.closeSession(session.sessionId);
      return;
    }
    if (session.ready) this.flushPendingInput(session);
  }

  private async ensureSessionStarted(session: TerminalSession): Promise<void> {
    if (session.started) return;
    if (!session.startPromise) {
      session.startPromise = (async () => {
        try {
          await this.startSession(session);
        }
        catch (error) {
          // Spawn can fail after the helper has accepted the ID. Close both the
          // native side and the local xterm state before allowing a retry.
          this.bridge.closeSession(session.sessionId);
          if (!session.disposed) this.disposeSession(session, false);
          throw error;
        }
        finally {
          session.startPromise = null;
        }
      })();
    }
    await session.startPromise;
  }

  private updateHeader(options: TerminalPaperOptions, agent: TerminalAgent): void {
    if (this.title) {
      this.title.textContent = agent === "codex" ? "QLab — Codex" : "QLab — Terminal";
    }
    if (this.paperTitle) this.paperTitle.textContent = options.paperTitle;
    if (this.contextMeta) {
      const page = options.pageLabel ? `PDF ${options.pageLabel} · ` : "";
      this.contextMeta.textContent = `${page}cwd: ${options.workingDirectory}`;
      this.contextMeta.title = this.contextMeta.textContent;
    }
  }

  /**
   * Output is only a cheap wake-up signal. The actual formula source is read
   * later from xterm's rendered buffer, after its parser has applied cursor
   * movement, line clearing, and TUI redraws.
  */
  private observeMathOutput(session: TerminalSession, output: string): void {
    if (session.disposed) return;
    // Most TUI redraw chunks contain only cursor/colour CSI sequences. Avoid
    // even ANSI cleanup for those high-frequency spinner updates.
    if (!/[\\$^_•⏺]/.test(output) && !/(?:^|[\r\n])[ \t]*[\[\]]/.test(output)) return;
    const plain = stripTerminalControlSequences(output);
    if (!/[\\$\[\]]/.test(plain)) return;
    session.mathDetectionTail = (session.mathDetectionTail + "\n" + plain)
      .slice(-MATH_DETECTION_TAIL_CHARS);
    if (!hasMathPreviewCandidate(session.mathDetectionTail)) return;
    session.mathCandidatePending = true;
    if (!this.isVisibleSession(session)) return;
    this.scheduleMathScan(session);
  }

  private scheduleMathScan(session: TerminalSession): void {
    if (!session.mathCandidatePending || !this.isVisibleSession(session)) return;
    this.clearMathScanTimer(session);
    session.mathScanTimer = setTimeout(() => {
      session.mathScanTimer = null;
      if (!this.isVisibleSession(session)) return;
      this.scanMathPreview(session);
    }, MATH_PREVIEW_DEBOUNCE_MS);
  }

  private scanMathPreview(session: TerminalSession): void {
    const expressions = extractTerminalMath(this.readRenderedTerminalBuffer(session));
    session.mathCandidatePending = false;
    if (!expressions.length) return;
    const fingerprint = expressions.map(mathExpressionFingerprint).join("\u001f");
    session.mathDetectionTail = "";
    if (fingerprint === session.mathFingerprint) return;
    session.mathExpressions = expressions;
    session.mathFingerprint = fingerprint;
    this.renderMathPreview(session);
    requestAnimationFrame(() => this.fitCurrent());
  }

  private readRenderedTerminalBuffer(session: TerminalSession): string {
    const buffer = session.terminal.buffer.active;
    const start = Math.max(0, buffer.length - MATH_PREVIEW_BUFFER_LINES);
    const logicalLines: string[] = [];
    for (let index = start; index < buffer.length; index++) {
      const line = buffer.getLine(index);
      if (!line) continue;
      const text = line.translateToString(true);
      if (line.isWrapped && logicalLines.length) {
        logicalLines[logicalLines.length - 1] += text;
      }
      else logicalLines.push(text);
    }
    return logicalLines.join("\n").slice(-MATH_PREVIEW_BUFFER_CHARS);
  }

  private renderMathPreview(session: TerminalSession): void {
    if (this.current !== session || !this.mathPreview || !this.mathPreviewBody) return;
    const hasExpressions = session.mathExpressions.length > 0;
    if (this.mathPreviewToggle) {
      this.mathPreviewToggle.disabled = !hasExpressions;
      this.mathPreviewToggle.classList.toggle("has-formulas", hasExpressions);
      this.mathPreviewToggle.setAttribute(
        "aria-pressed",
        String(hasExpressions && !session.mathPreviewDismissed),
      );
      this.mathPreviewToggle.title = hasExpressions
        ? `Preview the latest ${session.mathExpressions.length} formulas`
        : "Formula preview becomes available after LaTeX output is detected";
    }
    if (!hasExpressions || session.mathPreviewDismissed) {
      this.mathPreview.hidden = true;
      this.mathPreviewBody.replaceChildren();
      return;
    }

    this.mathPreview.hidden = false;
    this.mathPreview.classList.toggle("is-collapsed", session.mathPreviewCollapsed);
    if (this.mathPreviewTitle) {
      this.mathPreviewTitle.textContent = `Formula Preview · ${session.mathExpressions.length}`;
    }
    if (this.mathPreviewCollapse) {
      this.mathPreviewCollapse.textContent = session.mathPreviewCollapsed ? "Expand" : "Collapse";
      this.mathPreviewCollapse.title = session.mathPreviewCollapsed
        ? "Expand Formula Preview"
        : "Collapse Formula Preview";
    }
    this.mathPreviewBody.replaceChildren();
    if (session.mathPreviewCollapsed) return;

    const doc = this.mathPreview.ownerDocument;
    session.mathExpressions.forEach((expression, index) => {
      const card = doc.createElement("article");
      card.className = "zc-math-preview-card";
      const label = doc.createElement("span");
      label.className = "zc-math-preview-label";
      label.textContent = index === session.mathExpressions.length - 1
        ? "Latest"
        : `−${session.mathExpressions.length - index - 1}`;
      const formula = doc.createElement("div");
      formula.className = "zc-math-preview-formula";
      // renderMarkdown delegates math to the hardened KaTeX path with
      // trust:false, strict:error, bounded expansion, and unsafe nodes removed.
      formula.appendChild(renderMarkdown(doc, `\\[\n${expression}\n\\]`));
      card.append(label, formula);
      this.mathPreviewBody!.appendChild(card);
    });
  }

  private isVisibleSession(session: TerminalSession): boolean {
    return this.visible
      && this.current === session
      && Boolean(this.root?.isConnected)
      && !session.disposed;
  }

  private clearMathScanTimer(session: TerminalSession): void {
    if (session.mathScanTimer === null) return;
    clearTimeout(session.mathScanTimer);
    session.mathScanTimer = null;
  }

  private setZotkitStatus(state: "checking" | "enabled" | "missing"): void {
    if (!this.zotkitStatus) return;
    this.zotkitStatus.classList.remove("is-checking", "is-enabled", "is-missing");
    this.zotkitStatus.classList.add(`is-${state}`);
    if (state === "enabled") {
      this.zotkitStatus.textContent = "Built-in Zotkit: enabled";
      this.zotkitStatus.title = "Built-in read-only CLI and zotkit_library MCP; no Python, credentials, or extra installation required";
    }
    else if (state === "missing") {
      this.zotkitStatus.textContent = "Built-in Zotkit: snapshot unavailable";
      this.zotkitStatus.title = "The current library metadata snapshot is unavailable; Reader MCP is still available";
    }
    else {
      this.zotkitStatus.textContent = "Built-in Zotkit: preparing…";
      this.zotkitStatus.title = "Preparing built-in read-only library tools";
    }
  }

  private showStatus(message: string, error = false): void {
    if (!this.surface || !this.status) return;
    if (!this.status.isConnected) this.surface.replaceChildren(this.status);
    this.status.textContent = message;
    this.status.classList.toggle("is-error", error);
  }

  private fitCurrent(): void {
    if (!this.current || this.current.disposed || !this.root?.isConnected) return;
    try { this.current.fit.fit(); }
    catch { /* the Item Pane may be between layout passes */ }
  }

  private sessionByID(sessionId: string): TerminalSession | undefined {
    return [...this.sessions.values()].find((item) => item.sessionId === sessionId);
  }

  private evictOldestSession(): void {
    if (this.sessions.size < MAX_TERMINAL_SESSIONS) return;
    const candidates = [...this.sessions.values()]
      .filter((session) => session !== this.current)
      .sort((left, right) => left.lastUsed - right.lastUsed);
    const oldest = candidates[0];
    if (oldest) this.disposeSession(oldest, true);
  }

  private touchSession(session: TerminalSession): void {
    session.lastUsed = Date.now();
    this.scheduleIdleCleanup();
  }

  private observeStartupOutput(session: TerminalSession, output: string): void {
    if (session.ready || session.disposed || session.exited) return;
    session.startupOutput = (session.startupOutput + output).slice(-8_192);
    const prompt = session.agent === "codex" ? "›" : "❯";
    if (session.startupOutput.includes(prompt)) this.markSessionReady(session);
  }

  private markSessionReady(session: TerminalSession): void {
    if (session.ready || session.disposed || session.exited) return;
    session.ready = true;
    session.startupOutput = "";
    this.clearReadyTimer(session);
    this.flushPendingInput(session);
  }

  private flushPendingInput(session: TerminalSession): void {
    if (!session.started || !session.ready || !session.pendingInput) return;
    const input = session.pendingInput;
    session.pendingInput = "";
    this.bridge.input(session.sessionId, input);
  }

  private clearReadyTimer(session: TerminalSession): void {
    if (session.readyTimer === null) return;
    clearTimeout(session.readyTimer);
    session.readyTimer = null;
  }

  private closeIdleSessions(now = Date.now()): void {
    for (const session of [...this.sessions.values()]) {
      const isVisible = this.visible && this.current === session && Boolean(this.root?.isConnected);
      if (isVisible || now - session.lastUsed < TERMINAL_SESSION_IDLE_MS) continue;
      this.disposeSession(session, true);
    }
  }

  private scheduleIdleCleanup(): void {
    if (this.idleCleanupTimer) clearTimeout(this.idleCleanupTimer);
    this.idleCleanupTimer = null;
    const candidates = [...this.sessions.values()].filter(
      (session) => !(this.visible && this.current === session && this.root?.isConnected),
    );
    if (!candidates.length) return;
    const nextExpiry = Math.min(
      ...candidates.map((session) => session.lastUsed + TERMINAL_SESSION_IDLE_MS),
    );
    this.idleCleanupTimer = setTimeout(() => {
      this.idleCleanupTimer = null;
      this.closeIdleSessions();
      this.scheduleIdleCleanup();
    }, Math.max(0, nextExpiry - Date.now()));
  }

  private disposeSession(session: TerminalSession, closeProcess: boolean): void {
    if (session.disposed) return;
    session.disposed = true;
    this.clearReadyTimer(session);
    this.clearMathScanTimer(session);
    session.pendingInput = "";
    if (closeProcess && session.started && !session.exited) {
      this.bridge.closeSession(session.sessionId);
    }
    session.exited = true;
    session.terminal.dispose();
    this.sessions.delete(session.key);
    if (this.current === session) {
      this.current = null;
      if (this.mathPreview) this.mathPreview.hidden = true;
      if (this.mathPreviewToggle) {
        this.mathPreviewToggle.disabled = true;
        this.mathPreviewToggle.classList.remove("has-formulas");
      }
    }
  }

  private trafficButton(
    doc: Document,
    className: string,
    title: string,
    callback: () => void,
  ): HTMLButtonElement {
    const button = doc.createElement("button");
    button.type = "button";
    button.className = className;
    button.title = title;
    button.setAttribute("aria-label", title);
    button.addEventListener("click", callback);
    return button;
  }
}

/** Fast gate used before any xterm buffer walk. */
export function hasMathPreviewCandidate(output: string): boolean {
  const plain = stripTerminalControlSequences(output);
  if (/\\\[|\\\(|\$\$/.test(plain)) return true;
  const bracket = /(?:^|\n)[ \t]*(?:[•⏺][ \t]*)?\[([\s\S]{0,2000})/.exec(plain);
  return Boolean(bracket && looksLikeLatex(bracket[1] || ""));
}

/**
 * Extract at most the three newest unique formulas from xterm's plain buffer.
 * Square brackets count only when they form a standalone line/block and the
 * body has a strong LaTeX signal, which excludes citations and CLI badges.
 */
export function extractTerminalMath(bufferText: string): string[] {
  const text = stripTerminalControlSequences(bufferText).slice(-MATH_PREVIEW_BUFFER_CHARS);
  const matches: Array<{ index: number; expression: string }> = [];
  const collect = (pattern: RegExp, capture = 1) => {
    for (const match of text.matchAll(pattern)) {
      const expression = normalizeMathExpression(match[capture] || "");
      if (!expression || expression.length > MAX_MATH_EXPRESSION_CHARS) continue;
      matches.push({ index: match.index || 0, expression });
    }
  };

  collect(/\\\[([\s\S]{1,2000}?)\\\]/g);
  collect(/\$\$([\s\S]{1,2000}?)\$\$/g);
  collect(/\\\(([\s\S]{1,2000}?)\\\)/g);
  for (const match of text.matchAll(
    /(?:^|\n)[ \t]*(?:[•⏺][ \t]*)?\[[ \t]*(?:\n)?([\s\S]{1,2000}?)(?:\n)?[ \t]*(?:[•⏺][ \t]*)?\][ \t]*(?=\n|$)/g,
  )) {
    const expression = normalizeMathExpression(match[1] || "");
    if (!expression || expression.length > MAX_MATH_EXPRESSION_CHARS) continue;
    if (!looksLikeLatex(expression)) continue;
    matches.push({ index: match.index || 0, expression });
  }

  matches.sort((left, right) => left.index - right.index);
  const selected: string[] = [];
  const seen = new Set<string>();
  for (let index = matches.length - 1; index >= 0; index--) {
    const expression = matches[index]!.expression;
    const fingerprint = mathExpressionFingerprint(expression);
    if (seen.has(fingerprint)) continue;
    seen.add(fingerprint);
    selected.unshift(expression);
    if (selected.length === MAX_MATH_PREVIEW_FORMULAS) break;
  }
  return selected;
}

function looksLikeLatex(expression: string): boolean {
  return /\\[A-Za-z]{2,}/.test(expression)
    || /(?:[A-Za-z0-9)}\]])\s*[_^]\s*(?:\{|[A-Za-z0-9\\])/.test(expression)
    || /(?:\\(?:alpha|beta|gamma|delta|theta|lambda|mu|pi|sigma|omega)|[α-ωΑ-Ω])/.test(expression);
}

function normalizeMathExpression(expression: string): string {
  return expression
    .replace(/\u00a0/g, " ")
    .split("\n")
    .map((line) => line.trim())
    .join("\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function mathExpressionFingerprint(expression: string): string {
  return normalizeMathExpression(expression).replace(/\s+/g, " ");
}

function stripTerminalControlSequences(text: string): string {
  return text
    // OSC sequences, including hyperlinks, terminated by BEL or ST.
    .replace(/\x1b\][^\x07]*(?:\x07|\x1b\\)/g, "")
    // CSI cursor/style commands emitted by the Codex TUI.
    .replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, "")
    .replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g, "");
}

function codexMcpArguments(
  name: string,
  server: { command: string; args: string[] },
): string[] {
  return [
    "-c", `mcp_servers.${name}.command=${tomlString(server.command)}`,
    "-c", `mcp_servers.${name}.args=[${server.args.map(tomlString).join(",")}]`,
    "-c", `mcp_servers.${name}.enabled=true`,
    // Both XPI-bundled servers expose query-only tools. Approve only these two
    // servers up front so Codex 0.145 does not hide an MCP approval request
    // inside unified exec; shell commands and the user's other MCPs retain the
    // global untrusted approval policy.
    "-c", `mcp_servers.${name}.default_tools_approval_mode=${tomlString("approve")}`,
    "-c", `mcp_servers.${name}.tool_timeout_sec=10`,
  ];
}

function tomlString(value: string): string {
  return JSON.stringify(value);
}

export function prependExecutableDirectory(executable: string): string {
  const separator = executable.lastIndexOf("/");
  const directory = separator > 0 ? executable.slice(0, separator) : executable;
  let inherited = "";
  try { inherited = Services.env.get("PATH") || ""; }
  catch { /* use the minimal macOS path below */ }
  const fallback = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin";
  // Finder-launched GUI apps often inherit a non-empty but incomplete PATH
  // such as /usr/bin:/bin. Always add the standard Homebrew/local locations
  // so the user's existing Codex MCP commands (for example `node`) still work.
  return [...new Set(
    [directory, ...inherited.split(":"), ...fallback.split(":")].filter(Boolean),
  )].join(":");
}
