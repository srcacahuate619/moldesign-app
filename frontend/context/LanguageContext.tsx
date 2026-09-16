"use client";

import React, { createContext, useContext, useState, useEffect } from "react";
import { useAuth } from "../lib/auth";
import { getUserItem, setUserItem } from "../lib/userStorage";
import { TRADUCCIONES_POR_SUPERFICIE } from "./traducciones";

export type Locale = "es" | "en";

export interface Language {
  code: Locale;
  name: string;
  flag: string;
}

export const LANGUAGES: Language[] = [
  { code: "es", name: "Español", flag: "🇲🇽" },
  { code: "en", name: "English", flag: "🇺🇸" },
];

const MVP_LOCALES = new Set<Locale>(LANGUAGES.map((language) => language.code));

export const TRANSLATIONS: Record<Locale, Record<string, string>> = {
  // Los modulos por superficie van PRIMERO: si alguna clave coincidiera con una
  // del bloque historico, gana la historica y nada cambia de comportamiento.
  // Que no coincidan lo comprueba `idiomasCompletos.test.ts`, porque un choque
  // silencioso haria que una pantalla cambiara de texto al editar otra.
  es: {
    ...TRADUCCIONES_POR_SUPERFICIE.es,
    // Nav / Common
    options: "Opciones",
    batch: "Batch",
    evaluation: "Evaluación",
    moldex: "Moldex",
    support: "Soporte",
    logout: "Salir",
    login: "Entrar",
    welcome: "Bienvenido",
    close: "Cerrar",
    save: "Guardar",
    cancel: "Cancelar",
    confirm: "Confirmar",
    error: "Error",
    success: "Éxito",

    // Landing Page
    // NARRATIVA. Lo que este producto es, y lo que NO afirma ser. No descubre
    // fármacos, no predice eficacia y no sustituye un experimento: prepara
    // hipótesis, ejecuta evaluaciones iniciales y entrega evidencia que otro
    // puede verificar. Cualquier texto que prometa más de eso hay que
    // corregirlo aquí, no matizarlo con una nota al pie.
    hero_tagline: "LOCAL · CÓDIGO FUENTE PÚBLICO",
    hero_title_1: "PREPARA",
    hero_title_2: "EVALÚA",
    hero_title_3: "DOCUMENTA",
    hero_desc: "Una herramienta local con código fuente público para preparar hipótesis estructurales, ejecutar evaluaciones iniciales y entregar evidencia computacional reproducible. No descubre fármacos ni predice eficacia clínica, y no sustituye a un experimento.",
    evidence_tagline: "EVIDENCIA ESTRUCTURAL AUDITABLE",
    evidence_title_1: "CONFIANZA",
    evidence_title_2: "PROCEDENCIA",
    evidence_title_3: "TRANSFERENCIA",
    vision_label: "DIRECCIÓN FUTURA",
    vision_title: "El IDE del drug discovery",
    vision_desc: "La visión es convertir MolDesign en un entorno de trabajo donde cada decisión estructural conserve su contexto, incertidumbre y procedencia. Hoy el alcance es más acotado: prepara, evalúa y documenta evidencia estructural; no ejecuta FEP ni dinámica molecular y no cubre el descubrimiento de fármacos de principio a fin.",
    hero_button_edu: "Modo Estudiante",
    hero_button_pro: "Evaluación Avanzada",
    features_title: "Qué hace, exactamente",
    step_01_title: "Evaluación por caso",
    step_01_desc: "Un receptor, un ligando y una hipótesis declarada. La comprobación previa dice qué va a entrar en la corrida antes de ejecutarla.",
    step_02_title: "Cohortes comparables",
    step_02_desc: "Muchas moléculas bajo un único receptor y una configuración común, con su cobertura, sus excepciones y sus duplicados declarados.",
    step_03_title: "Dossier y paquete reproducible",
    step_03_desc: "Un PDF que dice qué se calculó y qué quedó sin evaluar, y un ZIP con manifiesto y hashes que un tercero puede verificar sin ejecutar nada.",
    step_04_title: "Ejecución local",
    step_04_desc: "El motor corre en este equipo. Ningún dato molecular sale de aquí salvo que tú lo exportes.",
    step_05_title: "Límites científicos declarados",
    step_05_desc: "Completar un acoplamiento no demuestra actividad. Lo que no se comprobó aparece como NO EVALUADO, no como aprobado.",
    stats_molecules: "Moléculas Evaluadas",
    stats_best_score: "Mejor afinidad observada (kcal/mol)",
    stats_certified: "Integridad registrada",

    // Options Panel
    opt_appearance: "Apariencia",
    opt_theme: "Tema",
    opt_theme_dark: "Oscuro",
    opt_theme_light: "Claro",
    opt_interface: "Interfaz",
    opt_sounds: "Sonidos de Interfaz",
    opt_sounds_muted: "Sonidos silenciados",
    opt_sounds_active: "Sonidos activos",
    opt_sounds_activate: "Clic para activar",
    opt_sounds_silence: "Clic para silenciar",
    opt_ai: "Intérprete IA",
    opt_ai_config: "Configurar proveedor IA",
    opt_ai_chat_open: "Abrir MolChat",
    opt_ai_chat_close: "Cerrar MolChat",
    opt_data: "Datos y Respaldo",
    opt_data_export: "Exportar Bioteca (JSON)",
    opt_data_export_desc: "Descarga todas tus moléculas y resultados en un archivo portátil",
    opt_data_export_success: "Respaldo exportado correctamente",
    opt_data_reset: "Restablecer datos de sesión",
    opt_data_reset_desc: "Cierra la sesión local activa. El historial de evaluaciones permanece en la base de datos.",
    opt_data_reset_warning: "Esta acción cerrará tu sesión local. Tus evaluaciones y moléculas no se eliminarán.",
    opt_data_reset_success: "Sesión restablecida",
    opt_legal: "Legal e Información",
    opt_legal_terms: "Términos y Privacidad",
    opt_legal_about: "Acerca de",

    // Legal / Terms Modal
    legal_title: "Marco Legal — MolDesign",
    legal_tab_terms: "Términos de Uso",
    legal_tab_priv: "Privacidad",
    legal_tab_lic: "Licencia",
    legal_local_first: "Local-First · Sin Telemetría · Conexiones externas opcionales",
    legal_understood: "Entendido",

    // Login Page
    login_title: "Inicio de Sesión Local",
    login_subtitle: "MolDesign ejecuta el acoplamiento y el análisis en tu dispositivo.",
    login_username: "Nombre de Usuario",
    login_password: "Contraseña (Mínimo 4 caracteres)",
    login_btn: "Acceder al Laboratorio",
    login_privacy_badge: "El cálculo se ejecuta en tu equipo. Las conexiones externas son opcionales.",
    login_error_fields: "Por favor, completa todos los campos correctamente.",
    login_error_auth: "Credenciales incorrectas.",

    // Evaluation Page
    eval_title: "Panel de Evaluación Molecular",
    eval_draw_tab: "1. Dibujar Molécula",
    eval_target_tab: "2. Seleccionar Blanco",
    eval_run_tab: "3. Simulación & Score",
    eval_results_tab: "4. Reporte Final",
    eval_target_select_title: "Selecciona el Blanco de Acoplamiento",
    eval_target_desc: "Selecciona el receptor proteico contra el cual se simulará el acoplamiento molecular (docking).",
    eval_run_simulation: "Iniciar Simulación Científica",
    eval_docking_progress: "Simulando acoplamiento molecular...",
    eval_docking_success: "Acoplamiento molecular completado con éxito.",
    eval_docking_fail: "Error durante la simulación de acoplamiento.",
    eval_vina_score: "Afinidad de Vina",
    eval_admet_score: "Propiedades ADMET",
    eval_solana_status: "Registro experimental en Solana",
    eval_solana_btn: "Probar registro en devnet",

    // ── Ayudas contextuales (los "?") ─────────────────────────────
    // Cada una desactiva UNA lectura equivocada concreta. Si un texto no
    // corrige un malentendido real, no lleva "?".
    ayuda_ensemble_titulo: "Generación conformacional",
    ayuda_ensemble: "El acoplamiento parte de una conformación 3D del ligando. Con «ensemble» se generan K y cada una se acopla por separado; las poses se juntan y se reordenan por afinidad. Amplía la COBERTURA: sube la probabilidad de que alguna conformación se parezca a la real. En la medición interna NO mejoró la elección de la pose top-1 — el cuello de botella se desplaza a la selección. Compra amplitud de búsqueda, no precisión, y cuesta K veces el tiempo de docking.",

    ayuda_exhaustividad_titulo: "Exhaustividad y semilla",
    ayuda_exhaustividad: "La exhaustividad es cuánto busca Vina dentro de la caja. Más búsqueda reduce la probabilidad de perderse una pose por azar, pero no corrige un sitio mal definido ni una preparación dudosa. La semilla fija el azar: sin ella la corrida no se puede repetir bit a bit.",

    ayuda_afinidad_titulo: "Afinidad Vina observada",
    ayuda_afinidad: "Es el valor que la función de puntuación de Vina asignó a esta pose, en kcal/mol. NO es una energía libre de unión medida, ni se convierte en Ki o IC50. Sirve para ordenar poses dentro de esta misma corrida; comparar entre receptores o protocolos distintos no está justificado.",

    ayuda_margen_titulo: "Margen del selector",
    ayuda_margen: "Es la distancia entre la primera y la segunda pose según el modelo de selección. NO es una probabilidad ni una nota: un margen alto dice que el modelo separó claramente, no que acertara. Por debajo del umbral el selector se abstiene, y la referencia vuelve a ser Vina top-1.",

    ayuda_estados_titulo: "Revisión vs. no evaluada",
    ayuda_estados: "«Controles superados» es lo único que autoriza llamar válida a una pose. «Requiere revisión» significa que la batería no corrió entera — no que la pose sea buena. «No evaluada» describe lo que le pasó al VALIDADOR, nunca a la molécula: ninguna de las dos es evidencia negativa sobre el compuesto.",

    ayuda_cobertura_titulo: "Cobertura evaluada",
    ayuda_cobertura: "Cuántas poses recibieron veredicto físico, sobre cuántas produjo la corrida. El denominador importa: «todas superadas» sobre 2 de 9 poses no dice nada de las 7 restantes. Por eso se muestran las dos cifras y nunca un porcentaje suelto.",

    ayuda_checksums_titulo: "Checksums del paquete",
    ayuda_checksums: "Demuestran INTEGRIDAD: que los bytes no cambiaron desde que se generó el paquete. No demuestran que el método fuera adecuado, que la preparación fuera correcta ni que la conclusión sea cierta. Que un paquete sea «válido» es una afirmación sobre los archivos, no sobre la ciencia.",

    // ── Evidencia estructural (P0-C) ──────────────────────────────
    // Español e inglés se mantienen en paralelo a propósito: una prueba
    // comprueba que ninguna clave `se_` existe sólo en un idioma.
    se_title: "Evidencia estructural",
    se_subtitle: "Cómo se generaron las poses, cuál se sugiere y qué controles físicos superó.",
    se_disclaimer: "Describe lo que esta corrida midió. No afirma actividad biológica, potencia ni éxito farmacológico.",
    se_legacy: "Corrida anterior a estas etapas",
    se_legacy_note: "Esta evaluación se ejecutó antes de que existieran la validación física y el selector de pose. No es que fallaran: no llegaron a ejecutarse.",
    se_empty: "Esta corrida no dejó poses ni contratos que mostrar.",
    se_loading: "Cargando evidencia estructural…",
    se_error: "No se pudo leer la evidencia estructural de esta corrida.",
    se_show_detail: "Ver detalle",
    se_hide_detail: "Ocultar detalle",
    se_not_reported: "No informado",
    se_technical: "Detalles técnicos",
    se_s1_title: "Generación",
    se_s1_lead: "Qué produjo el acoplamiento y con qué protocolo.",
    se_gen_poses: "Poses producidas",
    se_gen_affinity: "Mejor afinidad Vina observada",
    se_gen_affinity_note: "Es lo que Vina observó, no una medición experimental de energía libre.",
    se_gen_gap: "Δ pose 1–2",
    se_gen_protocol: "Protocolo",
    se_gen_seed: "Semilla",
    se_gen_parser: "Lectura de poses",
    se_gen_conformers: "Conformeros / restarts",
    se_gen_conformers_absent: "No registrados por esta corrida",
    se_gen_conformers_note: "El resultado no persiste estos parámetros. No se rellenan con la configuración del caso: sería atribuir a esta corrida un ajuste que nadie guardó con ella.",
    se_gen_receptor: "Receptor preparado",
    se_gen_receptor_absent: "Sin huella del receptor",
    se_gen_provenance: "Trazas de reproducibilidad",
    se_gen_no_poses: "El acoplamiento no conservó ninguna pose.",
    se_s2_title: "Selección",
    se_s2_lead: "El selector recomienda; no sustituye. La pose principal sigue siendo la de Vina.",
    se_sel_selected: "El selector recomienda una pose",
    se_sel_abstained: "El selector se abstuvo",
    se_sel_unavailable: "Selector no disponible",
    se_sel_error: "El selector falló",
    se_sel_vina_top1: "Vina top-1 (original)",
    se_sel_suggested: "Pose sugerida",
    se_sel_would_have: "Habría sugerido",
    se_sel_no_recommendation: "Sin recomendación",
    se_sel_confidence: "Margen de confianza",
    se_sel_threshold: "umbral",
    se_sel_confidence_note: "Es la distancia entre la primera y la segunda pose según el selector. No es una probabilidad ni una nota.",
    se_sel_model: "Modelo",
    se_sel_fallback: "Referencia: Vina top-1 (fallback)",
    se_sel_fallback_note: "No es un acierto del selector: es lo que queda cuando no hay recomendación.",
    se_sel_diverge: "La pose sugerida NO es la top-1 de Vina",
    se_sel_diverge_note: "Las dos se conservan y las dos se enseñan. La pose principal del producto sigue siendo la de Vina; la sugerida es una recomendación que puedes comparar.",
    se_sel_agree: "La pose sugerida coincide con la top-1 de Vina",
    se_sel_abstain_reason: "Razón",
    se_sel_scores: "Puntuación del selector por pose",
    se_sel_warnings: "Avisos del selector",
    se_reason_MODELO_AUSENTE: "El modelo del selector no está en este equipo.",
    se_reason_SIN_POSES: "La corrida no conservó ninguna pose.",
    se_reason_SIN_PDBQT_DE_POSE: "Alguna pose no conservó sus coordenadas, y el selector necesita las de todas para comparar.",
    se_reason_RECEPTOR_NO_DISPONIBLE: "No se pudo usar el receptor exacto de esta corrida, y el selector no opina sobre otro.",
    se_reason_SELECTOR_FALLO: "El selector no pudo evaluar estas poses.",
    se_reason_MARGEN_BAJO_UMBRAL: "El margen entre la primera y la segunda no llega al umbral de abstención.",
    se_reason_UNA_SOLA_POSE: "Una sola pose: no hay margen que medir.",
    se_reason_SELECCION_AUSENTE: "Esta evaluación es anterior a la etapa de selección de pose.",
    se_reason_RECEPTOR_AUSENTE: "El receptor preparado de esta corrida no está disponible.",
    se_reason_RECEPTOR_NO_COINCIDE: "El receptor del catálogo ya no es el que se acopló; validar contra otro daría un veredicto sobre un sistema distinto.",
    se_reason_RECEPTOR_SIN_HUELLA: "La corrida no registró el hash del receptor, así que no se puede demostrar cuál se usó.",
    se_reason_SIN_PLANTILLA: "No hay plantilla química declarada para reconstruir la pose; el grafo no se adivina.",
    se_reason_MAPA_SIN_HIDROGENOS_POLARES: "El mapa atómico no cubre los hidrógenos polares de la pose.",
    se_reason_VALIDADOR_NO_DISPONIBLE: "El validador físico no está disponible en este equipo.",
    se_reason_EVIDENCIA_AUSENTE: "Esta evaluación es anterior a la etapa de validación física.",

    // ── Controles de PoseBusters, dichos en español ───────────────────────
    //
    // Son los nombres de columna que devuelve PoseBusters 0.6.5 tal cual, y la
    // interfaz los imprimía crudos: en una pantalla en español aparecía
    // «Controles que fallan: minimum_distance_to_protein, internal_steric_clash».
    // El identificador sigue estando —va en el `title` de la línea y en el
    // dossier— porque es el que permite reproducir el control; lo que cambia es
    // lo que se lee.
    se_check_mol_pred_loaded: "Carga de la pose",
    se_check_mol_true_loaded: "Carga de la referencia",
    se_check_mol_cond_loaded: "Carga del receptor",
    se_check_sanitization: "Saneamiento químico (RDKit)",
    se_check_inchi_convertible: "Convertible a InChI",
    se_check_all_atoms_connected: "Todos los átomos conectados",
    se_check_no_radicals: "Sin radicales libres",
    se_check_bond_lengths: "Longitudes de enlace",
    se_check_bond_angles: "Ángulos de enlace",
    se_check_internal_steric_clash: "Choque estérico interno",
    se_check_aromatic_ring_flatness: "Planaridad de anillos aromáticos",
    "se_check_non-aromatic_ring_non-flatness": "No planaridad de anillos no aromáticos",
    se_check_double_bond_flatness: "Planaridad de dobles enlaces",
    se_check_internal_energy: "Energía interna del confórmero",
    "se_check_protein-ligand_maximum_distance": "Distancia máxima al receptor",
    se_check_minimum_distance_to_protein: "Distancia mínima a la proteína",
    se_check_minimum_distance_to_organic_cofactors: "Distancia mínima a cofactores orgánicos",
    se_check_minimum_distance_to_inorganic_cofactors: "Distancia mínima a cofactores inorgánicos",
    se_check_minimum_distance_to_waters: "Distancia mínima a las aguas",
    se_check_volume_overlap_with_protein: "Solapamiento de volumen con la proteína",
    se_check_volume_overlap_with_organic_cofactors: "Solapamiento de volumen con cofactores orgánicos",
    se_check_volume_overlap_with_inorganic_cofactors: "Solapamiento de volumen con cofactores inorgánicos",
    se_check_volume_overlap_with_waters: "Solapamiento de volumen con las aguas",
    se_s3_title: "Controles físicos",
    se_s3_lead: "Qué comprobó el validador sobre cada pose, y qué no pudo comprobar.",
    se_phys_passed: "Controles superados",
    se_phys_failed: "Controles fallidos",
    se_phys_review: "Requiere revisión",
    se_phys_not_evaluated: "No evaluada",
    se_phys_coverage: "Cobertura evaluada",
    se_phys_poses_unit: "poses",
    se_phys_engine: "Motor de validación",
    se_phys_failing: "Controles que fallan",
    se_phys_none_failing: "Ningún control de química o geometría falla.",
    se_phys_counts: "Desglose",
    se_phys_count_pass: "pasan",
    se_phys_count_fail: "fallan",
    se_phys_count_skip: "sin evaluar",
    se_phys_suggested_status: "Estado físico de la pose sugerida",
    se_phys_review_note: "La pose sugerida no está confirmada como físicamente válida, y no se sustituye por otra. Elegir «la siguiente que pase» sería una decisión que nadie tomó y para la que el modelo no fue entrenado.",
    se_phys_absent: "Esta corrida no ejecutó los controles físicos.",
    se_phys_review_meaning: "“Requiere revisión” significa que la batería no corrió entera. No es una pose aprobada.",
    se_phys_not_evaluated_meaning: "“No evaluada” describe lo que le pasó al validador, nunca a la molécula.",
    se_phys_per_pose: "Veredicto por pose",
    se_phys_open_in_structure: "Consulta los controles individuales desde Estructura y evidencia.",
    se_phys_reason: "Razón de la abstención",
    se_s4_title: "Decisión justificable",
    se_s4_lead: "Qué se puede sostener con esta evidencia, y qué queda abierto.",
    se_dec_established: "Qué evidencia existe",
    se_dec_uncertainties: "Incertidumbres abiertas",
    se_dec_no_uncertainties: "No quedan incertidumbres más allá de los límites generales del protocolo.",
    se_dec_alternatives: "Alternativas físicamente válidas",
    se_dec_alternatives_note: "Se listan para que puedas compararlas. Ninguna se selecciona automáticamente.",
    se_dec_no_alternatives: "Ninguna otra pose superó los controles físicos.",
    se_dec_next: "Próximo paso recomendado",
    se_dec_next_abstain: "Abstenerse: completar la corrida",
    se_dec_next_abstain_detail: "No priorizar el ligando ni encadenar cálculos posteriores mientras falten poses o haya controles fallidos.",
    se_dec_next_review: "Revisar la geometría antes de continuar",
    se_dec_next_review_detail: "Resolver los controles pendientes antes de MM-GBSA, dinámica molecular o cualquier priorización experimental.",
    se_dec_next_proceed: "Apta para análisis posterior dentro del mismo protocolo",
    se_dec_next_proceed_detail: "La evidencia disponible permite continuar conservando las limitaciones documentadas. No dice que la molécula sea activa.",
    se_ev_poses_generated: "Se generaron poses con su afinidad Vina observada.",
    se_ev_physical_checks_run: "Los controles físicos se ejecutaron sobre las poses de esta corrida.",
    se_ev_selector_ran: "El selector de pose se ejecutó y dejó su veredicto.",
    se_ev_provenance_sealed: "El receptor de la corrida quedó sellado por su hash.",
    se_unc_no_physical_validation: "Ninguna pose recibió veredicto físico.",
    se_unc_partial_coverage: "Sólo una parte de las poses recibió veredicto.",
    se_unc_suggested_pose_not_passed: "La pose sugerida no está confirmada como físicamente válida.",
    se_unc_selector_abstained: "El selector no recomendó ninguna pose.",
    se_unc_selector_unavailable: "El selector no se ejecutó en esta corrida.",
    se_unc_selector_error: "El selector falló, así que no hay recomendación que leer.",
    se_unc_selection_diverges: "La pose sugerida y la top-1 de Vina no son la misma.",
    se_unc_single_pose: "Con una sola pose no hay separación interna que medir.",
    se_unc_near_tie: "Varias poses quedan a 1 kcal/mol o menos; quedarse con una sola es ambiguo.",
    se_unc_incomplete_provenance: "La traza de reproducibilidad está incompleta.",
    se_unc_no_seed: "La corrida no registró la semilla, así que no se puede repetir bit a bit.",
    se_cmp_title: "Comparar poses",
    se_cmp_lead: "Top-1 de Vina, pose sugerida y alternativas, una al lado de otra.",
    se_cmp_rank: "Pose",
    se_cmp_affinity: "Afinidad Vina",
    se_cmp_selector: "Selector",
    se_cmp_physical: "Controles físicos",
    se_cmp_role: "Papel",
    se_cmp_role_top1: "Vina top-1",
    se_cmp_role_suggested: "Sugerida",
    se_cmp_role_alternative: "Alternativa",

    // Moldex / Targets Page
    moldex_title: "Biblioteca de Blancos Moleculares (Moldex)",
    moldex_search: "Buscar blanco...",
    moldex_table_pdb: "ID PDB",
    moldex_table_name: "Nombre del Receptor",
    moldex_table_type: "Tipo",
    moldex_table_resolution: "Resolución",

    // Divulgación de IA generativa. Microsoft la exige para cualquier
    // aplicación que entregue texto generado por un modelo, y pide además una
    // vía para reportar una respuesta dañina o inapropiada.
    //
    // El texto dice tres cosas y ninguna es decorativa: que lo escribe un
    // modelo, que puede equivocarse, y que no es un resultado científico. Esa
    // tercera es la que importa aquí: MolChat habla de moléculas y receptores
    // junto a una pantalla que sí calcula, y confundir las dos superficies es
    // el error caro. No se puede cerrar, a diferencia del aviso del modelo
    // local: una divulgación que se oculta deja de serlo.
    ia_aviso_generativa: "Las respuestas de MolChat las escribe un modelo de lenguaje. Pueden ser incorrectas y no son un resultado científico: los números del expediente salen del cálculo, no de aquí.",
    ia_reportar: "Reportar respuesta",
    ia_reportar_titulo: "Reportar esta respuesta al equipo de MolDesign",
    ia_reportar_aviso: "Abre tu programa de correo con la respuesta y el proveedor ya escritos. No se envía nada hasta que tú lo mandes.",
    ia_reportar_asunto: "Reporte de respuesta de MolChat",
    ia_reportar_cuerpo_cabecera: "Describe qué tiene de incorrecto o de inapropiado esta respuesta:",
    ia_reportar_cuerpo_respuesta: "Respuesta reportada",
    ia_reportar_cuerpo_proveedor: "Proveedor",
    ia_reportar_sin_correo: "No se pudo abrir el programa de correo. Escribe a soporte-moldesign@amezcua-dev.com y adjunta la respuesta.",
  },
  en: {
    ...TRADUCCIONES_POR_SUPERFICIE.en,
    options: "Options",
    batch: "Batch",
    evaluation: "Evaluation",
    moldex: "Moldex",
    support: "Support",
    logout: "Log Out",
    login: "Log In",
    welcome: "Welcome",
    close: "Close",
    save: "Save",
    cancel: "Cancel",
    confirm: "Confirm",
    error: "Error",
    success: "Success",

    hero_tagline: "Local · Public source code",
    hero_title_1: "Prepare",
    hero_title_2: "Evaluate",
    hero_title_3: "Document",
    hero_desc: "A local tool with publicly available source code for preparing structural hypotheses, running initial evaluations, and delivering reproducible computational evidence. It does not discover drugs, predict clinical efficacy, or replace an experiment.",
    evidence_tagline: "AUDITABLE STRUCTURAL EVIDENCE",
    evidence_title_1: "CONFIDENCE",
    evidence_title_2: "PROVENANCE",
    evidence_title_3: "TRANSFER",
    vision_label: "FUTURE DIRECTION",
    vision_title: "The IDE for drug discovery",
    vision_desc: "The vision is to make MolDesign a working environment where every structural decision retains its context, uncertainty, and provenance. Its scope today is narrower: it prepares, evaluates, and documents structural evidence; it does not run FEP or molecular dynamics and does not cover end-to-end drug discovery.",
    hero_button_edu: "Student Mode",
    hero_button_pro: "Advanced Evaluation",
    features_title: "What it does, exactly",
    step_01_title: "Case-based evaluation",
    step_01_desc: "One receptor, one ligand and a declared hypothesis. The preflight says what will enter the run before running it.",
    step_02_title: "Comparable cohorts",
    step_02_desc: "Many molecules under a single receptor and a common configuration, with declared coverage, exceptions and duplicates.",
    step_03_title: "Dossier and reproducible package",
    step_03_desc: "A PDF stating what was computed and what was left unevaluated, plus a ZIP with manifest and hashes a third party can verify without running anything.",
    step_04_title: "Local execution",
    step_04_desc: "The engine runs on this machine. No molecular data leaves it unless you export it.",
    step_05_title: "Declared scientific limits",
    step_05_desc: "Completing a docking run does not demonstrate activity. What was not checked shows as NOT EVALUATED, never as approved.",
    stats_molecules: "Evaluated Molecules",
    stats_best_score: "Best observed affinity (kcal/mol)",
    stats_certified: "Integrity registered",

    opt_appearance: "Appearance",
    opt_theme: "Theme",
    opt_theme_dark: "Dark",
    opt_theme_light: "Light",
    opt_interface: "Interface",
    opt_sounds: "Interface Sounds",
    opt_sounds_muted: "Sounds muted",
    opt_sounds_active: "Sounds active",
    opt_sounds_activate: "Click to activate",
    opt_sounds_silence: "Click to mute",
    opt_ai: "AI Interpreter",
    opt_ai_config: "Configure AI provider",
    opt_ai_chat_open: "Open MolChat",
    opt_ai_chat_close: "Close MolChat",
    opt_data: "Data & Backup",
    opt_data_export: "Export Library (JSON)",
    opt_data_export_desc: "Download all your molecules and results in a portable file",
    opt_data_export_success: "Backup exported successfully",
    opt_data_reset: "Reset session data",
    opt_data_reset_desc: "Closes active local session. Evaluation history remains intact in database.",
    opt_data_reset_warning: "This action will log you out. Your evaluations and molecules will not be deleted.",
    opt_data_reset_success: "Session reset",
    opt_legal: "Legal & Info",
    opt_legal_terms: "Terms & Privacy",
    opt_legal_about: "About",

    legal_title: "Legal Framework — MolDesign",
    legal_tab_terms: "Terms of Use",
    legal_tab_priv: "Privacy",
    legal_tab_lic: "License",
    legal_local_first: "Local-First · No Telemetry · External connections optional",
    legal_understood: "Understood",

    login_title: "Local Login",
    login_subtitle: "MolDesign runs docking and analysis on your device.",
    login_username: "Username",
    login_password: "Password (Min 4 characters)",
    login_btn: "Access Laboratory",
    login_privacy_badge: "Computation runs on your device. External connections are optional.",
    login_error_fields: "Please complete all fields correctly.",
    login_error_auth: "Incorrect credentials.",

    eval_title: "Molecular Evaluation Panel",
    eval_draw_tab: "1. Draw Molecule",
    eval_target_tab: "2. Select Target",
    eval_run_tab: "3. Simulation & Score",
    eval_results_tab: "4. Final Report",
    eval_target_select_title: "Select Docking Target",
    eval_target_desc: "Select which protein receptor to simulate molecular docking against.",
    eval_run_simulation: "Start Scientific Simulation",
    eval_docking_progress: "Simulating molecular docking...",
    eval_docking_success: "Molecular docking completed successfully.",
    eval_docking_fail: "Error during docking simulation.",
    eval_vina_score: "Vina Affinity",
    eval_admet_score: "ADMET Properties",
    eval_solana_status: "Experimental Solana record",
    eval_solana_btn: "Test devnet record",

    // ── Contextual help (the "?") ─────────────────────────────────
    ayuda_ensemble_titulo: "Conformer generation",
    ayuda_ensemble: "Docking starts from one 3D conformation of the ligand. With \"ensemble\", K are generated and each is docked separately; the poses are pooled and re-ranked by affinity. It widens COVERAGE: it raises the chance that some conformation resembles the real one. In our internal measurement it did NOT improve the top-1 pick — the bottleneck moves to selection. It buys breadth of search, not precision, and costs K times the docking time.",

    ayuda_exhaustividad_titulo: "Exhaustiveness and seed",
    ayuda_exhaustividad: "Exhaustiveness is how hard Vina searches inside the box. More search lowers the chance of missing a pose by luck, but it does not fix a badly defined site or a doubtful preparation. The seed pins the randomness: without it the run cannot be repeated bit for bit.",

    ayuda_afinidad_titulo: "Observed Vina affinity",
    ayuda_afinidad: "The value Vina's scoring function assigned to this pose, in kcal/mol. It is NOT a measured binding free energy, and it does not convert into Ki or IC50. It orders poses within this same run; comparing across receptors or protocols is not justified.",

    ayuda_margen_titulo: "Selector margin",
    ayuda_margen: "The distance between the first and second pose according to the selection model. It is NOT a probability or a grade: a wide margin says the model separated them clearly, not that it was right. Below the threshold the selector abstains, and the reference goes back to Vina top-1.",

    ayuda_estados_titulo: "Review vs. not evaluated",
    ayuda_estados: "\"Checks passed\" is the only thing that licenses calling a pose valid. \"Needs review\" means the battery did not run in full — not that the pose is good. \"Not evaluated\" describes what happened to the VALIDATOR, never to the molecule: neither is negative evidence about the compound.",

    ayuda_cobertura_titulo: "Evaluated coverage",
    ayuda_cobertura: "How many poses received a physical verdict, out of how many the run produced. The denominator matters: \"all passed\" over 2 of 9 poses says nothing about the other 7. That is why both figures are shown and never a bare percentage.",

    ayuda_checksums_titulo: "Package checksums",
    ayuda_checksums: "They prove INTEGRITY: that the bytes have not changed since the package was generated. They do not prove the method was adequate, the preparation correct, or the conclusion true. A package being \"valid\" is a claim about the files, not about the science.",

    // ── Structural evidence (P0-C) ────────────────────────────────
    // Kept in lockstep with the Spanish block on purpose: a test asserts
    // that no `se_` key exists in only one language.
    se_title: "Structural evidence",
    se_subtitle: "How the poses were generated, which one is suggested, and which physical checks it passed.",
    se_disclaimer: "Describes what this run measured. It claims no biological activity, potency or pharmacological success.",
    se_legacy: "Run predates these stages",
    se_legacy_note: "This evaluation ran before physical validation and the pose selector existed. They did not fail: they never ran.",
    se_empty: "This run left no poses or contracts to show.",
    se_loading: "Loading structural evidence…",
    se_error: "The structural evidence for this run could not be read.",
    se_show_detail: "Show detail",
    se_hide_detail: "Hide detail",
    se_not_reported: "Not reported",
    se_technical: "Technical details",
    se_s1_title: "Generation",
    se_s1_lead: "What the docking produced, and under which protocol.",
    se_gen_poses: "Poses produced",
    se_gen_affinity: "Best observed Vina affinity",
    se_gen_affinity_note: "This is what Vina observed, not an experimental free-energy measurement.",
    se_gen_gap: "Δ pose 1–2",
    se_gen_protocol: "Protocol",
    se_gen_seed: "Random seed",
    se_gen_parser: "Pose parsing",
    se_gen_conformers: "Conformers / restarts",
    se_gen_conformers_absent: "Not recorded by this run",
    se_gen_conformers_note: "The result does not persist these parameters. They are not filled in from the case configuration: that would attribute to this run a setting nobody saved with it.",
    se_gen_receptor: "Prepared receptor",
    se_gen_receptor_absent: "No receptor fingerprint",
    se_gen_provenance: "Reproducibility traces",
    se_gen_no_poses: "The docking kept no poses.",
    se_s2_title: "Selection",
    se_s2_lead: "The selector recommends; it does not replace. The primary pose is still Vina's.",
    se_sel_selected: "The selector recommends a pose",
    se_sel_abstained: "The selector abstained",
    se_sel_unavailable: "Selector unavailable",
    se_sel_error: "The selector failed",
    se_sel_vina_top1: "Vina top-1 (original)",
    se_sel_suggested: "Suggested pose",
    se_sel_would_have: "Would have suggested",
    se_sel_no_recommendation: "No recommendation",
    se_sel_confidence: "Confidence margin",
    se_sel_threshold: "threshold",
    se_sel_confidence_note: "The distance between the first and second pose according to the selector. It is not a probability or a grade.",
    se_sel_model: "Model",
    se_sel_fallback: "Reference: Vina top-1 (fallback)",
    se_sel_fallback_note: "Not a selector success: it is what remains when there is no recommendation.",
    se_sel_diverge: "The suggested pose is NOT Vina's top-1",
    se_sel_diverge_note: "Both are kept and both are shown. The product's primary pose is still Vina's; the suggested one is a recommendation you can compare.",
    se_sel_agree: "The suggested pose matches Vina's top-1",
    se_sel_abstain_reason: "Reason",
    se_sel_scores: "Selector score per pose",
    se_sel_warnings: "Selector warnings",
    se_reason_MODELO_AUSENTE: "The selector model is not present on this machine.",
    se_reason_SIN_POSES: "The run kept no poses.",
    se_reason_SIN_PDBQT_DE_POSE: "Some pose did not keep its coordinates, and the selector needs all of them to compare.",
    se_reason_RECEPTOR_NO_DISPONIBLE: "The exact receptor of this run could not be used, and the selector will not opine on a different one.",
    se_reason_SELECTOR_FALLO: "The selector could not evaluate these poses.",
    se_reason_MARGEN_BAJO_UMBRAL: "The margin between the first and second pose does not reach the abstention threshold.",
    se_reason_UNA_SOLA_POSE: "A single pose: there is no margin to measure.",
    se_reason_SELECCION_AUSENTE: "This evaluation predates the pose selection stage.",
    se_reason_RECEPTOR_AUSENTE: "The prepared receptor for this run is not available.",
    se_reason_RECEPTOR_NO_COINCIDE: "The catalogue receptor is no longer the one that was docked; validating against another would judge a different system.",
    se_reason_RECEPTOR_SIN_HUELLA: "The run did not record the receptor hash, so there is no proof of which one was used.",
    se_reason_SIN_PLANTILLA: "No chemical template is declared to rebuild the pose; the graph is never guessed.",
    se_reason_MAPA_SIN_HIDROGENOS_POLARES: "The atom map does not cover the polar hydrogens of the pose.",
    se_reason_VALIDADOR_NO_DISPONIBLE: "The physical validator is not available on this machine.",
    se_reason_EVIDENCIA_AUSENTE: "This evaluation predates the physical validation stage.",

    // PoseBusters column names, spelled out. English readers get the same
    // treatment as Spanish ones: a sentence, not an identifier.
    se_check_mol_pred_loaded: "Pose loaded",
    se_check_mol_true_loaded: "Reference loaded",
    se_check_mol_cond_loaded: "Receptor loaded",
    se_check_sanitization: "Chemical sanitization (RDKit)",
    se_check_inchi_convertible: "InChI convertible",
    se_check_all_atoms_connected: "All atoms connected",
    se_check_no_radicals: "No free radicals",
    se_check_bond_lengths: "Bond lengths",
    se_check_bond_angles: "Bond angles",
    se_check_internal_steric_clash: "Internal steric clash",
    se_check_aromatic_ring_flatness: "Aromatic ring flatness",
    "se_check_non-aromatic_ring_non-flatness": "Non-aromatic ring non-flatness",
    se_check_double_bond_flatness: "Double bond flatness",
    se_check_internal_energy: "Conformer internal energy",
    "se_check_protein-ligand_maximum_distance": "Maximum distance to the receptor",
    se_check_minimum_distance_to_protein: "Minimum distance to protein",
    se_check_minimum_distance_to_organic_cofactors: "Minimum distance to organic cofactors",
    se_check_minimum_distance_to_inorganic_cofactors: "Minimum distance to inorganic cofactors",
    se_check_minimum_distance_to_waters: "Minimum distance to waters",
    se_check_volume_overlap_with_protein: "Volume overlap with protein",
    se_check_volume_overlap_with_organic_cofactors: "Volume overlap with organic cofactors",
    se_check_volume_overlap_with_inorganic_cofactors: "Volume overlap with inorganic cofactors",
    se_check_volume_overlap_with_waters: "Volume overlap with waters",
    se_s3_title: "Physical checks",
    se_s3_lead: "What the validator checked on each pose, and what it could not check.",
    se_phys_passed: "Checks passed",
    se_phys_failed: "Checks failed",
    se_phys_review: "Needs review",
    se_phys_not_evaluated: "Not evaluated",
    se_phys_coverage: "Evaluated coverage",
    se_phys_poses_unit: "poses",
    se_phys_engine: "Validation engine",
    se_phys_failing: "Failing checks",
    se_phys_none_failing: "No chemistry or geometry check fails.",
    se_phys_counts: "Breakdown",
    se_phys_count_pass: "pass",
    se_phys_count_fail: "fail",
    se_phys_count_skip: "not evaluated",
    se_phys_suggested_status: "Physical status of the suggested pose",
    se_phys_review_note: "The suggested pose is not confirmed physically valid, and it is not swapped for another. Picking “the next one that passes” would be a decision nobody made and one the model was not trained for.",
    se_phys_absent: "This run did not execute the physical checks.",
    se_phys_review_meaning: "“Needs review” means the battery did not run in full. It is not an approved pose.",
    se_phys_not_evaluated_meaning: "“Not evaluated” describes what happened to the validator, never to the molecule.",
    se_phys_per_pose: "Verdict per pose",
    se_phys_open_in_structure: "See individual checks in Structure and evidence.",
    se_phys_reason: "Abstention reason",
    se_s4_title: "Justifiable decision",
    se_s4_lead: "What this evidence supports, and what remains open.",
    se_dec_established: "What evidence exists",
    se_dec_uncertainties: "Open uncertainties",
    se_dec_no_uncertainties: "No uncertainties remain beyond the protocol's general limits.",
    se_dec_alternatives: "Physically valid alternatives",
    se_dec_alternatives_note: "Listed so you can compare them. None is selected automatically.",
    se_dec_no_alternatives: "No other pose passed the physical checks.",
    se_dec_next: "Recommended next step",
    se_dec_next_abstain: "Abstain: complete the run",
    se_dec_next_abstain_detail: "Do not prioritise the ligand or chain further calculations while poses are missing or checks are failing.",
    se_dec_next_review: "Review the geometry before continuing",
    se_dec_next_review_detail: "Resolve the pending checks before MM-GBSA, molecular dynamics or any experimental prioritisation.",
    se_dec_next_proceed: "Suitable for further analysis within the same protocol",
    se_dec_next_proceed_detail: "The available evidence supports continuing while keeping the documented limitations. It does not say the molecule is active.",
    se_ev_poses_generated: "Poses were generated with their observed Vina affinity.",
    se_ev_physical_checks_run: "Physical checks ran on this run's poses.",
    se_ev_selector_ran: "The pose selector ran and left its verdict.",
    se_ev_provenance_sealed: "The run's receptor is sealed by its hash.",
    se_unc_no_physical_validation: "No pose received a physical verdict.",
    se_unc_partial_coverage: "Only some of the poses received a verdict.",
    se_unc_suggested_pose_not_passed: "The suggested pose is not confirmed physically valid.",
    se_unc_selector_abstained: "The selector recommended no pose.",
    se_unc_selector_unavailable: "The selector did not run for this evaluation.",
    se_unc_selector_error: "The selector failed, so there is no recommendation to read.",
    se_unc_selection_diverges: "The suggested pose and Vina's top-1 are not the same.",
    se_unc_single_pose: "With a single pose there is no internal separation to measure.",
    se_unc_near_tie: "Several poses lie within 1 kcal/mol; keeping only one is ambiguous.",
    se_unc_incomplete_provenance: "The reproducibility trace is incomplete.",
    se_unc_no_seed: "The run did not record the seed, so it cannot be repeated bit for bit.",
    se_cmp_title: "Compare poses",
    se_cmp_lead: "Vina top-1, the suggested pose and the alternatives, side by side.",
    se_cmp_rank: "Pose",
    se_cmp_affinity: "Vina affinity",
    se_cmp_selector: "Selector",
    se_cmp_physical: "Physical checks",
    se_cmp_role: "Role",
    se_cmp_role_top1: "Vina top-1",
    se_cmp_role_suggested: "Suggested",
    se_cmp_role_alternative: "Alternative",

    moldex_title: "Molecular Targets Library (Moldex)",
    moldex_search: "Search target...",
    moldex_table_pdb: "PDB ID",
    moldex_table_name: "Receptor Name",
    moldex_table_type: "Type",
    moldex_table_resolution: "Resolution",

    ia_aviso_generativa: "MolChat's answers are written by a language model. They can be wrong and they are not a scientific result: the numbers in the case file come from the computation, not from here.",
    ia_reportar: "Report answer",
    ia_reportar_titulo: "Report this answer to the MolDesign team",
    ia_reportar_aviso: "Opens your mail client with the answer and the provider already filled in. Nothing is sent until you send it.",
    ia_reportar_asunto: "MolChat answer report",
    ia_reportar_cuerpo_cabecera: "Describe what is wrong or inappropriate about this answer:",
    ia_reportar_cuerpo_respuesta: "Reported answer",
    ia_reportar_cuerpo_proveedor: "Provider",
    ia_reportar_sin_correo: "Could not open your mail client. Write to soporte-moldesign@amezcua-dev.com and attach the answer.",
  },
};

