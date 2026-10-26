// =====================================================================
// Casos — el espacio reproducible: proteína, hipótesis, corridas, informe
// =====================================================================
//
// LA REGLA QUE MANDA EN ESTE MÓDULO. Los casos son donde el producto declara lo
// que NO sabe, y esas frases son las que menos margen tienen al traducirse:
//
//   · «No se puede afirmar a qué inputs corresponde este informe» no se vuelve
//     «may not correspond»: la imposibilidad de afirmar es el hecho.
//   · «Lo que quede en "No definido" se declarará como tal en el dossier, no se
//     rellenará por su cuenta» promete una ausencia. En inglés promete lo mismo.
//   · «Sólo puedes documentar una abstención» es una restricción, no un consejo.
//
// «No definido» aparece en el dossier como valor literal, así que su traducción
// tiene que ser la que el dossier también use. Va en `comun` como
// `c_no_definido` para que no puedan divergir.

import type { ModuloDeTraduccion } from "./index";

export const casos: ModuloDeTraduccion = {
  es: {
    ca_context_question_question: "¿Qué intenta responder este caso?",
    ca_context_question_hint: "Sin esto, el dossier no puede declarar qué se estaba preguntando.",
    ca_context_decision_question: "¿Qué decisión se pretende tomar?",
    ca_context_decision_hint: "Una evidencia sin decisión asociada no se puede calificar de suficiente ni de insuficiente.",
    ca_context_systemRationale_question: "¿Qué justifica la elección del sistema?",
    ca_context_systemRationale_hint: "Estructura, ensamblaje, cadenas y estado: por qué éste y no otro.",
    ca_context_controls_question: "¿Qué controles o referencias existen?",
    ca_context_controls_hint: "Ligando de referencia, redock del cristal, series conocidas, negativos.",
    ca_context_assumptions_question: "¿Qué supuestos se están haciendo?",
    ca_context_assumptions_hint: "Protonación, tautomería, aguas, cofactores, rigidez del receptor.",
    ca_context_uncertainties_question: "¿Qué incertidumbres ya se conocen?",
    ca_context_uncertainties_hint: "Lo que ya se sabe que este caso NO podrá resolver.",
    ca_context_notes_question: "Notas",
    ca_context_notes_hint: "Contexto libre. Aparece en el dossier; no entra en ningún cálculo.",
    // ── Espacio vacío y creación ──────────────────────────────────
    ca_crear_titulo: "Crea un caso de estudio",
    ca_crear_descripcion:
      "Reúne una proteína, una hipótesis de sitio, ligandos, corridas, controles "
      + "e informes en un espacio reproducible.",
    ca_crear_boton: "Crear un caso",
    ca_move_work_account: "Llevarlo a mi cuenta",
    ca_work_transferred: "Trabajo traspasado a tu cuenta.",
    ca_case_singular: "caso",
    ca_case_plural: "casos",
    ca_and: "y",
    ca_context_heading: "Contexto",
    ca_context_questions_heading: "Preguntas del caso",
    ca_dossier_review_sidebar: "Disposici\u00f3n cient\u00edfica y contexto",
    ca_contexto_contador: "{n} / {max} caracteres",
    ca_contexto_excede: "Supera en {exceso} caracteres el límite del dossier ({max}). El dossier no se podrá actualizar hasta acortarlo; tu texto no se ha modificado.",
    ca_abstain_label: "Abstenerse.",
    ca_dossier_update: "Actualizar dossier",
    ca_dossier_expandir: "Pantalla completa",
    ca_dossier_reducir: "Salir de pantalla completa",
    ca_open_existing_folder: "Abrir carpeta existente",
    ca_new_case_title: "Caso nuevo",
    ca_approximate_type: "Tipo aproximado",
    ca_kind_explore: "Explorar una hipótesis",
    ca_kind_compare: "Comparar una serie",
    ca_kind_review: "Revisar una pose",
    ca_kind_prepare: "Preparar evidencia para un cálculo posterior",
    ca_nombre_carpeta_invalido: "Ese nombre no puede convertirse en una carpeta válida. Evita caracteres reservados del sistema.",
    ca_run_id_label: "Corrida {id}",
    ca_solo_lo_minimo:
      "Las preguntas científicas se responden después, en «Detalles del caso». "
      + "Aquí sólo lo mínimo.",
    ca_ubicacion: "Ubicación",
    ca_cambiar_carpeta: "Cambiar carpeta…",
    ca_carpeta_por_defecto: "Carpeta por defecto. Puedes cambiarla.",
    ca_carpeta_por_defecto_fallo: "No se pudo preparar la carpeta por defecto. Elige una carpeta.",
    ca_aviso_onedrive:
      "Esta carpeta está dentro de OneDrive, que puede bloquear o duplicar archivos mientras se escriben. Si notas problemas, elige otra carpeta.",
    ca_carpeta_se_llamara: "La carpeta se llamará",
    ca_nombre_visible_conserva:
      ": el nombre visible del caso conserva lo que has escrito.",
    ca_ejemplo_nombre: "p. ej. Serie de inhibidores — cribado inicial",

    // ── Panel lateral ─────────────────────────────────────────────
    ca_mostrar_casos: "Mostrar los casos",
    ca_ocultar_casos: "Ocultar los casos",
    ca_mostrar_panel: "Mostrar el panel de casos",
    ca_ocultar_panel: "Ocultar el panel de casos",
    ca_cerrar_panel: "Cerrar panel de casos",
    ca_ancho_panel: "Ancho del panel de casos",
    ca_mostrar_carpeta: "Mostrar la carpeta de {nombre}",
    ca_sidebar_cases: "Casos",
    ca_sidebar_archived: "Archivados",
    ca_sidebar_archive: "Archivar (reversible)",
    ca_sidebar_search: "Buscar",
    ca_sidebar_search_cases: "Buscar casos",
    ca_sidebar_active_cases: "Casos activos",
    ca_sidebar_new_case: "Nuevo caso",
    ca_sidebar_restore: "Restaurar",
    ca_workspace_open_report: "Abrir informe",
    ca_workspace_storage: "Almacenamiento",
    ca_workspace_copy_id: "Copiar identificador",
    ca_workspace_run_registered: "Corrida registrada",
    ca_workspace_dismiss_notice: "Descartar aviso",
    ca_workspace_retry_save: "Reintentar guardado",
    ca_workspace_in_progress: "en curso",
    ca_workspace_tracking_interrupted: "seguimiento interrumpido",
    ca_workspace_details: "Detalles",
    ca_workspace_storage_browser: "Guardado en este navegador",
    ca_storage_device: "Carpeta en este equipo",
    ca_view_evaluation: "Evaluación",
    ca_view_report: "Dossier",
    ca_disposition_accept: "Aceptar evidencia",
    ca_disposition_limit: "Aceptar con límites",
    ca_disposition_abstain: "Abstenerse",
    ca_disposition_save_all_hint: "Al guardar, se registran la disposici\u00f3n y todas las respuestas del caso.",
    ca_disposition_saving: "Guardando disposici\u00f3n y contexto\u2026",
    ca_pending_details_zero: "Sin detalles pendientes",
    ca_pending_detail_one: "{count} detalle pendiente",
    ca_pending_details_many: "{count} detalles pendientes",
    ca_case_status_draft: "Borrador",
    ca_case_status_qualifying: "Cualificando",
    ca_case_status_ready: "Listo",
    ca_case_status_running: "Ejecutando",
    ca_case_status_review: "En revisión",
    ca_case_status_completed: "Completado",
    ca_case_status_abstained: "Abstención",
    ca_run_state_idle: "preparada",
    ca_run_state_submitted: "enviada",
    ca_run_state_running: "en curso",
    ca_run_state_interrupted: "seguimiento interrumpido",
    ca_run_state_completed: "completada",
    ca_run_state_failed: "fallida",
    ca_run_state_cancelled: "cancelada",
    ca_case_activity_no_evaluations: "sin evaluaciones",
    ca_case_activity_undated: "evaluación sin fecha",
    ca_case_activity_evaluated: "evaluada {time}",
    ca_case_activity_started: "iniciada {time}",
    ca_time_just_now: "hace instantes",
    ca_time_minutes_ago: "hace {count} min",
    ca_time_hours_ago: "hace {count} h",
    ca_time_days_ago: "hace {count} d",
    ca_recovery_relocate: "Relocalizar",
    ca_recovery_forget: "Retirar del índice",
    ca_recovery_repair: "Reparar",
    ca_receptor_label_single: "{pdbId} · cadena {chain}",
    ca_receptor_label_multiple: "{pdbId} · cadenas {chains}",

    // ── Detalles y contexto ───────────────────────────────────────
    ca_detalles: "Detalles del caso",
    ca_cerrar_detalles: "Cerrar detalles del caso",
    ca_detalles_con_pendientes: "Detalles del caso, {pendientes}",
    ca_modo_del_caso: "Modo del caso",
    ca_nada_bloquea:
      "Ninguna de estas preguntas bloquea la evaluación. Lo que quede en «No "
      + "definido» se declarará como tal en el dossier, no se rellenará por su "
      + "cuenta.",

    // ── Corrida sin registrar y carpetas ──────────────────────────
    ca_corrida_arranco: "La corrida arrancó pero",
    ca_id_no_guardado: "su identificador no se pudo guardar",
    ca_resultado_no_recuperado: "su resultado no se ha podido recuperar",
    ca_nada_cambiado: ". No se ha cambiado nada.",
    ca_no_se_importa_solo: ". No se importará por su cuenta.",
    ca_usar_carpeta_nueva: "Usar la carpeta nueva",
    ca_inicializar_como_caso: "Inicializar como caso",
    ca_ya_registrado: "El caso ya está registrado en otra carpeta",
    ca_carpeta_sin_caso: "Carpeta sin caso",

    // ── Historial de corridas ─────────────────────────────────────
    ca_historial_titulo: "Evaluaciones anteriores de este caso",
    ca_historial_cerrar: "Cerrar historial de evaluaciones del caso",
    ca_sin_evaluaciones: "Este caso todavía no ha lanzado ninguna evaluación.",
    ca_otra_hipotesis: "Otra hipótesis",
    ca_otro_protocolo: "Otro protocolo",
    ca_recuperando_resultado:
      "Recuperando el resultado guardado de esta corrida…",
    ca_history_one_run: "1 corrida registrada.",
    ca_history_many_runs: "{n} corridas registradas.",
    ca_history_on_screen: "En pantalla",
    ca_history_protocol_unregistered: "Protocolo no registrado",
    ca_history_modo_unico: "Único K={k}",
    ca_history_modo_ensemble: "Ensemble K={k}",
    ca_history_difiere: "Difiere del sistema inicial: {detalle}.",
    ca_history_dif_dockingEngine: "motor {run} (sistema: {sistema})",
    ca_history_dif_exhaustiveness: "exhaustividad {run} (sistema: {sistema})",
    ca_history_dif_numPoses: "{run} poses (sistema: {sistema})",
    ca_history_dif_conformers: "K={run} (sistema: K={sistema})",
    ca_history_filtros: "Filtros del historial",
    ca_history_filtro_modo: "Modo de la corrida",
    ca_history_filtro_estado: "Estado",
    ca_history_todos_estados: "Todos",
    ca_history_modo_todas: "Todas ({n})",
    ca_history_modo_unicas: "Únicas ({n})",
    ca_history_modo_ensembles: "Ensembles ({n})",
    ca_history_buscar: "Buscar por SMILES o corrida",
    ca_history_mostrando: "Mostrando {n} de {total}",
    ca_history_sin_coincidencias: "Ninguna evaluación coincide con este filtro.",
    ca_history_quitar_filtros: "Quitar filtros",
    ca_history_hide: "Ocultar",
    ca_history_view_result: "Ver resultado",
    ca_history_poses: "Poses",
    ca_history_receptor: "Receptor",
    ca_history_informe: "Descargar informe",
    ca_history_3d_complex: "Complejo 3D",

    // ── Informe ───────────────────────────────────────────────────
    ca_informe_titulo: "Informe del caso",
    ca_volver_evaluacion: "Volver a Evaluación",
    ca_informe_anterior: "Este informe es de una corrida anterior.",
    ca_informe_anterior_detalle:
      "Los inputs del caso han cambiado desde que se ejecutó, así que no es "
      + "evidencia de la hipótesis actual. Para obtener evidencia de los inputs "
      + "de ahora hay que volver a evaluar.",
    ca_informe_sin_huella:
      "No se puede afirmar a qué inputs corresponde este informe.",
    ca_informe_sin_huella_detalle:
      "La corrida se lanzó antes de que el caso registrara la huella de sus "
      + "inputs. Se conserva por trazabilidad; no se le atribuye la hipótesis "
      + "actual.",
    ca_dossier_corrida: "Dossier de la corrida",
    ca_dossier_caso: "Dossier del caso",
    ca_dossier_lo_redacta:
      "El documento lo redacta el motor con lo que este caso declaró y con lo que "
      + "la corrida produjo de verdad. Lo que quedó sin responder aparece dentro "
      + "como «NO DEFINIDO»: no se rellena por su cuenta.",
    ca_dossier_generando: "Generando el dossier del caso…",
    ca_dossier_fallo: "No se pudo generar el dossier",
    ca_dossier_descargado: "Paquete descargado como",
    ca_dossier_manifiesto:
      ". Incluye su propio manifiesto con hashes; la verificación la hace quien "
      + "lo reciba.",

    // ── Disposición científica ────────────────────────────────────
    ca_disposicion_titulo: "Disposición científica",
    ca_disposicion_descripcion:
      "Decide qué puede afirmarse de esta corrida. La justificación queda "
      + "guardada junto a la huella de inputs.",
    ca_disposicion_sin_huella:
      "Esta evidencia no coincide con los inputs actuales o no tiene una huella "
      + "comprobable. Sólo puedes documentar una abstención hasta volver a "
      + "ejecutar con los inputs actuales.",
    ca_disposicion_abstencion:
      "No se afirmará una conclusión con esta corrida.",
    ca_disposicion_anteriores:
      "Disposiciones anteriores de este caso (retiradas al cambiar los inputs):",
    ca_justificacion: "Justificación (obligatoria)",
    ca_justificacion_ejemplo:
      "Qué evidencia respalda esta decisión y qué límites tiene…",
    ca_estado_corrida_idle: "Sin arrancar",
    ca_estado_corrida_submitted: "Enviada",
    ca_estado_corrida_running: "Ejecutando",
    ca_estado_corrida_interrupted: "Seguimiento perdido",
    ca_estado_corrida_completed: "Terminada",
    ca_estado_corrida_failed: "Fallida",
    ca_estado_corrida_cancelled: "Cancelada",
    ca_sistema_fijado:
      "Este caso ya está fijado a su sistema estructural. Puedes cambiar el ligando y el protocolo; para cambiar receptor, caja o residuos crea otro caso.",
    ca_trabajo_en_curso_cambio:
      "Hay trabajo en curso en este caso. Espera a que termine o cancélalo antes de cambiar de caso: cambiar ahora dejaría la ejecución sin seguimiento.",
    ca_trabajo_en_curso_bloquea:
      "Hay trabajo en curso en este caso. Espera a que termine o cancélalo para cambiar de caso.",
  },
  en: {
    ca_context_question_question: "What question does this case address?",
    ca_context_question_hint: "Without this, the dossier cannot state what question was being asked.",
    ca_context_decision_question: "What decision will be made?",
    ca_context_decision_hint: "Evidence without an associated decision cannot be judged sufficient or insufficient.",
    ca_context_systemRationale_question: "What justifies the choice of system?",
    ca_context_systemRationale_hint: "Structure, assembly, chains and state: why this system was chosen.",
    ca_context_controls_question: "What controls or references are available?",
    ca_context_controls_hint: "Reference ligand, crystal redocking, known series, negative controls.",
    ca_context_assumptions_question: "What assumptions are being made?",
    ca_context_assumptions_hint: "Protonation, tautomerism, waters, cofactors, receptor rigidity.",
    ca_context_uncertainties_question: "What uncertainties are already known?",
    ca_context_uncertainties_hint: "What is already known to be beyond what this case can resolve.",
    ca_context_notes_question: "Notes",
    ca_context_notes_hint: "Free context. It appears in the dossier and is not used in any calculation.",
    ca_crear_titulo: "Create a study case",
    ca_crear_descripcion:
      "Bring a protein, a site hypothesis, ligands, runs, controls and reports "
      + "together in one reproducible space.",
    ca_crear_boton: "Create a case",
    ca_move_work_account: "Move it to my account",
    ca_work_transferred: "Work transferred to your account.",
    ca_case_singular: "case",
    ca_case_plural: "cases",
    ca_and: "and",
    ca_context_heading: "Context",
    ca_context_questions_heading: "Case questions",
    ca_dossier_review_sidebar: "Scientific disposition and context",
    ca_contexto_contador: "{n} / {max} characters",
    ca_contexto_excede: "Exceeds the dossier limit ({max}) by {exceso} characters. The dossier cannot be updated until it is shortened; your text has not been changed.",
    ca_abstain_label: "Abstain.",
    ca_dossier_update: "Refresh dossier",
    ca_dossier_expandir: "Full screen",
    ca_dossier_reducir: "Exit full screen",
    ca_open_existing_folder: "Open an existing folder",
    ca_new_case_title: "New case",
    ca_approximate_type: "Approximate type",
    ca_kind_explore: "Explore a hypothesis",
    ca_kind_compare: "Compare a series",
    ca_kind_review: "Review a pose",
    ca_kind_prepare: "Prepare evidence for a later calculation",
    ca_nombre_carpeta_invalido: "That name cannot become a valid folder. Avoid reserved system characters.",
    ca_run_id_label: "Run {id}",
    ca_solo_lo_minimo:
      "The scientific questions are answered later, in «Case details». Only the "
      + "essentials here.",
    ca_ubicacion: "Location",
    ca_cambiar_carpeta: "Change folder…",
    ca_carpeta_por_defecto: "Default folder. You can change it.",
    ca_carpeta_por_defecto_fallo: "The default folder could not be prepared. Choose a folder.",
    ca_aviso_onedrive:
      "This folder is inside OneDrive, which can lock or duplicate files while they are being written. If you notice problems, choose another folder.",
    ca_carpeta_se_llamara: "The folder will be called",
    ca_nombre_visible_conserva:
      ": the visible name of the case keeps exactly what you typed.",
    ca_ejemplo_nombre: "e.g. Inhibitor series — initial screen",

    ca_mostrar_casos: "Show cases",
    ca_ocultar_casos: "Hide cases",
    ca_mostrar_panel: "Show the cases panel",
    ca_ocultar_panel: "Hide the cases panel",
    ca_cerrar_panel: "Close the cases panel",
    ca_ancho_panel: "Width of the cases panel",
    ca_mostrar_carpeta: "Show the folder of {nombre}",
    ca_sidebar_cases: "Cases",
    ca_sidebar_archived: "Archived",
    ca_sidebar_archive: "Archive (reversible)",
    ca_sidebar_search: "Search",
    ca_sidebar_search_cases: "Search cases",
    ca_sidebar_active_cases: "Active cases",
    ca_sidebar_new_case: "New case",
    ca_sidebar_restore: "Restore",
    ca_workspace_open_report: "Open report",
    ca_workspace_storage: "Storage",
    ca_workspace_copy_id: "Copy identifier",
    ca_workspace_run_registered: "Run registered",
    ca_workspace_dismiss_notice: "Dismiss notice",
    ca_workspace_retry_save: "Retry save",
    ca_workspace_in_progress: "in progress",
    ca_workspace_tracking_interrupted: "tracking interrupted",
    ca_workspace_details: "Details",
    ca_workspace_storage_browser: "Saved in this browser",
    ca_storage_device: "Folder on this device",
    ca_view_evaluation: "Evaluation",
    ca_view_report: "Dossier",
    ca_disposition_accept: "Accept the evidence",
    ca_disposition_limit: "Accept with limits",
    ca_disposition_abstain: "Abstain",
    ca_disposition_save_all_hint: "Saving records the disposition and all case answers.",
    ca_disposition_saving: "Saving disposition and context\u2026",
    ca_pending_details_zero: "No pending details",
    ca_pending_detail_one: "{count} pending detail",
    ca_pending_details_many: "{count} pending details",
    ca_case_status_draft: "Draft",
    ca_case_status_qualifying: "Qualifying",
    ca_case_status_ready: "Ready",
    ca_case_status_running: "Running",
    ca_case_status_review: "Review",
    ca_case_status_completed: "Completed",
    ca_case_status_abstained: "Abstained",
    ca_run_state_idle: "prepared",
    ca_run_state_submitted: "submitted",
    ca_run_state_running: "in progress",
    ca_run_state_interrupted: "tracking interrupted",
    ca_run_state_completed: "completed",
    ca_run_state_failed: "failed",
    ca_run_state_cancelled: "canceled",
    ca_case_activity_no_evaluations: "no evaluations",
    ca_case_activity_undated: "evaluation has no date",
    ca_case_activity_evaluated: "evaluated {time}",
    ca_case_activity_started: "started {time}",
    ca_time_just_now: "just now",
    ca_time_minutes_ago: "{count} min ago",
    ca_time_hours_ago: "{count} hr ago",
    ca_time_days_ago: "{count} days ago",
    ca_recovery_relocate: "Relocate",
    ca_recovery_forget: "Remove from index",
    ca_recovery_repair: "Repair",
    ca_receptor_label_single: "{pdbId} · chain {chain}",
    ca_receptor_label_multiple: "{pdbId} · chains {chains}",

    ca_detalles: "Case details",
    ca_cerrar_detalles: "Close case details",
    ca_detalles_con_pendientes: "Case details, {pendientes}",
    ca_modo_del_caso: "Case mode",
    ca_nada_bloquea:
      "None of these questions blocks the evaluation. Whatever stays «Not "
      + "defined» will be declared as such in the dossier; it is not filled in "
      + "on its own.",

    ca_corrida_arranco: "The run started but",
    ca_id_no_guardado: "its identifier could not be saved",
    ca_resultado_no_recuperado: "its result could not be recovered",
    ca_nada_cambiado: ". Nothing has been changed.",
    ca_no_se_importa_solo: ". It will not be imported on its own.",
    ca_usar_carpeta_nueva: "Use the new folder",
    ca_inicializar_como_caso: "Initialize as a case",
    ca_ya_registrado: "The case is already registered in another folder",
    ca_carpeta_sin_caso: "Folder with no case",

    ca_historial_titulo: "Previous evaluations of this case",
    ca_historial_cerrar: "Close the case evaluation history",
    ca_sin_evaluaciones: "This case has not launched any evaluation yet.",
    ca_otra_hipotesis: "Another hypothesis",
    ca_otro_protocolo: "Another protocol",
    ca_recuperando_resultado: "Recovering the saved result of this run…",
    ca_history_one_run: "1 run recorded.",
    ca_history_many_runs: "{n} runs recorded.",
    ca_history_on_screen: "On screen",
    ca_history_protocol_unregistered: "Protocol not recorded",
    ca_history_modo_unico: "Single K={k}",
    ca_history_modo_ensemble: "Ensemble (K={k})",
    ca_history_difiere: "Differs from the initial system: {detalle}.",
    ca_history_dif_dockingEngine: "engine {run} (system: {sistema})",
    ca_history_dif_exhaustiveness: "exhaustiveness {run} (system: {sistema})",
    ca_history_dif_numPoses: "{run} poses (system: {sistema})",
    ca_history_dif_conformers: "K={run} (system: K={sistema})",
    ca_history_filtros: "History filters",
    ca_history_filtro_modo: "Run mode",
    ca_history_filtro_estado: "State",
    ca_history_todos_estados: "All",
    ca_history_modo_todas: "All ({n})",
    ca_history_modo_unicas: "Single ({n})",
    ca_history_modo_ensembles: "Ensemble runs ({n})",
    ca_history_buscar: "Search by SMILES or run",
    ca_history_mostrando: "Showing {n} of {total}",
    ca_history_sin_coincidencias: "No evaluation matches this filter.",
    ca_history_quitar_filtros: "Clear filters",
    ca_history_hide: "Hide",
    ca_history_view_result: "View result",
    ca_history_poses: "Poses",
    ca_history_receptor: "Receptor",
    ca_history_informe: "Download report",
    ca_history_3d_complex: "3D complex",

    ca_informe_titulo: "Case report",
    ca_volver_evaluacion: "Back to Evaluation",
    ca_informe_anterior: "This report is from an earlier run.",
    ca_informe_anterior_detalle:
      "The case inputs have changed since it ran, so it is not evidence for the "
      + "current hypothesis. To get evidence for the inputs as they are now, you "
      + "have to run the evaluation again.",
    ca_informe_sin_huella:
      "It cannot be stated which inputs this report corresponds to.",
    ca_informe_sin_huella_detalle:
      "The run was launched before the case recorded the fingerprint of its "
      + "inputs. It is kept for traceability; the current hypothesis is not "
      + "attributed to it.",
    ca_dossier_corrida: "Run dossier",
    ca_dossier_caso: "Case dossier",
    ca_dossier_lo_redacta:
      "The document is written by the engine from what this case declared and "
      + "from what the run actually produced. Whatever was left unanswered "
      + "appears inside as «NOT DEFINED»: it is not filled in on its own.",
    ca_dossier_generando: "Generating the case dossier…",
    ca_dossier_fallo: "The dossier could not be generated",
    ca_dossier_descargado: "Package downloaded as",
    ca_dossier_manifiesto:
      ". It includes its own manifest with hashes; verification is done by "
      + "whoever receives it.",

    ca_disposicion_titulo: "Scientific disposition",
    ca_disposicion_descripcion:
      "Decide what can be stated from this run. The rationale is stored "
      + "alongside the input fingerprint.",
    ca_disposicion_sin_huella:
      "This evidence does not match the current inputs, or it has no verifiable "
      + "fingerprint. You can only document an abstention until you run again "
      + "with the current inputs.",
    ca_disposicion_abstencion:
      "No conclusion will be stated from this run.",
    ca_disposicion_anteriores:
      "Earlier dispositions of this case (retired when the inputs changed):",
    ca_justificacion: "Rationale (required)",
    ca_justificacion_ejemplo:
      "What evidence supports this decision and what its limits are…",
    ca_estado_corrida_idle: "Not started",
    ca_estado_corrida_submitted: "Submitted",
    ca_estado_corrida_running: "Running",
    ca_estado_corrida_interrupted: "Tracking lost",
    ca_estado_corrida_completed: "Completed",
    ca_estado_corrida_failed: "Failed",
    ca_estado_corrida_cancelled: "Canceled",
    ca_sistema_fijado:
      "This case is already locked to its structural system. You can change the ligand and the protocol; to change the receptor, box or residues, create another case.",
    ca_trabajo_en_curso_cambio:
      "There is work in progress in this case. Wait for it to finish or cancel it before switching cases: switching now would leave the run untracked.",
    ca_trabajo_en_curso_bloquea:
      "There is work in progress in this case. Wait for it to finish or cancel it to switch cases.",
  },
};
