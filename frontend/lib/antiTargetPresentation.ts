import { frontendMessage, type FrontendText, type Translate } from "./frontendError";
export type AntiTargetTextField = "risk" | "targetFunction" | "bioDetails" | "mitigationSar";
const KEYS: Readonly<Record<string, Partial<Record<AntiTargetTextField, string>>>> = {
  "5VA1": {
    "risk": "pr_anti_5VA1_risk",
    "targetFunction": "pr_anti_5VA1_targetFunction",
    "bioDetails": "pr_anti_5VA1_bioDetails",
    "mitigationSar": "pr_anti_5VA1_mitigationSar"
  },
  "4NY4": {
    "risk": "pr_anti_4NY4_risk",
    "targetFunction": "pr_anti_4NY4_targetFunction",
    "bioDetails": "pr_anti_4NY4_bioDetails",
    "mitigationSar": "pr_anti_4NY4_mitigationSar"
  },
  "7SRQ": {
    "risk": "pr_anti_7SRQ_risk",
    "targetFunction": "pr_anti_7SRQ_targetFunction",
    "bioDetails": "pr_anti_7SRQ_bioDetails",
    "mitigationSar": "pr_anti_7SRQ_mitigationSar"
  }
};
export function antiTargetFieldMessage(pdbId: string, field: AntiTargetTextField, fallback: string): FrontendText {
  const key = KEYS[pdbId]?.[field];
  return key ? frontendMessage(key) : fallback;
}
export function antiTargetFieldText(pdbId: string, field: AntiTargetTextField, fallback: string, t: Translate): string {
  const message = antiTargetFieldMessage(pdbId, field, fallback);
  return typeof message === "string" ? message : message.render(t);
}

export type AntiTargetPreset = "default" | "all" | "none";

/** Resuelve una acción estable a IDs; nunca depende de la etiqueta traducida del botón. */
export function seleccionarAntiDianasPorAccion(
  action: AntiTargetPreset,
  defaultTargetIds: readonly string[],
  availableTargetIds: readonly string[],
): string[] {
  switch (action) {
    case "none": return [];
    case "default": return [...defaultTargetIds];
    case "all": return [...availableTargetIds];
  }
}