/**
 * Valores que se interpolan en una traduccion.
 *
 * POR QUE HACEN FALTA. Media interfaz dice cosas como «3 de 12 receptores» o
 * «se hace una sola vez». Sin interpolacion hay dos salidas y las dos son
 * malas: partir la frase en tres claves —que en ingles se ordenan distinto— o
 * concatenar en el componente, que es como se cuelan las cadenas sin traducir.
 */
export type ValoresDeTraduccion = Readonly<Record<string, string | number>>;

interface LanguageContextProps {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, valores?: ValoresDeTraduccion) => string;
  currentLanguage: Language;
}

/**
 * Sustituye `{nombre}` por su valor.
 *
 * Un marcador sin valor SE DEJA COMO ESTA en vez de vaciarse: «quedan {n}
 * dias» es un error visible que alguien arregla, y «quedan  dias» es un error
 * que pasa inadvertido hasta que lo ve un usuario.
 */
export function interpolar(plantilla: string, valores?: ValoresDeTraduccion): string {
  if (!valores) return plantilla;
  return plantilla.replace(/\{(\w+)\}/g, (completo, nombre: string) =>
    nombre in valores ? String(valores[nombre]) : completo,
  );
}

const LanguageContext = createContext<LanguageContextProps | undefined>(undefined);

