// =====================================================================
// Clasificación dual de receptores: Familia Química ↔ Familia Terapéutica
// =====================================================================
//
// El modal "Elige Receptor" agrupa la MISMA lista completa de targets por
// dos ejes intercambiables (NUNCA filtra):
//   - quimica     → structural_family  ("gpcr", "kinase", "protease", ...)
//   - terapeutica → therapeutic_family ("cardiovascular", "oncologia", ...)
//
// Reglas de agrupación:
//   - key del grupo = display name (THERAPEUTIC_DISPLAY_NAMES, slug → nombre
//     humano; fallback al valor crudo si el slug no está en el mapa).
//   - targets sin familia (null / missing / vacío) → "Otra / No Clasificada".
//   - orden: familias con COUNT DESC (la más poblada primero) y "Otra" SIEMPRE
//     al final, sin importar cuántos ítems tenga.
//
// La preferencia del usuario se persiste en localStorage bajo
// "moldesign_receptor_mode" (default "quimica"). Los helpers son SSR-safe
// (try/catch + typeof window) porque Next.js hidrata del lado del servidor.
//
import { getUserItem, setUserItem } from "./userStorage";
// Funciones puras y sin side effects: testeables de forma aislada.

import type { Target } from "./api";

/** Bucket de último recurso para targets sin familia en el eje activo. */
export const UNCLASSIFIED_FAMILY = "Otra / No Clasificada";

/**
 * Mapa de presentación: slug canónico lowercase → nombre legible en el header
 * del grupo. Cubre familias químicas (D4) y terapéuticas (D3/D10). Si un
 * valor no está en el mapa, se muestra el valor crudo.
 */
export const THERAPEUTIC_DISPLAY_NAMES: Record<string, string> = {
  // ── Familias terapéuticas (área médica) ──
  cardiovascular: "Cardiovascular",
  endocrinologia: "Endocrinología",
  metabolismo: "Metabolismo",
  "inmuno-oncologia": "Inmuno-Oncología",
  neurodegeneracion: "Neurodegeneración",
  antivirales: "Antivirales",
  antibacterianos: "Antibacterianos",
  fibrosis: "Fibrosis",
  epigenetica: "Epigenética",
  "ubiquitina-proteasoma": "Ubiquitina-Proteasoma",
  senescencia___aging: "Senescencia & Aging",
  inflamacion___dolor: "Inflamación & Dolor",
  enfermedades_raras: "Enfermedades Raras",
  oncologia: "Oncología",
  psiquiatria: "Psiquiatría",
  coagulacion___hemostasia: "Coagulación & Hemostasia",
  antiparasitarios: "Antiparasitarios",

  // ── Familias químicas (clase molecular) ──
  gpcr: "GPCR",
  kinase: "Kinasa",
  protease: "Proteasa",
  ion_channel: "Canal Iónico",
  nuclear_receptor: "Receptor Nuclear",
  phosphodiesterase: "Fosfodiesterasa",
  transporter: "Transportador",
  cytochrome_p450: "Citocromo P450",
  oxidoreductase: "Oxidorreductasa",
  hydrolase: "Hidrolasa",
  methyltransferase: "Metiltransferasa",
  topoisomerase: "Topoisomerasa",
  polymerase: "Polimerasa",
  nuclease: "Nucleasa",
  proteasome: "Proteasoma",
  lipid_binding_protein: "Proteína de Unión a Lípidos",
  growth_factor: "Factor de Crecimiento",
  protein_interaction: "Interacción Proteína-Proteína",
  protein_protein_interaction: "Interacción Proteína-Proteína",
  chaperone: "Chaperona",
  gtpase: "GTPasa",
  metalloenzyme: "Metaloenzima",
  bromodomain: "Bromodominio",
  atp_synthase: "ATP Sintasa",
  ligase: "Ligasa",
  lyase: "Liasa",
  isomerase: "Isomerasa",
};

/** Eje de agrupación activo: familia química o familia terapéutica. */
export type ClassificationMode = "quimica" | "terapeutica";

const STORAGE_KEY = "moldesign_receptor_mode";

/**
 * Agrupa targets por el eje activo. Puro: no filtra, no muta, no toca
 * localStorage. Retorna pares [displayName, targets] ordenados por COUNT DESC
 * con "Otra / No Clasificada" siempre al final.
 */
export function groupTargets(targets: Target[], mode: ClassificationMode): [string, Target[]][] {
  const groups = new Map<string, Target[]>();

  for (const target of targets) {
    const raw = mode === "quimica" ? target.structural_family : target.therapeutic_family;
    const key =
      raw && raw.trim().length > 0 ? (THERAPEUTIC_DISPLAY_NAMES[raw] ?? raw) : UNCLASSIFIED_FAMILY;
    const bucket = groups.get(key);
    if (bucket) bucket.push(target);
    else groups.set(key, [target]);
  }

  const entries = Array.from(groups.entries());
  const classified = entries.filter(([key]) => key !== UNCLASSIFIED_FAMILY);
  const unclassified = entries.filter(([key]) => key === UNCLASSIFIED_FAMILY);
  classified.sort((a, b) => b[1].length - a[1].length);

  return [...classified, ...unclassified];
}

/** Lee el modo persistido. Default "quimica"; valores basura → "quimica". SSR-safe. */
export function readClassificationMode(): ClassificationMode {
  try {
    if (typeof window === "undefined") return "quimica";
    return getUserItem(STORAGE_KEY) === "terapeutica" ? "terapeutica" : "quimica";
  } catch {
    return "quimica";
  }
}

/** Persiste el modo elegido. SSR-safe (no-op fuera del navegador). */
export function writeClassificationMode(mode: ClassificationMode): void {
  try {
    if (typeof window === "undefined") return;
    setUserItem(STORAGE_KEY, mode);
  } catch {}
}
