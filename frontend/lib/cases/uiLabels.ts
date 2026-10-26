import type { CaseView } from "./types";

type Translate = (key: string) => string;

/** Presentación de rutas canónicas de Windows; no cambia la ruta usada para E/S. */
export function displayCasePath(path: string): string {
  if (path.startsWith("\\\\?\\UNC\\")) return `\\\\${path.slice(8)}`;
  if (path.startsWith("\\\\?\\") && /^[a-z]:\\/i.test(path.slice(4))) return path.slice(4);
  return path;
}

/** Translate repository-owned storage labels while preserving unknown labels. */
export function localizeCaseStorageLabel(label: string, t: Translate): string {
  if (label === "Carpeta en este equipo") return t("ca_storage_device");
  if (label === "Guardado en este navegador") return t("ca_workspace_storage_browser");
  return label;
}

export function caseViewLabel(view: CaseView, t: Translate): string {
  return t(view === "evaluation" ? "ca_view_evaluation" : "ca_view_report");
}
