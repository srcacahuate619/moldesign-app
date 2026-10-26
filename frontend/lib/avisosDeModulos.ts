import type { ActivityInput, ActivityStatus } from "./activityNotifications";
import type { ModelStatus } from "./types";

/**
 * Avisos de la campana para las descargas de modelos.
 *
 * Antes la campana tenía una sección fija con TODOS los modelos, instalados o
 * no, que nunca se iba (decisión del propietario, 2026-10-10: «no me parece
 * correcto»). Ahora cada descarga es un aviso más: aparece al empezar, lleva su
 * barra mientras baja y se convierte en «instalado» o en un fallo al terminar.
 * Un aviso por módulo, siempre con el mismo id: la sugerencia de bienvenida, la
 * descarga y su resultado son la misma entrada que cambia, no tres.
 */
export function idDeAvisoDeModulo(moduleId: string): string {
  return `model:${moduleId}`;
}

export type AccionDeAviso =
  | { readonly tipo: "emitir"; readonly aviso: ActivityInput }
  /** `soloSi`: se retira sólo si el aviso guardado está en ese estado. */
  | { readonly tipo: "retirar"; readonly id: string; readonly soloSi: ActivityStatus };

function enVuelo(status: ModelStatus | undefined): boolean {
  return status === "downloading" || status === "extracting";
}

function aviso(moduleId: string, status: ActivityInput["status"], clave: string): ActivityInput {
  return {
    id: idDeAvisoDeModulo(moduleId),
    source: "models",
    status,
    titleKey: `nt_modelo_${clave}`,
    messageKey: `nt_modelo_${clave}_msg`,
    moduleId,
    progress: null,
    href: "/launcher",
  };
}

/** Qué avisar al pasar de un estado de los modelos al siguiente. */
export function avisosPorTransicion(
  antes: Readonly<Record<string, ModelStatus>>,
  ahora: Readonly<Record<string, ModelStatus>>,
): AccionDeAviso[] {
  const acciones: AccionDeAviso[] = [];
  for (const [id, status] of Object.entries(ahora)) {
    const anterior = antes[id];
    if (anterior === status) continue;
    if (enVuelo(status)) {
      if (!enVuelo(anterior)) acciones.push({ tipo: "emitir", aviso: aviso(id, "in_progress", "descargando") });
    } else if (enVuelo(anterior)) {
      if (status === "ready") acciones.push({ tipo: "emitir", aviso: aviso(id, "success", "instalado") });
      else if (status === "error") acciones.push({ tipo: "emitir", aviso: aviso(id, "error", "fallo") });
      // Cancelada: lo decidió el investigador, no hay nada que avisarle.
      else acciones.push({ tipo: "retirar", id: idDeAvisoDeModulo(id), soloSi: "in_progress" });
    } else if (status === "ready") {
      // Ya está en disco (comprobado al arrancar o con «Verificar instalación»):
      // si quedaba la sugerencia de descargarlo, sobra. El «instalado» de una
      // descarga anterior se queda: es historia, no una sugerencia.
      acciones.push({ tipo: "retirar", id: idDeAvisoDeModulo(id), soloSi: "info" });
    }
  }
  return acciones;
}
