import {
  configuredLibraryRoot,
  pathExists,
  prefBool,
  prefInt,
  prefString,
  profilePath,
  setPrefString
} from "./platform";
import {
  parseStoredTargetPreferences,
  type StoredTargetPreferences,
} from "./repository-target";

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
  /** Display-only compatibility root until all UI consumers move to snapshots. */
  qlabRoot: string;
  repositoryTargets: StoredTargetPreferences;
  defaultModel: string;
  reasoningEffort: ReasoningEffort;
  approvalPolicy: string;
  terminalHeight: number;
  showReasoning: boolean;
  storageRoot: string;
}

export interface RawTargetMigrationInput {
  legacyQLabRoot: string;
  repositoryTargetsRaw: string;
}

/** Reads migration authorities without filesystem filtering or normalization. */
export function readRawTargetMigrationInput(): RawTargetMigrationInput {
  return {
    legacyQLabRoot: prefString("qlabRoot", ""),
    repositoryTargetsRaw: prefString("repositoryTargets", ""),
  };
}

export async function loadSettings(
  rawTargets: RawTargetMigrationInput = readRawTargetMigrationInput(),
): Promise<ZoteroChatSettings> {
  const configured = configuredLibraryRoot();
  const repositoryTargets = parseStoredTargetPreferences(rawTargets.repositoryTargetsRaw);
  const qlabRoot = repositoryTargets.migratedLegacy
    ? repositoryTargets.active?.canonicalRoot
      || repositoryTargets.pendingCandidate?.canonicalRoot
      || ""
    : rawTargets.legacyQLabRoot;
  return {
    libraryRoot: (await pathExists(configured)) ? configured : "",
    qlabRoot: qlabRoot && await pathExists(qlabRoot) ? qlabRoot : "",
    repositoryTargets,
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

export function saveRepositoryTargets(preferences: StoredTargetPreferences): void {
  setPrefString("repositoryTargets", JSON.stringify(preferences));
}

function normalizeEffort(value: string): ReasoningEffort {
  return ["minimal", "low", "medium", "high", "xhigh", "max", "ultra"].includes(value)
    ? value as ReasoningEffort
    : "medium";
}