export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const { isLoading: authLoading, user } = useAuth();
  const [locale, setLocaleState] = useState<Locale>("es");
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    if (authLoading) return;
    try {
      const saved = getUserItem("moldesign_locale", user?.user_id) as Locale | null;
      if (saved && MVP_LOCALES.has(saved) && TRANSLATIONS[saved]) {
        setLocaleState(saved);
      } else {
        const navLang = navigator.language.split("-")[0] as Locale;
        if (MVP_LOCALES.has(navLang) && TRANSLATIONS[navLang]) {
          setLocaleState(navLang);
        }
      }
    } catch {}
    setHydrated(true);
  }, [authLoading, user?.user_id]);

  const setLocale = (l: Locale) => {
    if (!MVP_LOCALES.has(l) || !TRANSLATIONS[l]) return;
    setLocaleState(l);
    try {
      if (user) setUserItem("moldesign_locale", l, user.user_id);
    } catch {}
  };

  const t = (key: string, valores?: ValoresDeTraduccion): string => {
    const dict = TRANSLATIONS[locale] || TRANSLATIONS.es;
    return interpolar(dict[key] || TRANSLATIONS.es[key] || key, valores);
  };

  useEffect(() => {
    const originalFetch = window.fetch;
    document.documentElement.lang = locale;
    document.title = TRANSLATIONS[locale].z_document_title;
    const localizedFetch: typeof window.fetch = (input, init) => {
      const headers = new Headers(input instanceof Request ? input.headers : undefined);
      new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
      headers.set("Accept-Language", locale);
      return originalFetch(input, { ...init, headers });
    };
    window.fetch = localizedFetch;
    return () => {
      if (window.fetch === localizedFetch) window.fetch = originalFetch;
    };
  }, [locale]);

  const currentLanguage = LANGUAGES.find((lang) => lang.code === locale) || LANGUAGES[0];

  if (!hydrated) {
    return (
      <LanguageContext.Provider value={{ locale: "es", setLocale: () => {}, t: (k, v) => interpolar(TRANSLATIONS.es[k] || k, v), currentLanguage: LANGUAGES[0] }}>
        {children}
      </LanguageContext.Provider>
    );
  }

  return (
    <LanguageContext.Provider value={{ locale, setLocale, t, currentLanguage }}>
      {children}
    </LanguageContext.Provider>
  );
}

