import type { ModuleEntry } from "./types";

type Traductor = (key: string, valores?: Readonly<Record<string, string | number>>) => string;

/**
 * El nombre de un módulo descargable en el idioma de la interfaz.
 *
 * Lo usan la tarjeta de Descargas y los avisos de la campana: si cada uno lo
 * resolviera a su manera, el mismo modelo se llamaría distinto en dos sitios.
 */
export function nombreDelModulo(id: string, manifest: readonly ModuleEntry[], t: Traductor): string {
  if (id === "esmfold-weights") return t("op_download_esmfold_name");
  return manifest.find((entry) => entry.id === id)?.name ?? id;
}

export function descripcionDelModulo(entry: ModuleEntry, t: Traductor): string {
  if (entry.id === "esmfold-weights") return t("op_download_esmfold_description");
  if (entry.id === "llm-qwen15") return t("op_download_qwen_description");
  return entry.description || (entry.features || []).join(", ");
}

export function formatearBytes(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(2)} GB`;
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(0)} MB`;
  return `${(bytes / 1_000).toFixed(0)} KB`;
}

/** Bytes de un evento de progreso: Rust manda `bytes_downloaded`; el contrato viejo, `downloaded_bytes`. */
export function bytesDescargados(event: { bytes_downloaded?: number; downloaded_bytes?: number } | undefined): number {
  return event ? event.bytes_downloaded ?? event.downloaded_bytes ?? 0 : 0;
}

/**
 * Porcentaje de una descarga, y si ya sólo falta verificarla.
 *
 * Con todos los bytes en disco Rust todavía calcula el SHA-256 —con ESMFold,
 * 8,4 GB, más de medio minuto— y la barra se quedaba llena sin decir por qué.
 */
export function avanceDeDescarga(event: { bytes_downloaded?: number; downloaded_bytes?: number; total_bytes?: number } | undefined): {
  porcentaje: number;
  descargados: number;
  total: number;
  verificando: boolean;
} {
  const descargados = bytesDescargados(event);
  const total = event?.total_bytes ?? 0;
  const porcentaje = total > 0 ? Math.min(100, Math.floor((descargados / total) * 100)) : 0;
  return { porcentaje, descargados, total, verificando: total > 0 && descargados >= total };
}
