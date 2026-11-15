/**
 * Etiqueta y descripción de cada característica del Modelo A que aparece en el
 * SHAP, derivadas de la GRAMÁTICA de su nombre y no de un diccionario manual.
 *
 * Por qué una gramática: el diccionario anterior describía `ecif_N_don_C` como
 * «nitrógenos donadores del ligando y carbonos del bolsillo», y el extractor
 * (`rescoring/feature_extractor.py`) nombra las claves
 * `ecif_{tipo de PROTEÍNA}_{elemento del LIGANDO}`: el donador es de la proteína
 * y el ligando sólo se distingue por su elemento. Con 152 de las 167
 * características generadas así, enumerarlas a mano era invitar a que se
 * desalinearan (lo hicieron: nueve entradas describían características que el
 * modelo no tiene). Las pruebas recorren las 167 del modelo distribuido.
 */

export type Traductor = (key: string, values?: Readonly<Record<string, string | number>>) => string;

export type FeatureKind = "ecif" | "shell" | "descriptor" | "unknown";

export interface FeatureExplanation {
  label: string;
  desc: string;
  kind: FeatureKind;
}

export const ECIF_PROTEIN_TYPES = ["C_ali", "C_aro", "N_don", "N_acc", "O_don", "O_acc", "S", "other"] as const;
export const ECIF_LIGAND_TYPES = ["C", "N", "O", "S", "F", "Hal", "other"] as const;
export const SHELL_PROTEIN_ELEMENTS = ["C", "N", "O", "S"] as const;
export const SHELL_LIGAND_ELEMENTS = ["C", "N", "O", "S", "F", "P", "Cl", "Br"] as const;

/** Características que no son ECIF ni capas: descriptores del ligando, tamaño y pose. */
export const DESCRIPTOR_FEATURES = [
  "vina_best_score", "mw", "log_mw", "logp", "tpsa", "hbd", "hba", "rotatable_bonds", "qed",
  "heavy_atom_count", "contacts_per_ha_4A", "contacts_per_ha_6A",
  "pose_score_variance", "pose_score_range", "poses_passing_ratio",
] as const;

const ECIF = /^ecif_(C_ali|C_aro|N_don|N_acc|O_don|O_acc|S|other)_(C|N|O|S|F|Hal|other)$/;
const SHELL = /^shell_(C|N|O|S)_(C|N|O|S|F|P|Cl|Br)_(\d+)_(\d+)$/;

/**
 * Qué nota química admite un par ECIF.
 * - `carbono`: interviene un carbono; no puede ser un puente de hidrógeno clásico.
 * - `polar`: N/O de la proteína con N/O del ligando; compatible con un puente, sin verificarlo.
 * - `ninguna`: el resto (azufre, halógenos, otros elementos).
 */
export function notaDelPar(proteina: string, ligando: string): "carbono" | "polar" | "ninguna" {
  if (proteina.startsWith("C") || ligando === "C") return "carbono";
  const polarProteina = /^[NO]_(don|acc)$/.test(proteina);
  if (polarProteina && (ligando === "N" || ligando === "O")) return "polar";
  return "ninguna";
}

export function explainFeature(feature: string, t: Traductor): FeatureExplanation {
  const ecif = ECIF.exec(feature);
  if (ecif) {
    const [, protein, ligand] = ecif;
    const prot = t(`xai_p_${protein}`);
    const lig = t(`xai_l_${ligand}`);
    const partes = [t("xai_ecif_desc", { prot, lig })];
    const nota = notaDelPar(protein, ligand);
    if (nota === "carbono") partes.push(t("xai_ecif_note_carbon"));
    if (nota === "polar") partes.push(t("xai_ecif_note_polar"));
    if (/^[NO]_(don|acc)$/.test(protein)) partes.push(t("xai_ecif_note_typing"));
    return { label: t("xai_ecif_label", { prot, lig }), desc: partes.join(" "), kind: "ecif" };
  }
  const shell = SHELL.exec(feature);
  if (shell) {
    const [, pe, le, lo, hi] = shell;
    return {
      label: t("xai_shell_label", { pe, le, lo, hi }),
      desc: t("xai_shell_desc", { pe, le, lo, hi }),
      kind: "shell",
    };
  }
  if ((DESCRIPTOR_FEATURES as readonly string[]).includes(feature)) {
    return { label: t(`xai_f_${feature}_label`), desc: t(`xai_f_${feature}_desc`), kind: "descriptor" };
  }
  // Una característica nueva sin descripción se dice sin descripción: no se le
  // inventa una («propiedad físico-química del complejo» era falso para `logp`).
  return { label: feature.replace(/_/g, " "), desc: t("xai_f_unknown_desc"), kind: "unknown" };
}
