import type { ModelOption } from "./sidebar";

export function defaultSelectableModel(models: ModelOption[]): string {
  const fallback = models.find((model) => model.isDefault) || models[0];
  return fallback?.id ?? "";
}

export function renderModelOptions(
  select: HTMLSelectElement,
  models: ModelOption[],
  selected: string,
): void {
  const doc = select.ownerDocument;
  select.replaceChildren();
  if (models.length) {
    const optgroup = doc.createElement("optgroup");
    optgroup.label = "本地 Codex";
    for (const model of models) {
      const option = doc.createElement("option");
      option.value = model.id;
      option.textContent = model.label;
      optgroup.appendChild(option);
    }
    select.appendChild(optgroup);
  }
  if (selected) select.value = selected;
}
