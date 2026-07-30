import { resolveEditablePath } from "./editor-tree";

/**
 * Handing a QMD to a real code editor.
 *
 * A pane shared with the chat column is a bad place to write in, and the
 * editor a researcher already has is better at it than anything that would fit
 * there. So the plugin previews, and writing goes to Cursor or VS Code — the
 * same move the dashboard makes when it hands a prompt to Codex through a URL
 * scheme instead of building a chat of its own.
 *
 * The repository is opened as the workspace and the file is opened inside it,
 * because that is the state writing actually needs: search, Git, the Quarto
 * extension, and the neighbouring notes.
 */

export interface ExternalEditorApp {
  id: string;
  /** What the button says. */
  label: string;
  /** The macOS application bundle name `open -a` takes. */
  application: string;
  /** Where the bundle lives, relative to an applications directory. */
  bundle: string;
  /** Resolved installed bundle path, present after discovery. */
  path?: string;
}

/** Uses macOS's own application icon without redistributing editor artwork. */
export function externalEditorIconUrl(editor: ExternalEditorApp): string | null {
  if (!editor.path?.startsWith("/")) return null;
  return `moz-icon://${encodeURI(`file://${editor.path}`)}?size=32`;
}

/**
 * The editors offered, most specialised first.
 *
 * Cursor leads because a user who installed it installed it to write in.
 */
export const EXTERNAL_EDITORS: readonly ExternalEditorApp[] = [
  { id: "cursor", label: "Cursor", application: "Cursor", bundle: "Cursor.app" },
  {
    id: "vscode",
    label: "VS Code",
    application: "Visual Studio Code",
    bundle: "Visual Studio Code.app",
  },
  { id: "vscodium", label: "VSCodium", application: "VSCodium", bundle: "VSCodium.app" },
  { id: "zed", label: "Zed", application: "Zed", bundle: "Zed.app" },
  { id: "sublime", label: "Sublime Text", application: "Sublime Text", bundle: "Sublime Text.app" },
];

/** Where macOS keeps applications, in the order a launcher should prefer. */
const APPLICATION_DIRECTORIES = ["/Applications", "/System/Applications"];

export interface ExternalEditorRuntime {
  exists(path: string): Promise<boolean>;
  /** Resolves aliases and symbolic links before a file crosses the process boundary. */
  realPath(path: string): Promise<string>;
  /** The user's home directory, for `~/Applications`. */
  homeDirectory(): string;
  launch(application: string, paths: readonly string[]): Promise<void>;
}

/**
 * The editors actually installed, in preference order.
 *
 * Detection is by bundle rather than by asking the shell, because a `code`
 * or `cursor` command on `PATH` is a separate thing a user may or may not have
 * installed, and its absence says nothing about whether the application is
 * there.
 */
export async function installedEditors(
  runtime: ExternalEditorRuntime,
): Promise<ExternalEditorApp[]> {
  const home = runtime.homeDirectory().replace(/[\\/]+$/, "");
  const directories = [...APPLICATION_DIRECTORIES, ...(home ? [`${home}/Applications`] : [])];
  const found: ExternalEditorApp[] = [];
  for (const editor of EXTERNAL_EDITORS) {
    for (const directory of directories) {
      const path = `${directory}/${editor.bundle}`;
      if (await runtime.exists(path)) {
        found.push({ ...editor, path });
        break;
      }
    }
  }
  return found;
}

/**
 * Opens one QMD in an external editor, with the repository as its workspace.
 *
 * The two paths go in one invocation: `open` passes both to the application,
 * which reads the directory as a folder to open and the file as a file to
 * show in it. Doing it as two launches would race, and the second could land
 * in a window the first had not finished creating.
 */
export async function openInExternalEditor(
  runtime: ExternalEditorRuntime,
  editor: ExternalEditorApp,
  repoRoot: string,
  relativePath: string,
): Promise<void> {
  // Containment is checked here as well as at the preview, because this hands
  // a path to another application entirely.
  const lexicalRoot = repoRoot.replace(/[\\/]+$/, "");
  const lexicalPath = resolveEditablePath(lexicalRoot, relativePath);
  const treeName = relativePath.split("/", 1)[0]!;
  const lexicalTreeRoot = `${lexicalRoot}/${treeName}`;
  const [realRoot, realTreeRoot, realPath] = await Promise.all([
    runtime.realPath(lexicalRoot),
    runtime.realPath(lexicalTreeRoot),
    runtime.realPath(lexicalPath),
  ]);
  const expectedTreeRoot = `${realRoot}/${treeName}`;
  const expectedPath = `${realTreeRoot}/${relativePath.slice(treeName.length + 1)}`;
  if (realTreeRoot !== expectedTreeRoot || realPath !== expectedPath) {
    throw new Error("The selected QMD uses a symbolic link or resolves outside its declared tree");
  }
  await runtime.launch(editor.application, [realRoot, realPath]);
}

/** Chooses the editor to use: the remembered one if it is still installed. */
export function preferredEditor(
  installed: readonly ExternalEditorApp[],
  rememberedId: string,
): ExternalEditorApp | null {
  return installed.find((editor) => editor.id === rememberedId) ?? installed[0] ?? null;
}

export function createExternalEditorRuntime(
  spawn: (argv: readonly string[]) => Promise<void>,
): ExternalEditorRuntime {
  return {
    exists: (path) => IOUtils.exists(path),
    realPath: async (path) => {
      const file = Components.classes["@mozilla.org/file/local;1"]
        .createInstance(Components.interfaces.nsIFile);
      file.initWithPath(path);
      file.normalize();
      return String(file.path || path);
    },
    homeDirectory: () => {
      try {
        return String(Services.dirsvc.get("Home", Ci.nsIFile).path || "");
      }
      catch {
        return "";
      }
    },
    launch: (application, paths) => spawn(["/usr/bin/open", "-a", application, ...paths]),
  };
}
