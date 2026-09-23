// =====================================================================
// Páginas — Historial, Comunidad, el error global y los restos de Batch
// =====================================================================
//
// TRES FRASES DE AQUÍ SON LA TESIS DEL PRODUCTO Y NO ADMITEN PARÁFRASIS:
//
//   · «Esta pantalla no ordena moléculas por mérito farmacológico ni produce
//     ninguna puntuación agregada. La afinidad Vina observada es una señal de
//     ranking dentro de este protocolo, no una medida de energía libre ni una
//     predicción de actividad.»
//   · «Superarla no predice unión ni calidad farmacológica: todavía no se ha
//     calculado nada.»
//   · «El orden refleja los datos compartidos por el servicio; no es un ranking
//     de candidatos ni una predicción de actividad.»
//
// Se traducen con «it is not» y «does not predict». Nunca «should not be
// interpreted as» — eso convierte un hecho en una recomendación.
//
// Y el error global se traduce con cuidado aparte: es lo único que el usuario
// lee cuando la ventana no se pinta, y su trabajo es decirle que sus datos están
// intactos. Un inglés vago ahí asusta a quien ya está asustado.

import type { ModuloDeTraduccion } from "./index";

export const paginas: ModuloDeTraduccion = {
  es: {
    // ── Batch: lo que quedaba ─────────────────────────────────────
    pg_lote_intro:
      "Define una cohorte comparable, comprueba sus entradas, ejecútala bajo una "
      + "configuración común y entrega evidencia con su cobertura.",
    pg_lote_receptor_comun:
      "Un receptor y una configuración común para todas las moléculas. Es lo que "
      + "hace comparables las filas entre sí.",
    pg_lote_comprobar_no_ejecuta: "Comprobar no ejecuta nada.",
    pg_lote_superarla_no_predice:
      "Superarla no predice unión ni calidad farmacológica: todavía no se ha "
      + "calculado nada.",
    pg_lote_bloqueada: "Bloqueada — no se puede guardar ni ejecutar",
    pg_lote_avisos: "Avisos — no bloquean",
    pg_lote_orden_no_veredicto:
      "Ordenada por afinidad Vina observada. Es un orden, no un veredicto: "
      + "completar un acoplamiento no demuestra actividad.",
    pg_lote_sin_estado: "No hay moléculas con este estado.",
    pg_lote_paquete_descargado: "Paquete descargado como",
    pg_lote_manifiesto:
      ". Incluye su manifiesto con hashes; la verificación la hace quien lo "
      + "reciba.",
    pg_lote_dossier_no_cargado: "El dossier no está cargado.",
    pg_lote_inmutable:
      "Una cohorte guardada es inmutable: cambiar receptor, configuración o "
      + "archivo produce otra cohorte, no una edición.",
    pg_lote_sin_merito:
      "Esta pantalla no ordena moléculas por mérito farmacológico ni produce "
      + "ninguna puntuación agregada. La afinidad Vina observada es una señal de "
      + "ranking dentro de este protocolo, no una medida de energía libre ni una "
      + "predicción de actividad.",

    // ── Historial ─────────────────────────────────────────────────
    pg_hist_titulo: "Historial de evaluaciones",
    pg_hist_privado:
      "El historial guarda huellas que solo tus ojos deben ver: evaluaciones, "
      + "resultados y recibos de integridad. Identifícate para continuar.",
    pg_hist_descripcion:
      "Todas las evaluaciones de tu cuenta, tal como están en la base de datos. "
      + "Las que además aparecen en Moldex llevan la marca",
    pg_hist_ordenar: "Ordenar por:",
    pg_hist_vacio:
      "Todavía no has guardado ninguna evaluación molecular. Una evaluación "
      + "guardada conserva el docking, sus resultados, los hotspots observados y, "
      + "cuando existe, su recibo de integridad.",
    pg_hist_sin_recibo: "Sin recibo",
    pg_hist_verificando: "Verificando sesión",
    pg_hist_targets_unicos: "Targets únicos",
    pg_hist_copiar_id: "Copiar identificador de corrida: {taskId}",
    pg_hist_copiar_id_corto: "Copiar identificador de corrida {taskId}",
    pg_hist_anterior_task_id: "Corrida anterior al registro por task_id",
    pg_hist_descargar_recibo: "Descargar recibo de integridad PDF",
    pg_hist_acceso_bloqueado: "Acceso Bloqueado",
    pg_hist_subline_jwt: "autocomplete · validando token jwt · v 2.0",
    pg_hist_footer_autenticado: "historial molecular · acceso autenticado",
    pg_hist_ritual_inicia: "Inicia",
    pg_hist_ritual_conecta: "Conecta",
    pg_hist_ritual_solana: "wallet Solana opcional",
    pg_hist_ritual_accede: "Accede",
    pg_hist_ritual_firmado: "a tu historial firmado",
    pg_hist_iniciar_sesion: "Iniciar Sesión",
    pg_hist_footer_sesiones: "0 sesiones activas · acceso autenticado · v 2.0",
    pg_hist_stat_total: "Total evaluaciones",
    pg_hist_stat_mejor_score: "Mejor score",
    pg_hist_stat_promedio: "Promedio",
    pg_hist_orden_fecha: "Fecha",
    pg_hist_orden_score_total: "Score total",
    pg_hist_orden_afinidad: "Afinidad (kcal/mol)",
    pg_hist_cargando: "Cargando evaluaciones...",
    pg_hist_en_espera: "Historial en espera",
    pg_hist_ritual_conservar: "conservar en tu historial",
    pg_hist_lanzar_pipeline: "Iniciar pipeline",
    pg_hist_footer_evaluaciones:
      "0 evaluaciones guardadas · usuario {user} · v 2.0",
    pg_hist_th_target: "Diana",
    pg_hist_th_estado: "Estado de evaluación",
    pg_hist_th_corrida: "Corrida",
    pg_hist_th_score: "Score global",
    pg_hist_th_afinidad: "Afinidad (kcal/mol)",
    pg_hist_th_mw: "MW",
    pg_hist_th_lipinski: "Regla de Lipinski",
    pg_hist_th_recibo: "Recibo",
    pg_hist_th_fecha: "Fecha",
    pg_hist_promovida_moldex: "Promovida a Moldex",
    pg_hist_estado_pendiente: "En espera",
    pg_hist_estado_validada: "Validada",
    pg_hist_estado_en_curso: "En curso",
    pg_hist_estado_completada: "Completada",
    pg_hist_estado_fallida: "Fallida",

    // ── Moldex: lo que quedaba ────────────────────────────────────
    pg_mx_cargando: "cargando moléculas · modo molecular · v 2.0",
    pg_mx_reintentar: "Reintentar conexión",
    pg_mx_vacio:
      "Aún no hay evaluaciones guardadas en tu bioteca. Cada entrada conserva una "
      + "evaluación, sus resultados observados y, cuando existe, un recibo de "
      + "integridad.",
    pg_mx_cero_guardadas: "0 moléculas guardadas · bioteca local · v 2.0",
    pg_mx_contexto_target: "CONTEXTO DEL TARGET",
    pg_mx_auditoria: "AUDITORÍA CIENTÍFICA",
    pg_mx_sin_advertencias:
      "No hay advertencias registradas para esta corrida.",
    pg_mx_red_pruebas: "red de pruebas",
    pg_mx_recibo_otra_corrida:
      ". El recibo sigue correspondiendo a la corrida que selló, no para la que "
      + "se ve aquí.",
    pg_mx_sello_sin_corrida: "Sello sin corrida registrada",
    pg_mx_recibo_sin_procedencia:
      "Este recibo es anterior al registro de procedencia: no consta qué corrida "
      + "atestiguó, así que no puede afirmarse que corresponda a las cifras "
      + "mostradas.",

    // ── Comunidad ─────────────────────────────────────────────────
    pg_com_sin_conexion: "Sin conexión",
    pg_com_intro:
      "Explora targets compartidos por la comunidad, descarga receptores curados "
      + "y consulta evaluaciones publicadas bajo sus condiciones declaradas.",
    pg_com_conectando: "Conectando con la comunidad…",
    pg_com_sin_resultados: "No hay resultados compartidos disponibles.",
    pg_com_orden_no_ranking:
      "El orden refleja los datos compartidos por el servicio; no es un ranking "
      + "de candidatos ni una predicción de actividad.",
    pg_com_compartir_no_disponible:
      "Compartir receptores desde esta pantalla no está disponible en esta "
      + "versión.",
    pg_com_sin_feed:
      "No hay un feed de actividad disponible en esta versión.",
    pg_com_reintentar: "Reintentar carga de datos compartidos",
    pg_com_buscar: "Buscar por PDB ID, nombre o categoría…",
    pg_com_conectado: "Conectado",
    pg_com_global: "Comunidad Global",
    pg_com_actualizar: "Actualizar",
    pg_com_targets_compartidos: "Targets Compartidos",
    pg_com_resultados_compartidos: "Resultados compartidos",
    pg_com_buscar_receptores: "Buscar receptores compartidos",
    pg_com_resultado_compartido: "Resultado compartido",
    pg_com_comparte_evidencia: "Comparte tu evidencia",
    pg_com_actividad_reciente: "Actividad reciente",
    pg_com_panel_global: "Comunidad Global",
    pg_com_panel_login: "Iniciar sesión",
    pg_com_panel_conectado: "Conectado",
    pg_com_panel_conectar: "Conectar",
    pg_com_panel_email: "Correo electrónico",
    pg_com_panel_pass: "Contraseña",
    pg_com_panel_conectando: "Conectando...",
    pg_com_panel_top_descubrimientos: "Mejores descubrimientos",
    pg_com_panel_compartir: "Comparte tus descubrimientos",

    // ── Navegación ────────────────────────────────────────────────
    pg_nav_opciones: "OPCIONES",
    pg_nav_comunidad: "COMUNIDAD",
    pg_nav_ciencia: "CIENCIA",
    pg_nav_batch: "Batch",
    pg_nav_logo_alt: "Logo de MolDesign",
    pg_nav_moldex: "Moldex",
    pg_nav_historial: "HISTORIAL",
    pg_nav_usuario_escritorio: "Usuario de escritorio",
    pg_nav_salir: "SALIR",
    pg_nav_entrar: "ENTRAR",

    // ── Inicio ────────────────────────────────────────────────────
    pg_inicio_iniciando_red_3d: "Iniciando Red 3D...",
    pg_inicio_pipeline: "Flujo de cálculo",
    pg_inicio_afinidad_kcal: "Afinidad (kcal/mol)",
    pg_inicio_etapas: "etapas",
    // El registro en cadena NO encabeza esta descripción. Sella la integridad de
    // un dossier —dice CUÁNDO se emitió algo—, y ponerlo primero sugeriría que
    // la propiedad intelectual es la función del producto en vez de la evidencia.
    pg_inicio_descripcion:
      "Comprobación previa antes de ejecutar, docking local con AutoDock Vina, "
      + "cohortes comparables bajo una configuración común, y dossier con paquete "
      + "verificable. El registro de integridad en cadena es opcional y sella cuándo "
      + "se emitió un dossier; no valida su ciencia.",
    pg_inicio_boton_empezar: "Iniciar Evaluación",
    pg_inicio_stack_label: "Stack Tecnológico",
    pg_inicio_stack_titulo: "Motores de Cómputo e IA",
    pg_inicio_stack_desc:
      "Las partículas fluyendo entre los nodos representan el flujo del pipeline. "
      + "Haz clic en un nodo para ver su detalle.",
    pg_inicio_comunidad_label: "Comunidad",
    pg_inicio_evaluaciones_compartidas: "Evaluaciones compartidas",
    pg_inicio_comunidad_creciendo:
      "La comunidad científica está creciendo. Sé el primero en compartir una evaluación.",
    pg_inicio_evaluaciones_desc:
      "Evaluaciones compartidas por la comunidad. El orden es por afinidad observada; "
      + "no es un ranking de candidatos.",

    // ── Lanzador ──────────────────────────────────────────────────
    pg_lanzador_componentes_locales: "Componentes locales",
    pg_lanzador_modelos_motores: "Modelos y motores",
    pg_lanzador_componentes_disponibles: "Componentes disponibles",
    pg_lanzador_abrir: "Abrir MolDesign",
    pg_lanzador_instalar_requerido: "Instalar motor requerido",
    pg_lanzador_descarga_una: " Hay {n} descarga en progreso.",
    pg_lanzador_descargas_varias: " Hay {n} descargas en progreso.",

    // ── El error global ───────────────────────────────────────────
    pg_err_titulo: "MolDesign no pudo abrir la interfaz",
    pg_err_subtitulo: "La ventana quedó sin pintar",
    pg_err_datos_intactos:
      "Es un fallo de la interfaz, no de tus datos: los casos, las evaluaciones y "
      + "los archivos guardados están intactos en su carpeta. El motor de cálculo "
      + "puede seguir en marcha aunque esta ventana no se haya pintado.",
    pg_err_recargar: "Recargar la ventana",
    pg_err_reiniciar_seguro:
      "Si vuelve a ocurrir, el detalle queda en el registro de la aplicación. "
      + "Reiniciar MolDesign es seguro.",
  },
  en: {
    pg_lote_intro:
      "Define a comparable cohort, check its inputs, run it under one shared "
      + "configuration and deliver evidence with its coverage.",
    pg_lote_receptor_comun:
      "One receptor and one shared configuration for every molecule. That is what "
      + "makes the rows comparable with each other.",
    pg_lote_comprobar_no_ejecuta: "Checking runs nothing.",
    pg_lote_superarla_no_predice:
      "Passing it does not predict binding or pharmacological quality: nothing has "
      + "been calculated yet.",
    pg_lote_bloqueada: "Blocked — it cannot be saved or run",
    pg_lote_avisos: "Notices — they do not block",
    pg_lote_orden_no_veredicto:
      "Sorted by observed Vina affinity. It is an order, not a verdict: "
      + "completing a docking does not demonstrate activity.",
    pg_lote_sin_estado: "There are no molecules with this status.",
    pg_lote_paquete_descargado: "Package downloaded as",
    pg_lote_manifiesto:
      ". It includes its manifest with hashes; verification is done by whoever "
      + "receives it.",
    pg_lote_dossier_no_cargado: "The dossier is not loaded.",
    pg_lote_inmutable:
      "A saved cohort is immutable: changing the receptor, the configuration or "
      + "the file produces another cohort, not an edit.",
    pg_lote_sin_merito:
      "This screen does not rank molecules by pharmacological merit and produces "
      + "no aggregate score. The observed Vina affinity is a ranking signal within "
      + "this protocol, not a free-energy measurement and not a prediction of "
      + "activity.",

    pg_hist_titulo: "Evaluation history",
    pg_hist_privado:
      "The history holds traces only your eyes should see: evaluations, results "
      + "and integrity receipts. Sign in to continue.",
    pg_hist_descripcion:
      "Every evaluation in your account, exactly as it is in the database. The "
      + "ones that also appear in Moldex carry the mark",
    pg_hist_ordenar: "Sort by:",
    pg_hist_vacio:
      "You have not saved any molecular evaluation yet. A saved evaluation keeps "
      + "the docking, its results, the observed hotspots and, when there is one, "
      + "its integrity receipt.",
    pg_hist_sin_recibo: "No receipt",
    pg_hist_verificando: "Checking session",
    pg_hist_targets_unicos: "Unique targets",
    pg_hist_copiar_id: "Copy run identifier: {taskId}",
    pg_hist_copiar_id_corto: "Copy run identifier {taskId}",
    pg_hist_anterior_task_id: "Run predating the task_id record",
    pg_hist_descargar_recibo: "Download integrity receipt PDF",
    pg_hist_acceso_bloqueado: "Access Blocked",
    pg_hist_subline_jwt: "autocomplete · validating jwt token · v 2.0",
    pg_hist_footer_autenticado: "molecular history · authenticated access",
    pg_hist_ritual_inicia: "Sign in",
    pg_hist_ritual_conecta: "Connect",
    pg_hist_ritual_solana: "optional Solana wallet",
    pg_hist_ritual_accede: "Access",
    pg_hist_ritual_firmado: "to your signed history",
    pg_hist_iniciar_sesion: "Sign in",
    pg_hist_footer_sesiones: "0 active sessions · authenticated access · v 2.0",
    pg_hist_stat_total: "Total evaluations",
    pg_hist_stat_mejor_score: "Best score",
    pg_hist_stat_promedio: "Average",
    pg_hist_orden_fecha: "Date",
    pg_hist_orden_score_total: "Total score",
    pg_hist_orden_afinidad: "Affinity (kcal/mol)",
    pg_hist_cargando: "Loading evaluations...",
    pg_hist_en_espera: "History on standby",
    pg_hist_ritual_conservar: "preserve in your history",
    pg_hist_lanzar_pipeline: "Launch pipeline",
    pg_hist_footer_evaluaciones:
      "0 saved evaluations · user {user} · v 2.0",
    pg_hist_th_target: "Target",
    pg_hist_th_estado: "Evaluation status",
    pg_hist_th_corrida: "Run",
    pg_hist_th_score: "Global score",
    pg_hist_th_afinidad: "Affinity (kcal/mol)",
    pg_hist_th_mw: "MW",
    pg_hist_th_lipinski: "Lipinski rule",
    pg_hist_th_recibo: "Receipt",
    pg_hist_th_fecha: "Date",
    pg_hist_promovida_moldex: "Promoted to Moldex",
    pg_hist_estado_pendiente: "Pending",
    pg_hist_estado_validada: "Validated",
    pg_hist_estado_en_curso: "Running",
    pg_hist_estado_completada: "Completed",
    pg_hist_estado_fallida: "Failed",

    pg_mx_cargando: "loading molecules · molecular mode · v 2.0",
    pg_mx_reintentar: "Retry connection",
    pg_mx_vacio:
      "There are no saved evaluations in your library yet. Each entry keeps one "
      + "evaluation, its observed results and, when there is one, an integrity "
      + "receipt.",
    pg_mx_cero_guardadas: "0 molecules saved · local library · v 2.0",
    pg_mx_contexto_target: "TARGET CONTEXT",
    pg_mx_auditoria: "SCIENTIFIC AUDIT",
    pg_mx_sin_advertencias: "No warnings were recorded for this run.",
    pg_mx_red_pruebas: "test network",
    pg_mx_recibo_otra_corrida:
      ". The receipt still corresponds to the run it sealed, not to the one shown "
      + "here.",
    pg_mx_sello_sin_corrida: "Seal with no recorded run",
    pg_mx_recibo_sin_procedencia:
      "This receipt predates the provenance record: which run it attested is not "
      + "on file, so it cannot be stated that it corresponds to the figures shown.",

    pg_com_sin_conexion: "No connection",
    pg_com_intro:
      "Explore targets shared by the community, download curated receptors and "
      + "consult evaluations published under their declared terms.",
    pg_com_conectando: "Connecting to the community…",
    pg_com_sin_resultados: "No shared results are available.",
    pg_com_orden_no_ranking:
      "The order reflects the data shared by the service; it is not a ranking of "
      + "candidates and not a prediction of activity.",
    pg_com_compartir_no_disponible:
      "Sharing receptors from this screen is not available in this version.",
    pg_com_sin_feed:
      "No activity feed is available in this version.",
    pg_com_reintentar: "Retry loading the shared data",
    pg_com_buscar: "Search by PDB ID, name or category…",
    pg_com_conectado: "Connected",
    pg_com_global: "Global Community",
    pg_com_actualizar: "Refresh",
    pg_com_targets_compartidos: "Shared Targets",
    pg_com_resultados_compartidos: "Shared results",
    pg_com_buscar_receptores: "Search shared receptors",
    pg_com_resultado_compartido: "Shared result",
    pg_com_comparte_evidencia: "Share your evidence",
    pg_com_actividad_reciente: "Recent activity",
    pg_com_panel_global: "Global Community",
    pg_com_panel_login: "Log in",
    pg_com_panel_conectado: "Connected",
    pg_com_panel_conectar: "Connect",
    pg_com_panel_email: "Email",
    pg_com_panel_pass: "Password",
    pg_com_panel_conectando: "Connecting...",
    pg_com_panel_top_descubrimientos: "Top discoveries",
    pg_com_panel_compartir: "Share your discoveries",

    // ── Navegación ────────────────────────────────────────────────
    pg_nav_opciones: "OPTIONS",
    pg_nav_comunidad: "COMMUNITY",
    pg_nav_ciencia: "SCIENCE",
    pg_nav_batch: "Batch",
    pg_nav_logo_alt: "MolDesign logo",
    pg_nav_moldex: "Moldex",
    pg_nav_historial: "HISTORY",
    pg_nav_usuario_escritorio: "Desktop User",
    pg_nav_salir: "SIGN OUT",
    pg_nav_entrar: "SIGN IN",

    // ── Inicio ────────────────────────────────────────────────────
    pg_inicio_iniciando_red_3d: "Starting 3D Network...",
    pg_inicio_pipeline: "Pipeline",
    pg_inicio_afinidad_kcal: "Affinity (kcal/mol)",
    pg_inicio_etapas: "stages",
    pg_inicio_descripcion:
      "Preflight before running, local AutoDock Vina docking, comparable cohorts "
      + "under a common configuration, and a dossier with a verifiable package. "
      + "On-chain integrity registration is optional and seals when a dossier was "
      + "issued; it does not validate its science.",
    pg_inicio_boton_empezar: "Start Evaluation",
    pg_inicio_stack_label: "Technology Stack",
    pg_inicio_stack_titulo: "Compute Engines & AI",
    pg_inicio_stack_desc:
      "Particles flowing between nodes represent the pipeline flow. Click on a node "
      + "to view details.",
    pg_inicio_comunidad_label: "Community",
    pg_inicio_evaluaciones_compartidas: "Shared evaluations",
    pg_inicio_comunidad_creciendo:
      "The scientific community is growing. Be the first to share an evaluation.",
    pg_inicio_evaluaciones_desc:
      "Evaluations shared by the community, ordered by observed docking affinity. "
      + "This is not a candidate ranking.",

    // ── Lanzador ──────────────────────────────────────────────────
    pg_lanzador_componentes_locales: "Local components",
    pg_lanzador_modelos_motores: "Models and engines",
    pg_lanzador_componentes_disponibles: "Available components",
    pg_lanzador_abrir: "Open MolDesign",
    pg_lanzador_instalar_requerido: "Install required engine",
    pg_lanzador_descarga_una: " {n} download in progress.",
    pg_lanzador_descargas_varias: " {n} downloads in progress.",

    pg_err_titulo: "MolDesign could not open the interface",
    pg_err_subtitulo: "The window was left unpainted",
    pg_err_datos_intactos:
      "This is an interface failure, not a failure of your data: your cases, your "
      + "evaluations and your saved files are intact in their folder. The compute "
      + "engine may still be running even though this window was not painted.",
    pg_err_recargar: "Reload the window",
    pg_err_reiniciar_seguro:
      "If it happens again, the detail is left in the application log. Restarting "
      + "MolDesign is safe.",
  },
};
