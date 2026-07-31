export type ResearchObjectKind = "pdf" | "note" | "collection" | "draft";

export type ResearchActionID =
  | "summarize"
  | "evidence-qa"
  | "compare-papers"
  | "analyze-figure"
  | "write-draft";

export type ResearchActionMode =
  | "summary"
  | "evidence-qa"
  | "compare"
  | "figure"
  | "write-draft";

export interface ResearchObjectEnvelope {
  kind: ResearchObjectKind;
  title: string;
  libraryID?: string | number;
  itemKey?: string | null;
  attachmentKey?: string | null;
  collectionKey?: string | null;
  relativePath?: string | null;
}

export interface ResearchActionDefinition {
  id: ResearchActionID;
  label: string;
  description: string;
  objects: readonly ResearchObjectKind[];
}

export interface ResearchActionSkillBinding {
  name: "evidence-review" | "capture-chat-draft" | "expand-notes";
  path:
    | "skills/evidence-review/SKILL.md"
    | "skills/capture-chat-draft/SKILL.md"
    | "skills/expand-notes/SKILL.md";
  mode: ResearchActionMode;
}

export interface ResearchActionPromptContext {
  qlabRoot: string;
  object: ResearchObjectEnvelope;
}

const ALL_OBJECTS = ["pdf", "note", "collection", "draft"] as const;

/** The stable Action catalogue shown for the currently selected research object. */
export const RESEARCH_ACTIONS: readonly ResearchActionDefinition[] = Object.freeze([
  {
    id: "summarize",
    label: "Summarize",
    description: "Summarize the selected object with traceable evidence.",
    objects: ALL_OBJECTS,
  },
  {
    id: "evidence-qa",
    label: "Evidence QA",
    description: "Answer a question and audit each material claim against the source.",
    objects: ALL_OBJECTS,
  },
  {
    id: "compare-papers",
    label: "Compare Papers",
    description: "Compare the selected paper or collection on shared dimensions.",
    objects: ["pdf", "collection"],
  },
  {
    id: "analyze-figure",
    label: "Analyze Figure",
    description: "Analyze the visible or selected figure without inventing unreadable details.",
    objects: ["pdf"],
  },
  {
    id: "write-draft",
    label: "Write Draft",
    description: "Route verified material into the existing QMD Draft workflow.",
    objects: ALL_OBJECTS,
  },
]);

const READ_ONLY_MODES: Readonly<Partial<Record<ResearchActionID, ResearchActionMode>>> = {
  "summarize": "summary",
  "evidence-qa": "evidence-qa",
  "compare-papers": "compare",
  "analyze-figure": "figure",
};

const OBJECT_LABELS: Readonly<Record<ResearchObjectKind, string>> = {
  pdf: "PDF",
  note: "Note",
  collection: "Collection",
  draft: "Draft",
};

export function researchActionsForObject(kind: ResearchObjectKind): ResearchActionDefinition[] {
  return RESEARCH_ACTIONS.filter((action) => action.objects.includes(kind));
}

/** Resolve an Action to one canonical repository skill; no Action owns a second prompt workflow. */
export function researchActionSkill(
  actionID: ResearchActionID,
  kind: ResearchObjectKind,
): ResearchActionSkillBinding {
  const action = RESEARCH_ACTIONS.find((candidate) => candidate.id === actionID);
  if (!action || !action.objects.includes(kind)) {
    const actionLabel = action?.label || actionID;
    throw new Error(`${actionLabel} is not available for ${OBJECT_LABELS[kind]}`);
  }

  if (actionID === "write-draft") {
    if (kind === "pdf") {
      return {
        name: "capture-chat-draft",
        path: "skills/capture-chat-draft/SKILL.md",
        mode: "write-draft",
      };
    }
    return {
      name: "expand-notes",
      path: "skills/expand-notes/SKILL.md",
      mode: "write-draft",
    };
  }

  const mode = READ_ONLY_MODES[actionID];
  if (!mode) throw new Error(`No canonical skill mode is registered for ${action.label}`);
  return {
    name: "evidence-review",
    path: "skills/evidence-review/SKILL.md",
    mode,
  };
}

function normalizeRepositoryRoot(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) throw new Error("A selected Research Loop repository is required");
  if (trimmed === "/") return trimmed;
  return trimmed.replace(/[\\/]+$/u, "");
}

function validateObject(object: ResearchObjectEnvelope): void {
  if (!object.title.trim()) throw new Error("The research object needs a title");
  if (object.kind !== "draft") return;

  const relativePath = object.relativePath?.replace(/\\/gu, "/") || "";
  const segments = relativePath.split("/");
  const safe = relativePath.startsWith("drafts/")
    && relativePath.endsWith(".qmd")
    && segments.length > 1
    && segments.every((segment) => segment !== "" && segment !== "." && segment !== "..");
  if (!safe) throw new Error("A Draft Action requires a safe .qmd path under drafts/");
}

/** Prevent object content from terminating the sole untrusted-data envelope. */
function escapeObjectEnvelope(json: string): string {
  return json.replace(/<\s*\/\s*research_object\s*>/giu, (value) => (
    value.replaceAll("<", "＜").replaceAll(">", "＞")
  ));
}

/** Build the minimal hand-off: canonical skill, mode, and one untrusted object envelope. */
export function buildResearchActionPrompt(
  actionID: ResearchActionID,
  context: ResearchActionPromptContext,
): string {
  validateObject(context.object);
  const binding = researchActionSkill(actionID, context.object.kind);
  const object = {
    ...context.object,
    qlabRoot: normalizeRepositoryRoot(context.qlabRoot),
  };
  const envelope = escapeObjectEnvelope(JSON.stringify(object, null, 2));

  return [
    `Research Loop Action: ${actionID}`,
    `Mode: ${binding.mode}`,
    `Authority: Follow $${binding.name} at ${binding.path}.`,
    "<research_object>",
    envelope,
    "</research_object>",
  ].join("\n");
}
