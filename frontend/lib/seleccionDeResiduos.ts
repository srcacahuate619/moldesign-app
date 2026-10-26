// =====================================================================
// seleccionDeResiduos — los residuos de referencia de una corrida son TRES estados
// =====================================================================
//
// QA1-007. El backend ya distingue (SOL-08, `test_seleccion_vacia_de_hotspots.py`):
//
//     null / ausente   nunca se decidió: la corrida hereda los residuos del catálogo
//     []               decisión: «no quiero residuos de referencia»
//     ["A:ASP32", …]   decisión: sólo estos
//
// La interfaz los colapsaba en dos sitios, con efectos medidos en la cápsula de QA:
//
//   · Elegir un receptor fijaba `[]` (ver `CaseEvaluationRunner.setTarget`): toda
//     corrida «por defecto» iba SIN residuos de referencia, mientras «Opciones»
//     decía «15/15 activos» y el preflight decía «decisión del investigador».
//   · `ProEvaluation` convertía `[]` en `null` al aplicar y al reabrir «Opciones»:
//     quien desmarcaba los 15 los veía otra vez activos al volver a abrir el panel,
//     aunque el caso guardara «ninguno».
//
// Estas dos funciones son la única conversión entre lo guardado en el caso y el
// estado del panel, y no cruzan nunca `[]` con `null`.

/** `null` = sin decidir (catálogo). Un array —también el vacío— es una decisión. */
export type SeleccionDeResiduos = string[] | null;

/** Estado inicial del panel a partir de lo guardado en el caso. `[]` se CONSERVA. */
export function seleccionInicial(guardada: readonly string[] | null | undefined): SeleccionDeResiduos {
  return guardada ? [...guardada] : null;
}

/** Lo que aplicó el modal: la lista tal cual (incluida la vacía) o `null` si no trajo ninguna. */
export function seleccionAplicada(aplicada: readonly string[] | null | undefined): SeleccionDeResiduos {
  return aplicada ? [...aplicada] : null;
}

/** Lo que se guarda en el caso: ausente cuando no hay decisión, no un `[]` que sí lo sería. */
export function seleccionParaGuardar(seleccion: SeleccionDeResiduos): string[] | undefined {
  return seleccion ? [...seleccion] : undefined;
}
