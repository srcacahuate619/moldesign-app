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
// La tarjeta de la GNN enseña la CL-GNN, y su condición va pegada al número:
// «experimental» y «no pesa en el ranking». Pesa 0 porque sus AUC no son de los
// pesos que viajan. Sin esa condición, el número se leería como una predicción
// validada. Antes decía «Señal GNN (legacy)» y leía `gnn_score` (RTMScore), que
// la aplicación de escritorio nunca produce: la tarjeta salía siempre vacía.

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
    mx_donde_guarda: "¿Dónde se guarda esto?",
    mx_donde_guarda_detalle: "Moldex no guarda archivos sueltos de cada ficha: guarda cada evaluación como un registro en la base de datos local de MolDesign, y los archivos de la corrida (poses, informe en PDF) en la carpeta de datos de MolDesign. No se guardan en la carpeta del caso.",
    mx_abrir_carpeta_datos: "Abrir la carpeta de datos",
    mx_donde_guarda_error: "No se pudo consultar la ubicación.",
    mx_buscar: "Buscar molécula…",
    mx_cargando_2d: "Cargando estructura 2D",
    mx_comparar: "Comparar",
    mx_moleculas_cargadas: "moléculas cargadas",
    mx_molecula_cargada: "molécula cargada",
    mx_ordenar: "Ordenar",
    mx_sello_vigente: "Sello vigente",
    mx_sello_indeterminado: "Sello sin corrida",
    mx_visor_archivos_error: "No se pudieron cargar los archivos 3D de esta molécula. Sus métricas y descargas siguen disponibles.",
    mx_visor_reintentar: "Reintentar vista 3D",

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
    mx_correlacion_benchmark: "Calibración del receptor (Spearman ρ)",
    mx_calibracion_medida: "ρ = {rho} (IC 95 % [{a}; {b}], n = {n})",
    mx_calibracion_sin_medida: "Sin calibrar: no hay una ρ medida con n, intervalo y protocolo",
    mx_registro_integridad: "Registro de integridad",
    mx_reporte_cientifico: "Reporte científico",
    mx_cerrar_reporte: "Cerrar reporte científico",

    // ── Métricas ──────────────────────────────────────────────────
    mx_lipofilia: "Lipofilia",
    mx_masa: "Masa",
    mx_polaridad: "Polaridad",
    mx_hotspots: "Hotspots",
    mx_senal_clgnn: "Señal CL-GNN (experimental)",
    mx_clgnn_no_pesa: "no pesa en el ranking",
    mx_clgnn_no_disponible: "no disponible en esta corrida",
    mx_cumple: "Cumple",
    mx_no_cumple: "No cumple",
    mx_comparador: "el comparador",
    mx_llevame_a_ella: "acabo de guardar, llévame a ella",

    // ── Vistas y acciones de Moldex ───────────────────────────────
    mx_sincronizando_bioteca: "Sincronizando bioteca",
    mx_bioteca_en_espera: "Bioteca en espera",
    mx_paso_acopla_d: "con Vina; XGBoost reordena",
    mx_paso_acopla_vina_d: "con AutoDock Vina",
    mx_subtitulo_bioteca: "Bioteca",
    mx_tab_bioteca: "Ver bioteca",
    mx_filter_all: "Todos",
    mx_alcance_registro: "El registro de devnet guarda un memo con el hash del SMILES, el score redondeado, el PDB, la fecha y la wallet. No acredita la integridad del informe, del receptor ni de las poses, no identifica la revisión del documento, no demuestra que la pose sea válida ni que la conclusión científica sea correcta, y no sustituye evidencia experimental.",
    mx_tab_estructura_3d: "Ver estructura 3D",
    mx_ocultar_biblioteca: "Ocultar biblioteca",
    mx_mostrar_biblioteca: "Mostrar biblioteca",
    mx_hud_estructura_3d: "Estructura 3D",
    mx_hud_vista_estructural: "Vista estructural",
    mx_afinidad_observada: "Afinidad calculada (Vina)",
    mx_afinidad_heredada: "Afinidad heredada (origen no acreditado)",
    mx_ocultar_perfil: "Ocultar perfil",
    mx_mostrar_perfil: "Mostrar perfil",
    mx_descriptores_reglas: "Descriptores y reglas",
    mx_hits_unidad: "tocados",
    mx_hits_no_evaluado: "no evaluado",
    mx_unidad_regla: "regla",
    mx_sello_desfasado: "Sello desfasado",
    mx_verificar_solana: "Verificar en Solana",
    mx_token_local: "Sin registro en cadena · sólo local",
    mx_registrar_solana: "Registrar en Solana",
    mx_ver_reporte: "Ver reporte",
    mx_descargar_recibo_pdf: "Descargar recibo PDF",
    mx_descargar_complejo_pdb: "Descargar complejo 3D (PDB)",
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
    mx_donde_guarda: "Where is this stored?",
    mx_donde_guarda_detalle: "Moldex does not keep loose files for each card: it saves each evaluation as a record in MolDesign’s local database, and the run’s files (poses, PDF report) in MolDesign’s data folder. They are not stored in the case folder.",
    mx_abrir_carpeta_datos: "Open the data folder",
    mx_donde_guarda_error: "The location could not be retrieved.",
    mx_buscar: "Search for a molecule…",
    mx_cargando_2d: "Loading 2D structure",
    mx_comparar: "Compare",
    mx_moleculas_cargadas: "molecules loaded",
    mx_molecula_cargada: "molecule loaded",
    mx_ordenar: "Sort",
    mx_sello_vigente: "Current seal",
    mx_sello_indeterminado: "Seal without run identity",
    mx_visor_archivos_error: "The 3D files for this molecule could not be loaded. Its metrics and downloads remain available.",
    mx_visor_reintentar: "Retry 3D view",

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
    mx_correlacion_benchmark: "Receptor calibration (Spearman ρ)",
    mx_calibracion_medida: "ρ = {rho} (95% CI [{a}; {b}], n = {n})",
    mx_calibracion_sin_medida: "Not calibrated: no ρ measured with n, interval and protocol",
    mx_registro_integridad: "Integrity record",
    mx_reporte_cientifico: "Scientific report",
    mx_cerrar_reporte: "Close scientific report",

    mx_lipofilia: "Lipophilicity",
    mx_masa: "Mass",
    mx_polaridad: "Polarity",
    mx_hotspots: "Hotspots",
    mx_senal_clgnn: "CL-GNN signal (experimental)",
    mx_clgnn_no_pesa: "not used for ranking",
    mx_clgnn_no_disponible: "not available for this run",
    mx_cumple: "Passes",
    mx_no_cumple: "Does not pass",
    mx_comparador: "the comparator",
    mx_llevame_a_ella: "I just saved it, take me there",

    // ── Moldex views and actions ──────────────────────────────────
    mx_sincronizando_bioteca: "Synchronizing library",
    mx_bioteca_en_espera: "Library on standby",
    mx_paso_acopla_d: "with Vina; XGBoost re-ranks",
    mx_paso_acopla_vina_d: "with AutoDock Vina",
    mx_subtitulo_bioteca: "Library",
    mx_tab_bioteca: "View library",
    mx_filter_all: "All",
    mx_alcance_registro: "The devnet record stores a memo with the SMILES hash, the rounded score, the PDB, the date and the wallet. It does not attest to the integrity of the report, the receptor or the poses, does not identify the document's revision, does not establish that the pose is valid or the scientific conclusion is correct, and does not replace experimental evidence.",
    mx_tab_estructura_3d: "View 3D structure",
    mx_ocultar_biblioteca: "Hide library",
    mx_mostrar_biblioteca: "Show library",
    mx_hud_estructura_3d: "3D Structure",
    mx_hud_vista_estructural: "Structural view",
    mx_afinidad_observada: "Calculated affinity (Vina)",
    mx_afinidad_heredada: "Inherited affinity (origin not attested)",
    mx_ocultar_perfil: "Hide profile",
    mx_mostrar_perfil: "Show profile",
    mx_descriptores_reglas: "Descriptors and rules",
    mx_hits_unidad: "contacted",
    mx_hits_no_evaluado: "not evaluated",
    mx_unidad_regla: "rule",
    mx_sello_desfasado: "Outdated seal",
    mx_verificar_solana: "Verify on Solana",
    mx_token_local: "Not recorded on-chain · local only",
    mx_registrar_solana: "Record on Solana",
    mx_ver_reporte: "View report",
    mx_descargar_recibo_pdf: "Download receipt PDF",
    mx_descargar_complejo_pdb: "Download 3D complex (PDB)",
  },
};
