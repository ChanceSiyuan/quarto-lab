import {
  configuredLibraryRoot,
  pathExists,
  prefBool,
  prefInt,
  prefString,
  profilePath,
  setPrefString
} from "./platform";

export type ReasoningEffort =
  | "minimal"
  | "low"
  | "medium"
  | "high"
  | "xhigh"
  | "max"
  | "ultra";

export interface ZoteroChatSettings {
  libraryRoot: string;
  qlabRoot: string;
  defaultModel: string;
  reasoningEffort: ReasoningEffort;
  approvalPolicy: string;
  terminalHeight: number;
  showReasoning: boolean;
  storageRoot: string;
}

export async function loadSettings(): Promise<ZoteroChatSettings> {
  const configured = configuredLibraryRoot();
  const qlabRoot = prefString("qlabRoot", "");
  return {
    libraryRoot: (await pathExists(configured)) ? configured : "",
    qlabRoot: qlabRoot && await pathExists(qlabRoot) ? qlabRoot : "",
    defaultModel: prefString("defaultModel", ""),
    reasoningEffort: normalizeEffort(prefString("reasoningEffort", "medium")),
    approvalPolicy: prefString("approvalPolicy", "never"),
    terminalHeight: Math.max(260, Math.min(prefInt("terminalHeight", 420), 900)),
    showReasoning: prefBool("showReasoning", false),
    storageRoot: profilePath()
  };
}

export function saveLibraryRoot(path: string): void {
  setPrefString("libraryRoot", path);
}

export function saveQLabRoot(path: string): void {
  setPrefString("qlabRoot", path);
}

function normalizeEffort(value: string): ReasoningEffort {
  return ["minimal", "low", "medium", "high", "xhigh", "max", "ultra"].includes(value)
    ? value as ReasoningEffort
    : "medium";
}
