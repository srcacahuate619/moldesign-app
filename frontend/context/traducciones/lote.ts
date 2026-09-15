// =====================================================================
// Batch — cohortes: definir, comprobar, ejecutar y entregar evidencia
// =====================================================================
//
// La pantalla con más texto de la aplicación, y la que peor tolera una
// traducción floja: aquí se declara lo que una corrida NO midió, y un matiz
// perdido al cruzar de idioma convierte una limitación declarada en una
// promesa. «No se declararon controles; no podrá compararse el resultado con
// una referencia» tiene que seguir siendo una advertencia en inglés, no una
// nota informativa.
//
// SOBRE `lo_msg_*`. Son los códigos que devuelve la comprobación previa del
// backend. La clave conserva el código tal cual —`ARCHIVO_ILEGIBLE`— para que
// se pueda cruzar de un vistazo con `services/cohort/`: el día que el backend
// añada uno, la clave que falta se ve sin traducir el fichero entero.

import type { ModuloDeTraduccion } from "./index";

export const lote: ModuloDeTraduccion = {
  es: {
    // ── Los seis pasos ────────────────────────────────────────────
    lo_paso_definir: "Definir",
    lo_paso_comprobar: "Comprobar",
    lo_paso_guardar: "Guardar",
    lo_paso_ejecutar: "Ejecutar",
    lo_paso_evidencia: "Evidencia",
    lo_paso_informe: "Informe",

    // ── Filtros de la tabla ───────────────────────────────────────
    lo_filtro_todas: "Todas",
    lo_filtro_completadas: "Completadas",
    lo_filtro_duplicados: "Duplicados",
    lo_filtro_fallidas: "Fallidas",
    lo_filtro_no_evaluadas: "No evaluadas",

    // ── Comprobación previa: bloqueos y avisos ────────────────────
    lo_msg_ARCHIVO_ILEGIBLE: "No se pudo leer el archivo. Verifica que no esté dañado.",
    lo_msg_FORMATO_NO_SOPORTADO: "El formato del archivo no es compatible.",
    lo_msg_COLUMNA_SMILES_AUSENTE:
      "El archivo no contiene una columna de estructuras SMILES.",
    lo_msg_COHORTE_VACIA: "El archivo no contiene moléculas.",
    lo_msg_SIN_MOLECULAS_ELEGIBLES: "Ninguna molécula puede entrar en esta corrida.",
    lo_msg_LECTOR_NO_DISPONIBLE:
      "Esta instalación no incluye el lector necesario para ese formato.",
    lo_msg_VALIDADOR_NO_DISPONIBLE:
      "El validador químico no está disponible en esta instalación.",
    lo_msg_SIN_CONTROLES_DECLARADOS:
      "No se declararon controles; no podrá compararse el resultado con una referencia.",
    lo_msg_SIN_ETIQUETAS_ACTIVE:
      "No hay etiquetas de actividad; no se calcularán métricas supervisadas.",
    lo_msg_DUPLICADOS_CANONICOS:
      "Hay estructuras repetidas; se ejecutarán una vez y se declarará su reutilización.",
    lo_msg_FILAS_INVALIDAS:
      "Algunas filas no entrarán en la corrida. Revisa la cobertura antes de continuar.",
    lo_msg_CAJA_NO_DECLARADA:
      "La caja de búsqueda se tomará de la configuración validada del receptor.",
    lo_msg_SEMILLA_NO_DECLARADA:
      "No se indicó semilla; se congelará la semilla predeterminada de esta instalación.",
    lo_msg_desconocido: "La comprobación detectó una condición que requiere revisión.",
    lo_operacion_fallida: "La operación no se pudo completar.",
    lo_catalogo_no_cargado: "No se pudo cargar el catálogo: {detalle}",
    lo_seguimiento_interrumpido:
      "Se interrumpió el seguimiento de la cohorte. La corrida conserva su estado "
      + "en el backend; puedes reintentar.",
    lo_evaluacion_no_completada: "La evaluación no pudo completarse.",

    // ── 1 · Definir ───────────────────────────────────────────────
    lo_nombre_cohorte: "Nombre de la cohorte",
    lo_nombre_ejemplo: "Serie de anilinas · lote 3",
    lo_prepara_archivo: "Prepara el archivo",
    lo_limite_moleculas:
      "Incluye como máximo 500 moléculas en un archivo de hasta 8 MiB.",
    lo_csv_recomendaciones:
      "Para CSV, usa UTF-8, una primera fila de encabezado, comas como separador "
      + "y la columna recomendada",
    lo_tambien_se_aceptan: "; también se aceptan",
    lo_mismo_receptor:
      "Todas las moléculas usarán un único receptor y la misma configuración congelada.",
    lo_ejemplo_csv: "Ejemplo CSV mínimo",
    lo_ver_formatos: "Ver todos los formatos y campos",
    lo_formatos_csv_xlsx:
      "requieren una columna de estructura. Se recomienda",
    lo_formatos_opcionales: ". Las columnas opcionales son",
    lo_formatos_xlsx_hoja:
      ". XLSX usa la hoja activa y su primera fila como encabezado.",
    lo_formatos_smi:
      "una molécula por línea con el formato",
    lo_formatos_smi_separador:
      ", separado por espacios. Las líneas que comienzan con",
    lo_formatos_smi_comentarios:
      "son comentarios y el nombre no puede contener espacios.",
    lo_formatos_sdf:
      "se admite una molécula por registro. El nombre se lee de",
    lo_formatos_sdf_propiedades: "; las propiedades",
    lo_formatos_sdf_opcionales: "son opcionales.",
    lo_formatos_para: "Para",
    lo_formatos_usa: "usa",
    lo_o: "o",
    lo_formatos_activa: "para activa y",
    lo_formatos_inactiva: "para inactiva. Para",
    lo_archivo_moleculas: "Archivo de moléculas",

    // ── Receptor y motor ──────────────────────────────────────────
    lo_reintentar_catalogo: "Reintentar catálogo de receptores",
    lo_abrir_catalogo: "Abrir catálogo de receptores",
    lo_catalogo_con_cuenta: "Catálogo ({n})",
    lo_motor_disponible: "Motor disponible para cohortes nuevas.",
    lo_qvina_proximamente: "QuickVina 2 · Próximamente",
    lo_qvina_no_disponible:
      "QuickVina 2 no está disponible en esta versión; la evidencia histórica "
      + "sigue siendo legible.",
    lo_qvina_requiere_binario:
      "Requiere un binario Windows validado. Esta versión ejecuta únicamente Vina.",

    // ── 2 · Comprobación previa ───────────────────────────────────
    lo_titulo_comprobacion: "2 · Comprobación previa",
    lo_filas: "Filas",
    lo_elegibles: "Elegibles",
    lo_invalidas: "Inválidas",
    lo_moleculas_unicas: "Moléculas únicas",
    lo_cobertura_no_medible: "no medible (sin filas)",
    lo_cobertura: "{porcentaje} % · {elegibles} de {total}",

    // ── 4 · Ejecución ─────────────────────────────────────────────
    lo_titulo_ejecucion: "4 · Ejecución",
    lo_paralelismo: "Paralelismo",
    lo_ejecutar_cohorte: "Ejecutar cohorte",
    lo_preparando: "Preparando y abriendo…",
    lo_cancelacion_pedida: "· cancelación pedida",

    // ── 5 · Evidencia ─────────────────────────────────────────────
    lo_filas_del_archivo: "Filas del archivo",
    lo_no_evaluadas: "No evaluadas",
    lo_no_elegibles: "No elegibles",
    lo_metricas_etiquetadas: "Métricas etiquetadas",
    lo_controles_declarados:
      "Controles declarados (fuera de la población de la métrica)",
    lo_sin_afinidad: "sin afinidad",
    lo_limites_interpretacion: "Límites de interpretación",
    lo_filtrar_por_estado: "Filtrar por estado",
    lo_no_disponible: "NO DISPONIBLE",

    // ── 6 · Informe ───────────────────────────────────────────────
    lo_dossier_cohorte: "Dossier de cohorte",
    lo_ninguna_todavia: "Ninguna todavía.",
  },
  en: {
    lo_paso_definir: "Define",
    lo_paso_comprobar: "Check",
    lo_paso_guardar: "Save",
    lo_paso_ejecutar: "Run",
    lo_paso_evidencia: "Evidence",
    lo_paso_informe: "Report",

    lo_filtro_todas: "All",
    lo_filtro_completadas: "Completed",
    lo_filtro_duplicados: "Duplicates",
    lo_filtro_fallidas: "Failed",
    lo_filtro_no_evaluadas: "Not evaluated",

    lo_msg_ARCHIVO_ILEGIBLE: "The file could not be read. Check that it is not damaged.",
    lo_msg_FORMATO_NO_SOPORTADO: "The file format is not supported.",
    lo_msg_COLUMNA_SMILES_AUSENTE: "The file has no SMILES structure column.",
    lo_msg_COHORTE_VACIA: "The file contains no molecules.",
    lo_msg_SIN_MOLECULAS_ELEGIBLES: "No molecule can enter this run.",
    lo_msg_LECTOR_NO_DISPONIBLE:
      "This installation does not include the reader needed for that format.",
    lo_msg_VALIDADOR_NO_DISPONIBLE:
      "The chemical validator is not available in this installation.",
    lo_msg_SIN_CONTROLES_DECLARADOS:
      "No controls were declared; the result will not be comparable against a reference.",
    lo_msg_SIN_ETIQUETAS_ACTIVE:
      "There are no activity labels; supervised metrics will not be calculated.",
    lo_msg_DUPLICADOS_CANONICOS:
      "There are repeated structures; they will run once and their reuse will be declared.",
    lo_msg_FILAS_INVALIDAS:
      "Some rows will not enter the run. Check the coverage before continuing.",
    lo_msg_CAJA_NO_DECLARADA:
      "The search box will be taken from the validated configuration of the receptor.",
    lo_msg_SEMILLA_NO_DECLARADA:
      "No seed was given; the default seed of this installation will be frozen.",
    lo_msg_desconocido: "The check found a condition that needs review.",
    lo_operacion_fallida: "The operation could not be completed.",
    lo_catalogo_no_cargado: "The catalogue could not be loaded: {detalle}",
    lo_seguimiento_interrumpido:
      "Tracking of the cohort was interrupted. The run keeps its state in the "
      + "backend; you can retry.",
    lo_evaluacion_no_completada: "The evaluation could not be completed.",

    lo_nombre_cohorte: "Cohort name",
    lo_nombre_ejemplo: "Aniline series · batch 3",
    lo_prepara_archivo: "Prepare the file",
    lo_limite_moleculas:
      "Include at most 500 molecules in a file of up to 8 MiB.",
    lo_csv_recomendaciones:
      "For CSV, use UTF-8, a header row first, commas as the separator and the "
      + "recommended column",
    lo_tambien_se_aceptan: "; these are also accepted:",
    lo_mismo_receptor:
      "Every molecule will use a single receptor and the same frozen configuration.",
    lo_ejemplo_csv: "Minimal CSV example",
    lo_ver_formatos: "See every format and field",
    lo_formatos_csv_xlsx: "require a structure column. We recommend",
    lo_formatos_opcionales: ". The optional columns are",
    lo_formatos_xlsx_hoja: ". XLSX uses the active sheet and its first row as the header.",
    lo_formatos_smi: "one molecule per line in the format",
    lo_formatos_smi_separador: ", separated by spaces. Lines starting with",
    lo_formatos_smi_comentarios:
      "are comments, and the name cannot contain spaces.",
    lo_formatos_sdf: "one molecule per record is accepted. The name is read from",
    lo_formatos_sdf_propiedades: "; the properties",
    lo_formatos_sdf_opcionales: "are optional.",
    lo_formatos_para: "For",
    lo_formatos_usa: "use",
    lo_o: "or",
    lo_formatos_activa: "for active and",
    lo_formatos_inactiva: "for inactive. For",
    lo_archivo_moleculas: "Molecule file",

    lo_reintentar_catalogo: "Retry the receptor catalogue",
    lo_abrir_catalogo: "Open the receptor catalogue",
    lo_catalogo_con_cuenta: "Catalogue ({n})",
    lo_motor_disponible: "Engine available for new cohorts.",
    lo_qvina_proximamente: "QuickVina 2 · Coming soon",
    lo_qvina_no_disponible:
      "QuickVina 2 is not available in this version; the historical evidence "
      + "remains readable.",
    lo_qvina_requiere_binario:
      "It needs a validated Windows binary. This version runs Vina only.",

    lo_titulo_comprobacion: "2 · Pre-flight check",
    lo_filas: "Rows",
    lo_elegibles: "Eligible",
    lo_invalidas: "Invalid",
    lo_moleculas_unicas: "Unique molecules",
    lo_cobertura_no_medible: "not measurable (no rows)",
    lo_cobertura: "{porcentaje} % · {elegibles} of {total}",

    lo_titulo_ejecucion: "4 · Run",
    lo_paralelismo: "Parallelism",
    lo_ejecutar_cohorte: "Run cohort",
    lo_preparando: "Preparing and opening…",
    lo_cancelacion_pedida: "· cancellation requested",

    lo_filas_del_archivo: "Rows in the file",
    lo_no_evaluadas: "Not evaluated",
    lo_no_elegibles: "Not eligible",
    lo_metricas_etiquetadas: "Labelled metrics",
    lo_controles_declarados:
      "Declared controls (outside the metric population)",
    lo_sin_afinidad: "no affinity",
    lo_limites_interpretacion: "Limits of interpretation",
    lo_filtrar_por_estado: "Filter by status",
    lo_no_disponible: "NOT AVAILABLE",

    lo_dossier_cohorte: "Cohort dossier",
    lo_ninguna_todavia: "None yet.",
  },
};
