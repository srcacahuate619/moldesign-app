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
    lo_frontend_213: "La operación no se pudo completar (HTTP {v0}).",
    lo_frontend_214: "Error de conexión: no se pudo contactar con el motor local de MolDesign. Revisa su estado y vuelve a intentarlo.",
    lo_frontend_215: "Error de conexión: no se pudo contactar con el motor local de MolDesign.",
    lo_frontend_003: "dossier_cohorte.pdf",
    lo_frontend_004: "cohorte_{v0}.zip",
    lo_view_run_result: "Ver resultado de esta corrida",
    lo_result_no_task: "Esta fila no conserva la referencia a una corrida exacta; no se abrirá otro resultado.",
    lo_result_limit: "El docking completado no demuestra actividad ni validez física de la pose.",
    lo_seed_default: "Usar la semilla por defecto (42)",
    lo_seed_help: "Semilla por defecto: 42. Puedes elegir un entero entre 1 y 2147483647. Se congela antes de ejecutar y se declara por fila.",
    lo_tautomero_help: "Es el mismo para todas las filas y entra en la huella de la cohorte. Por defecto se acopla el tautómero escrito en el archivo. El canónico de RDKit lo sustituye por una forma normalizada, que no predice el tautómero dominante y a veces elige una minoritaria (hidroxamatos, lactamas).",
    // Nombre literal del campo del CSV/SDF; no se localiza porque forma parte
    // del formato que el usuario debe entregar al importador.
    lo_campo_active: "active",

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
      "La caja de búsqueda se tomará de la que guarda el receptor.",
    lo_msg_SEMILLA_NO_DECLARADA:
      "No se indicó semilla; se congelará la semilla por defecto: 42.",
    lo_msg_desconocido: "La comprobación detectó una condición que requiere revisión.",
    lo_msg_SMILES_AUSENTE: "La fila no trae SMILES.",
    lo_msg_SMILES_ILEGIBLE: "El SMILES no se puede leer.",
    lo_msg_SMILES_NO_ADMISIBLE:
      "El SMILES se lee, pero este producto no lo evalúa: tiene menos de 5 átomos pesados o una estructura química inválida.",
    lo_msg_REGISTRO_ILEGIBLE: "El registro de la fila no se puede leer.",
    lo_msg_ROL_CONTROL_INVALIDO: "El rol de control no es válido (usa reference, positive, negative o none).",
    lo_filas_rechazadas_titulo: "Filas que no entrarán en la corrida ({n})",
    lo_filas_rechazadas_ayuda: "Corrige estas filas en el archivo y vuelve a comprobar, o continúa sin ellas.",
    lo_fila_numero: "Fila {n}",
    lo_y_n_mas: "…y {n} más.",
    lo_cobertura_n_de_m: "{n} de {m}",
    lo_estado_en_cola: "En cola",
    lo_estado_ejecutando: "Ejecutando",
    lo_estado_completada: "Completada",
    lo_estado_completada_con_excepciones: "Completada con excepciones",
    lo_estado_sin_resultados: "Sin resultados utilizables",
    lo_estado_interrumpida: "Interrumpida",
    lo_estado_cancelada: "Cancelada",
    lo_estado_pendiente: "Pendiente",
    lo_estado_fallida: "Fallida",
    lo_estado_no_evaluada: "No evaluada",
    lo_estado_duplicado_reutilizado: "Duplicado reutilizado",
    lo_control_referencia: "Referencia",
    lo_control_positivo: "Positivo",
    lo_control_negativo: "Negativo",
    lo_etiqueta_activa: "activa",
    lo_etiqueta_inactiva: "inactiva",
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
    lo_elegir_archivo: "Elegir archivo",
    lo_sin_archivo: "No se eligió ningún archivo",

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
    lo_run_id_label: "Corrida {id}",
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

    // ── Elementos y acciones de la pantalla de cohortes ──────────
    lo_titulo_cohortes: "Cohortes",
    lo_aria_pasos: "Pasos",
    lo_ejemplo_smi_columnas: "SMILES nombre active control_role",
    lo_receptor_pdb_id: "Receptor (PDB ID)",
    lo_receptor_pdb_aria: "Receptor PDB ID",
    lo_cadena_opcional: "Cadena (opcional)",
    lo_exhaust_label: "Exhaust.",
    lo_poses_label: "Poses",
    lo_comprobar_cohorte: "Comprobar cohorte",
    lo_rol_referencia: "Referencia",
    lo_rol_positivos: "Positivos",
    lo_rol_negativos: "Negativos",
    lo_cohorte_prefijo: "cohorte",
    lo_progreso_archivo: "Archivo",
    lo_reanudar: "Reanudar",
    lo_th_afinidad_vina: "Afinidad Vina observada (kcal/mol)",
    lo_th_etiqueta: "Etiqueta",
    lo_th_control: "Control",
    lo_cohortes_guardadas: "Cohortes guardadas",
    lo_refrescar_lista: "Refrescar lista",
    lo_elegibles_sufijo: "elegibles",
  },
  en: {
    lo_frontend_213: "The operation could not be completed (HTTP {v0}).",
    lo_frontend_214: "Connection error: the local MolDesign engine could not be contacted. Check its status and try again.",
    lo_frontend_215: "Connection error: the local MolDesign engine could not be contacted.",
    lo_frontend_003: "cohort_dossier.pdf",
    lo_frontend_004: "cohort_{v0}.zip",
    lo_view_run_result: "View this run’s result",
    lo_result_no_task: "This row has no reference to an exact run; another result will not be opened.",
    lo_result_limit: "Completed docking does not demonstrate activity or physical pose validity.",
    lo_seed_default: "Use the default seed (42)",
    lo_seed_help: "Default seed: 42. You can choose an integer from 1 to 2147483647. It is frozen before execution and declared per row.",
    lo_tautomero_help: "It is the same for every row and is part of the cohort fingerprint. By default, the tautomer written in the file is docked. The RDKit canonical option replaces it with a normalized form that does not predict the dominant tautomer and sometimes picks a minor one (hydroxamates, lactams).",
    lo_campo_active: "active",

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
      "The search box will be taken from the one stored with the receptor.",
    lo_msg_SEMILLA_NO_DECLARADA:
      "No seed was given; the default seed, 42, will be frozen.",
    lo_msg_desconocido: "The check found a condition that needs review.",
    lo_msg_SMILES_AUSENTE: "The row has no SMILES.",
    lo_msg_SMILES_ILEGIBLE: "The SMILES cannot be read.",
    lo_msg_SMILES_NO_ADMISIBLE:
      "The SMILES reads, but this product does not evaluate it: it has fewer than 5 heavy atoms or an invalid chemical structure.",
    lo_msg_REGISTRO_ILEGIBLE: "The row record cannot be read.",
    lo_msg_ROL_CONTROL_INVALIDO: "The control role is not valid (use reference, positive, negative or none).",
    lo_filas_rechazadas_titulo: "Rows that will not enter the run ({n})",
    lo_filas_rechazadas_ayuda: "Fix these rows in the file and check again, or continue without them.",
    lo_fila_numero: "Row {n}",
    lo_y_n_mas: "…and {n} more.",
    lo_cobertura_n_de_m: "{n} of {m}",
    lo_estado_en_cola: "Queued",
    lo_estado_ejecutando: "Running",
    lo_estado_completada: "Completed",
    lo_estado_completada_con_excepciones: "Completed with exceptions",
    lo_estado_sin_resultados: "No usable results",
    lo_estado_interrumpida: "Interrupted",
    lo_estado_cancelada: "Canceled",
    lo_estado_pendiente: "Pending",
    lo_estado_fallida: "Failed",
    lo_estado_no_evaluada: "Not evaluated",
    lo_estado_duplicado_reutilizado: "Reused duplicate",
    lo_control_referencia: "Reference",
    lo_control_positivo: "Positive",
    lo_control_negativo: "Negative",
    lo_etiqueta_activa: "active",
    lo_etiqueta_inactiva: "inactive",
    lo_operacion_fallida: "The operation could not be completed.",
    lo_catalogo_no_cargado: "The catalog could not be loaded: {detalle}",
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
    lo_elegir_archivo: "Choose file",
    lo_sin_archivo: "No file selected",

    lo_reintentar_catalogo: "Retry the receptor catalog",
    lo_abrir_catalogo: "Open the receptor catalog",
    lo_catalogo_con_cuenta: "Catalog ({n})",
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
    lo_run_id_label: "Run {id}",
    lo_paralelismo: "Parallelism",
    lo_ejecutar_cohorte: "Run cohort",
    lo_preparando: "Preparing and opening…",
    lo_cancelacion_pedida: "· cancellation requested",

    lo_filas_del_archivo: "Rows in the file",
    lo_no_evaluadas: "Not evaluated",
    lo_no_elegibles: "Not eligible",
    lo_metricas_etiquetadas: "Labeled metrics",
    lo_controles_declarados:
      "Declared controls (outside the metric population)",
    lo_sin_afinidad: "no affinity",
    lo_limites_interpretacion: "Limits of interpretation",
    lo_filtrar_por_estado: "Filter by status",
    lo_no_disponible: "NOT AVAILABLE",

    lo_dossier_cohorte: "Cohort dossier",
    lo_ninguna_todavia: "None yet.",

    // ── Cohort screen elements and actions ────────────────────────
    lo_titulo_cohortes: "Cohorts",
    lo_aria_pasos: "Steps",
    lo_ejemplo_smi_columnas: "SMILES name active control_role",
    lo_receptor_pdb_id: "Receptor (PDB ID)",
    lo_receptor_pdb_aria: "Receptor PDB ID",
    lo_cadena_opcional: "Chain (optional)",
    lo_exhaust_label: "Exhaust.",
    lo_poses_label: "Poses",
    lo_comprobar_cohorte: "Check cohort",
    lo_rol_referencia: "Reference",
    lo_rol_positivos: "Positives",
    lo_rol_negativos: "Negatives",
    lo_cohorte_prefijo: "cohort",
    lo_progreso_archivo: "File",
    lo_reanudar: "Resume",
    lo_th_afinidad_vina: "Observed Vina affinity (kcal/mol)",
    lo_th_etiqueta: "Label",
    lo_th_control: "Control",
    lo_cohortes_guardadas: "Saved cohorts",
    lo_refrescar_lista: "Refresh list",
    lo_elegibles_sufijo: "eligible",
  },
};
