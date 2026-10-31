import type { CaseView } from "./types";

type Translate = (key: string) => string;

/** Presentación de rutas canónicas de Windows; no cambia la ruta usada para E/S. */
export function displayCasePath(path: string): string {
  if (path.startsWith("\\\\?\\UNC\\")) return `\\\\${path.slice(8)}`;
  if (path.startsWith("\\\\?\\") && /^[a-z]:\\/i.test(path.slice(4))) return path.slice(4);
  return path;
}

/** El tipo del repositorio decide la etiqueta; nunca su texto visible. */
export function localizeCaseStorageLabel(repository: { readonly id: string; readonly capabilities: { readonly storageLabel: string } }, t: Translate): string {
  if (repository.id === "tauri") return t("ca_storage_device");
  if (repository.id === "browser") return t("ca_workspace_storage_browser");
  return repository.capabilities.storageLabel;
}

export function caseViewLabel(view: CaseView, t: Translate): string {
  return t(view === "evaluation" ? "ca_view_evaluation" : "ca_view_report");
}