/**
 * Traducciones, sin tumbar el subárbol cuando falta el provider.
 *
 * ANTES LANZABA. Un componente que sólo quería dos etiquetas derribaba todo lo
 * que colgara de él si alguien lo montaba fuera del provider — que es
 * exactamente la clase de fallo que deja la ventana en blanco. Un texto que no
 * se puede traducir es un problema de idioma, no de disponibilidad: se degrada
 * al castellano, que es el idioma base del diccionario, y se avisa una vez en
 * consola para que el montaje mal hecho no pase inadvertido.
 */
export function useLanguage(): LanguageContextProps {
  const ctx = useContext(LanguageContext);
  if (ctx) return ctx;

  if (typeof console !== "undefined" && !avisoDeProviderEmitido) {
    avisoDeProviderEmitido = true;
    console.warn(
      "[LanguageContext] useLanguage fuera de LanguageProvider: se usa el " +
        "diccionario en castellano. Revisa dónde se monta este componente.",
    );
  }
  return RESPALDO_SIN_PROVIDER;
}

let avisoDeProviderEmitido = false;

const RESPALDO_SIN_PROVIDER: LanguageContextProps = {
  locale: "es",
  setLocale: () => {},
  t: (key: string, valores?: ValoresDeTraduccion) =>
    interpolar(TRANSLATIONS.es[key] ?? key, valores),
  currentLanguage: LANGUAGES[0],
};
/**
 * Texto traducido para auxiliares JSX creados fuera del cuerpo del componente
 * (por ejemplo, el fallback de una importaci?n din?mica). Mantiene el idioma
 * reactivo sin invocar hooks en el nivel superior del m?dulo.
 */
export function Translated({
  id,
  values,
}: Readonly<{ id: string; values?: ValoresDeTraduccion }>) {
  const { t } = useLanguage();
  return <>{t(id, values)}</>;
}
