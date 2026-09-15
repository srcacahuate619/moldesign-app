// =====================================================================
// Moldex — la bioteca: lo que el investigador decidió conservar
// =====================================================================
//
// UNA DECISIÓN DE VOCABULARIO QUE AQUÍ IMPORTA. Este producto llama «índice»
// —no «score»— a la cifra compuesta que ordena la lista, y le añade
// «histórico» porque puede venir de una corrida antigua con otro protocolo. Las
// dos palabras van juntas en los dos idiomas: «Historical composite index»
// conserva la advertencia, y «Score» a secas la pierde.
//
// «Señal GNN (legacy)» se traduce conservando `legacy`: no es un adorno, marca
// que esa señal viene de un modelo anterior y no se compara con las nuevas.

import type { ModuloDeTraduccion } from "./index";

export const moldex: ModuloDeTraduccion = {
  es: {
    // ── Estado vacío y errores ────────────────────────────────────
    mx_error_conexion: "Error de conexión",
    mx_error_carga: "No se pudo cargar Moldex",
    mx_error_motor_listo:
      "El motor local está listo, pero Moldex no pudo leer la biblioteca. Revisa el detalle y vuelve a intentarlo.",
    mx_motor_no_disponible:
      "El motor local todavía no está listo. Revisa su estado y vuelve a intentarlo.",
    mx_error_bioteca: "Error al cargar la bioteca:",
    mx_descarga_fallida: "No se pudo completar la descarga.",
    mx_sin_resultados: "No se encontraron moléculas con esos filtros.",
    mx_buscar: "Buscar molécula…",

    // ── Los tres pasos de la portada vacía ────────────────────────
    mx_paso_disena: "Diseña",
    mx_paso_disena_d: "con el Ketcher Editor",
    mx_paso_acopla: "Acopla",
    mx_paso_guarda: "Guarda",
    mx_paso_guarda_d: "salva en tu bioteca",

    // ── Orden de la lista ─────────────────────────────────────────
    mx_orden_recientes: "🕒 RECIENTES",
    mx_orden_indice_mayor: "ÍNDICE HISTÓRICO MAYOR",
    mx_orden_indice_menor: "ÍNDICE HISTÓRICO MENOR",
    mx_indice_compuesto: "ÍNDICE COMPUESTO HISTÓRICO",

    // ── Ficha de la molécula ──────────────────────────────────────
    mx_sitio_receptor: "Sitio del receptor",
    mx_molecula: "Molécula",
    mx_proteina_receptora: "Proteína receptora",
    mx_sin_nombre: "Sin nombre",
    mx_correlacion_benchmark: "Correlación del benchmark",
    mx_registro_integridad: "Registro de integridad",
    mx_reporte_cientifico: "Reporte científico",
    mx_cerrar_reporte: "Cerrar reporte científico",

    // ── Métricas ──────────────────────────────────────────────────
    mx_lipofilia: "Lipofilia",
    mx_masa: "Masa",
    mx_polaridad: "Polaridad",
    mx_hotspots: "Hotspots",
    mx_senal_gnn: "Señal GNN (legacy)",
    mx_cumple: "Cumple",
    mx_no_cumple: "No cumple",
    mx_comparador: "el comparador",
    mx_llevame_a_ella: "acabo de guardar, llévame a ella",
  },
  en: {
    mx_error_conexion: "Connection error",
    mx_error_carga: "Could not load Moldex",
    mx_error_motor_listo:
      "The local engine is ready, but Moldex could not read the library. Check the detail and try again.",
    mx_motor_no_disponible:
      "The local engine is not ready yet. Check its status and try again.",
    mx_error_bioteca: "Could not load the library:",
    mx_descarga_fallida: "The download could not be completed.",
    mx_sin_resultados: "No molecules matched those filters.",
    mx_buscar: "Search for a molecule…",

    mx_paso_disena: "Design",
    mx_paso_disena_d: "with the Ketcher Editor",
    mx_paso_acopla: "Dock",
    mx_paso_guarda: "Save",
    mx_paso_guarda_d: "keep it in your library",

    mx_orden_recientes: "🕒 MOST RECENT",
    mx_orden_indice_mayor: "HIGHEST HISTORICAL INDEX",
    mx_orden_indice_menor: "LOWEST HISTORICAL INDEX",
    mx_indice_compuesto: "HISTORICAL COMPOSITE INDEX",

    mx_sitio_receptor: "Receptor site",
    mx_molecula: "Molecule",
    mx_proteina_receptora: "Receptor protein",
    mx_sin_nombre: "Unnamed",
    mx_correlacion_benchmark: "Benchmark correlation",
    mx_registro_integridad: "Integrity record",
    mx_reporte_cientifico: "Scientific report",
    mx_cerrar_reporte: "Close scientific report",

    mx_lipofilia: "Lipophilicity",
    mx_masa: "Mass",
    mx_polaridad: "Polarity",
    mx_hotspots: "Hotspots",
    mx_senal_gnn: "GNN signal (legacy)",
    mx_cumple: "Passes",
    mx_no_cumple: "Does not pass",
    mx_comparador: "the comparator",
    mx_llevame_a_ella: "I just saved it, take me there",
  },
};
