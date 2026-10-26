// =====================================================================
// Pro — pestañas de análisis, receptor propio, preparación y registro
// =====================================================================
//
// EL PATRÓN QUE SE REPITE EN TODO ESTE MÓDULO: casi cada texto largo existe para
// acotar lo que el número NO dice. Se traducen conservando la negación entera,
// porque es lo único que impide que una señal de docking se lea como una
// medición:
//
//   · «no convierten una afinidad de docking en actividad, eficacia o
//     selectividad experimental»
//   · «No es comparable entre moléculas distintas ni con un ΔG experimental»
//   · «Son predicciones de un modelo, no mediciones: se citan como tales»
//   · «esto no constituye una conclusión de seguridad»
//   · «Esa concentración no es una Ki ni una IC50»
//
// En inglés, «it is not comparable» y «this does not constitute» — nunca «may
// not be comparable» ni «should not be taken as». El producto no sugiere: dice.
//
// SHAP, GNN, SAR, ADMET, MM-GBSA, PDBQT, Meeko, exhaustiveness y los nombres de
// campos de fuerza se quedan igual: son nomenclatura, no prosa.

import type { ModuloDeTraduccion } from "./index";

export const pro: ModuloDeTraduccion = {
  es: {
    pr_pipeline_sub_this_run: "de esta corrida",
    // ── Preparación previa de la corrida ──────────────────────────
    pr_preflight_state_blocking: "Bloquea",
    pr_preflight_state_warning: "Advertencia",
    pr_preflight_state_not_evaluated: "No evaluado",
    pr_preflight_state_pass: "Pasa",
    pr_preflight_method_qvina: "Acoplamiento molecular con QuickVina 2",
    pr_preflight_method_vina: "Acoplamiento molecular con AutoDock Vina",
    pr_preflight_method_vina_compatible: "Ruta de acoplamiento compatible con Vina",
    pr_preflight_method_configured: "Ruta de acoplamiento configurada",
    pr_preflight_ensemble: "Ensemble de confórmeros",
    pr_comprobacion_automatica:
      "Al ejecutar, se comprobarán el ligando, el receptor y la configuración.",
    pr_comprobacion_pendiente: "Pendiente",
    pr_conformeros_resumen_uno: "1 confórmero inicial",
    pr_conformeros_resumen_varios: "{cantidad} confórmeros iniciales",
    pr_preflight_receptor: "Receptor",
    pr_preflight_ligand: "Ligando",
    pr_preflight_effective_box: "Caja de búsqueda efectiva",
    pr_preflight_blocker_one: "bloqueante",
    pr_preflight_blocker_many: "bloqueantes",
    pr_preflight_warning_one: "advertencia",
    pr_preflight_warning_many: "advertencias",
    pr_preflight_fingerprint: "huella",
    pr_preflight_species: "Especie",
    pr_preflight_source: "Fuente",
    pr_preflight_after_filtering: "Tras filtrar",
    pr_preflight_removed: "Retirado",
    pr_preflight_waters: "Aguas",
    pr_preflight_metals: "Metales",
    pr_preflight_not_evaluated: "No evaluado.",
    pr_preflight_controls: "Controles",
    pr_preflight_species_water: "agua",
    pr_preflight_species_metal: "metal",
    pr_preflight_species_organic_cofactor: "cofactor orgánico",
    pr_preflight_species_other_component: "otro componente de la estructura",
    pr_preflight_declared_cofactors: "Se conservan únicamente los cofactores declarados: {cofactors}",
    pr_stage_required: "Obligatorio",
    pr_stage_move_up: "Mover arriba",
    pr_stage_move_down: "Mover abajo",
    pr_stage_running: "EN CURSO",
    pr_stage_done: "LISTO",
    pr_stage_failed: "FALLO",

    // ── Configuración avanzada y motores ──────────────────────────
    pr_cfg_activos: "activos",
    pr_cfg_ad: "AD",
    pr_cfg_abrir_gestor: "Abrir gestor",
    pr_cfg_centro: "CENTRO",
    pr_cfg_cpu_only: "Solo CPU",
    pr_cfg_cuda: "CUDA",
    pr_cfg_docks_paralelos: "Acoplamientos paralelos",
    pr_cfg_encender: "Encender",
    pr_cfg_estimado: "estimado",
    pr_cfg_experimental: "Experimental",
    pr_cfg_num_modes: "Número de modos",
    pr_cfg_opencl: "OpenCL",
    pr_cfg_openmm_refinement: "Plegamiento + refinamiento con OpenMM.",
    pr_cfg_pasos_mmgbsa: "Pasos MM-GBSA",
    pr_cfg_perfil_admet: "Perfil ADMET",
    pr_cfg_plegado: "PLEGADO",
    pr_cfg_preciso: "PRECISO",
    pr_cfg_predictivo: "PREDICTIVO",
    pr_cfg_procesos: "Procesos",
    pr_cfg_pose: "pose",
    pr_cfg_poses: "poses",
    pr_cfg_quickvina: "QuickVina 2",
    pr_cfg_selectividad_antitarget: "Selectividad anti-diana",
    pr_cfg_tuyo: "Tuyo",
    pr_cfg_volver_ph: "Volver a 7.4",
    pr_cfg_workers: "Trabajadores",
    pr_engine_vina_fp64: "AutoDock Vina (FP64)",
    pr_engine_diffdock_fp32: "DiffDock (FP32)",
    pr_engine_fp16: "FP16",
    pr_engine_fp32: "FP32",
    pr_engine_quickvina_fp64: "QuickVina 2 (FP64)",
    pr_engine_auto_detect: "detección automática",
    pr_engine_folding_refinement: "Plegamiento completo + refinamiento con OpenMM.",
    pr_engine_requires_gpu: "Requiere GPU",

    pr_tab_structure_evidence: "Estructura y evidencia",
    pr_tab_properties: "Propiedades",
    pr_tab_explainability: "Explicabilidad",
    pr_analysis_alerts_reservations: "Alertas y reservas",
    pr_admet_available: "ADMET disponible",
    pr_admet_calculate: "Calcular ADMET",
    pr_sar_evidence_available: "Evidencia SAR disponible",
    pr_pose_a: "Pose A",
    pr_pose_b: "Pose B",
    pr_pose_label: "Pose",
    pr_selector_label: "Selector",
    pr_pose_comparison_3d: "Comparar poses en 3D",
    pr_pose_coordinates_recorded: "coordenadas registradas",

    // ── Parámetros y nomenclatura química ─────────────────────────
    pr_param_admet_no_disponible: "ADMET-AI no disponible",
    pr_param_admet_ai: "ADMET-AI",
    pr_param_cns_mpo: "CNS MPO",
    pr_param_coincidencias: "coincidencias",
    pr_param_filtro_egan: "Egan",
    pr_param_filtro_ghose: "Ghose",
    pr_param_filtro_lipinski: "Lipinski",
    pr_param_filtro_muegge: "Muegge",
    pr_param_filtro_veber: "Veber",
    pr_param_hbd_hba: "HBD / HBA",
    pr_param_hia: "HIA",
    pr_param_le: "LE",
    pr_param_lle: "LLE",
    pr_param_logp: "LogP",
    pr_param_ml_stacking: "Apilamiento de modelos (ML)",
    pr_param_modelo_universal: "Universal",
    pr_param_modelo_usado: "Modelo usado",
    pr_param_mw: "MW",
    pr_param_no: "no",
    pr_param_pains: "PAINS",
    pr_param_permeable: "✓ Permeable",
    pr_param_ppb: "PPB",
    pr_param_rings: "Anillos",
    pr_param_rotatable_bonds: "Enlaces rotables",
    pr_param_solubilidad: "Solubilidad",
    pr_param_tpsa: "TPSA",

    // ── Pestañas de análisis ──────────────────────────────────────
    pr_analisis_corrida: "Análisis de la corrida",
    pr_areas_analisis: "Áreas de análisis",
    pr_metodos_avanzados: "Métodos de análisis avanzado",
    pr_elegir_poses: "Elegir poses para comparar",
    pr_comparar_explicacion:
      "Elige cualquier par de poses generado por esta corrida. La comparación "
      + "conserva afinidad, señal del selector y estado físico; no convierte esos "
      + "datos en una única calificación.",
    pr_sin_poses: "No hay poses serializadas que comparar todavía.",
    pr_abrir_comparacion: "Abrir comparación 3D",
    pr_minimo_dos_poses:
      "Se necesitan al menos dos poses para abrir una comparación.",
    pr_resumen_poses: "Resumen comparable de todas las poses generadas",
    pr_controles_fisicos: "Controles físicos",
    pr_post_docking: "Análisis post-docking",
    pr_post_docking_limite:
      "Estas acciones amplían la evidencia de la corrida; no convierten una "
      + "afinidad de docking en actividad, eficacia o selectividad experimental.",
    pr_refinar_mmgbsa: "MM-GBSA no disponible",
    pr_mmgbsa_retirado: "La parametrización legacy no supera la guardia de integridad. Los valores históricos sin versión de motor están invalidados.",
    pr_mmgbsa_indisponible: "No disponible",
    pr_mmgbsa_control_retirado: "MM-GBSA no disponible: parametrización legacy inconsistente.",
    pr_ordenar_poses: "ordenar poses de esta misma molécula",
    pr_mmgbsa_no_comparable:
      "No es comparable entre moléculas distintas ni con un ΔG experimental: el "
      + "ligando se parametriza con tipos de átomo de proteína (AMBER14), no con "
      + "un campo de fuerzas de molécula pequeña. Requiere C, H, O, N, S o P — "
      + "con halógenos el cálculo no puede ejecutarse.",
    pr_calcular_admet: "Calcular el perfil ADMET",
    pr_admet_predice:
      "Predice solubilidad, absorción intestinal, permeabilidad BBB y unión a "
      + "proteínas plasmáticas con ADMET-AI, en esta máquina. Depende",
    pr_solo_smiles: "sólo del SMILES",
    pr_admet_no_repite:
      ": no usa la pose ni el receptor, así que no hace falta repetir el "
      + "acoplamiento.",
    pr_admet_predicciones:
      "Son predicciones de un modelo, no mediciones: se citan como tales. La "
      + "primera ejecución carga el ensamble y puede tardar —especialmente en una "
      + "máquina virtual o sin GPU—.",
    pr_viaja_en_dossier: "y viaja en el dossier.",
    pr_sar_explicacion:
      "Consulta análogos que ya existen en el historial. Esta versión no genera "
      + "actividad ni inventa una serie SAR cuando no hay mediciones comparables.",

    // ── Receptor propio ───────────────────────────────────────────
    pr_receptor_intro:
      "Integra tus propias proteínas a la base de datos privada de MolDesign.",
    pr_modo_automatico: "Modo automático (.PDB)",
    pr_sube_archivo: "Sube un archivo",
    pr_por_ejemplo_rcsb: "(por ejemplo, extraído del RCSB PDB).",
    pr_pipeline_filtrara:
      "El pipeline filtrará la cadena y el agua, y generará el PDBQT con Meeko.",
    pr_se_autodescubrira: "Se autodescubrirá el",
    pr_basado_cocristal: "basado en el ligando cocristalizado.",
    pr_ya_preparado: "ya preparado en tu entorno de trabajo.",
    pr_no_modificaremos:
      "No modificaremos la estructura, se inyectará directamente al motor Vina.",
    pr_indicar_coordenadas:
      "indicar las coordenadas (X, Y, Z) del centro de la caja.",
    pr_nombre_receptor: "Nombre del receptor",
    pr_tamano_caja: "Tamaño de la caja (grid size)",
    pr_automatizacion: "Automatización inteligente",
    pr_servidor_rastreara:
      "El servidor rastreará la estructura PDB y computará un centro espacial en "
      + "el ligando cocristalizado principal.",
    pr_compartir_comunidad: "Compartir con la comunidad",
    pr_cerrar_subida: "Cerrar subida de receptor",
    // ── Subida de un receptor propio: tres caminos ──
    pr_rp_camino_titulo:
      "¿Qué vas a subir?",
    pr_rp_a_titulo:
      "Estructura cruda",
    pr_rp_a_desc:
      "Experimental o predicha. MolDesign la prepara, retira lo que no sirve y audita lo que cambió.",
    pr_rp_a_punto1:
      "Cadenas, huecos, aguas, metales y cofactores se resuelven o quedan declarados en Preparación.",
    pr_rp_a_punto2:
      "Si es una predicción (AlphaFold DB), se lee la confianza (pLDDT) del sitio y Preparación pide revisión donde es baja.",
    pr_rp_a_punto3:
      "Si el archivo no trae el ligando del cristal, indica el centro de la caja de búsqueda.",
    pr_rp_b_titulo:
      "Ya preparada por tu equipo",
    pr_rp_b_desc:
      "MolDesign respeta tu protonación, aguas, metales y cofactores; no vuelve a protonar.",
    pr_rp_b_punto1:
      "La protonación queda declarada por ti: se comprueba que Meeko aplicó las plantillas que nombra tu archivo (HID, HIE, HIP, CYX…), no que sean correctas.",
    pr_rp_b_punto2:
      "Una especie que no se puede representar para Vina se rechaza con el motivo; no se retira en silencio.",
    pr_rp_b_punto3:
      "Un PQR de PDB2PQR se lee; Vina no usa sus cargas y así se declara.",
    pr_rp_c_titulo:
      "PDBQT listo para Vina",
    pr_rp_c_desc:
      "Se evalúa tal cual, sin pasar por Meeko ni volver a protonar.",
    pr_rp_c_punto1:
      "Un PDBQT no dice dónde está el sitio: indica el centro de la caja de búsqueda.",
    pr_rp_c_punto2:
      "Sin la estructura de origen, Preparación no puede auditar qué se retiró y lo declara; con ella compara el origen con el PDBQT.",
    pr_rp_archivo:
      "Archivo del receptor",
    pr_rp_elegir_archivo:
      "Elegir archivo",
    pr_rp_sin_archivo:
      "Ningún archivo elegido",
    pr_rp_extensiones:
      "Admitidos: {ext}",
    pr_rp_tambien_gz:
      "también comprimidos con .gz",
    pr_rp_origen:
      "Estructura de origen (opcional)",
    pr_rp_origen_nota:
      "La estructura de la que salió el PDBQT. MolDesign comprueba que es el mismo receptor y audita lo que se retiró al prepararlo.",
    pr_rp_origen_quitar:
      "Quitar",
    pr_rp_extension_invalida:
      "«{name}» no tiene una extensión admitida en este camino ({ext}). Elige otro archivo o cambia de camino.",
    pr_rp_falta_archivo:
      "Elige el archivo del receptor.",
    pr_rp_caja_opcional:
      "Caja de búsqueda (opcional)",
    pr_rp_caja_obligatoria:
      "Caja de búsqueda (obligatoria)",
    pr_rp_caja_incompleta:
      "Indica las tres coordenadas del centro (X, Y, Z) o ninguna.",
    pr_rp_caja_obligatoria_falta:
      "Un PDBQT no dice dónde está el sitio: indica las coordenadas (X, Y, Z) del centro de la caja.",
    pr_rp_cadena_otra:
      "Otra cadena",
    pr_rp_cadena_nota:
      "Escribe la cadena tal como está en el archivo (un mmCIF puede llamarlas, por ejemplo, «AAA»).",
    pr_custom_receptor_title: "Subir receptor personalizado",
    pr_custom_manual_mode: "Modo manual (.PDBQT)",
    pr_custom_active_site: "sitio activo",
    pr_custom_required: "obligatorio",
    pr_custom_name_placeholder: "Ej. mi quinasa mutante",
    pr_custom_chain_to_evaluate: "Cadena a evaluar",
    pr_custom_cofactors_optional: "Cofactores a mantener (opcional)",
    pr_custom_grid_center: "Coordenadas del centro (caja de búsqueda)",
    pr_custom_grid_size_x: "Tamaño X",
    pr_custom_grid_size_y: "Tamaño Y",
    pr_custom_grid_size_z: "Tamaño Z",
    pr_custom_processing: "Procesando…",
    pr_custom_select_file: "Seleccionar archivo",
    pr_custom_process_file: "Procesar: {name}…",
    pr_viewer_switch: "Cambiar visor",
    pr_viewer_switch_to: "Cambiar al visor {viewer}",
    pr_viewer_switch_label: "Ver {viewer}",
    pr_viewer_waiting_coordinates: "Esperando coordenadas estructurales…",
    pr_viewer_grid_box: "Caja de búsqueda",
    pr_contact_label: "Contacto",
    pr_viewer_omitted: "Omitido",

    // ── Preparación de la corrida ─────────────────────────────────
    pr_preparacion_titulo: "Comprobación previa",
    pr_preparacion_explicacion:
      "Comprobación previa sobre los archivos reales. No ejecuta el acoplamiento "
      + "y no emite ningún veredicto sobre la molécula. Si detecta un bloqueante técnico, "
      + "la corrida no se ejecuta y aquí se muestra el motivo.",
    pr_revisada_aceptada: "Revisada y aceptada por ti",
    pr_marcar_revisada: "Marcar como revisada",
    pr_conformero_unico: "Confórmero único",
    pr_inputs_cambiaron:
      "Los inputs cambiaron desde la última comprobación, así que ya no describe "
      + "lo que se ejecutaría. Se repite sola al pulsar «Ejecutar evaluación».",
    pr_resumen_guardado:
      "Resumen guardado con el caso. El detalle de controles y el diff se calculan "
      + "de nuevo cuando cambia algo de la corrida.",
    pr_ligando_canonico: "Ligando (canónico)",
    pr_de_la_fuente: "De la fuente a la entrada del preparador",
    pr_especies_retiradas: "Especies químicas identificadas como retiradas",
    pr_codigos_residuo:
      "Los códigos corresponden a los nombres de residuo del archivo PDB; el "
      + "conteo indica registros atómicos retirados.",
    pr_politica_preparacion: "Política de preparación de esta ruta",
    pr_metodo: "Método:",
    pr_aguas_eliminadas: "Se eliminan todas antes del acoplamiento",
    pr_cofactores_reconocidos: "Cofactores orgánicos reconocidos:",
    pr_num_conformaciones: "Número de conformaciones del ensemble",

    // ── Registro científico ───────────────────────────────────────
    pr_reg_cargando_paper: "Cargando el paper…",
    pr_reg_cargando: "Cargando el registro…",
    pr_reg_no_cargado: "No se pudo cargar el registro científico.",
    pr_reg_sin_paper:
      "El paper de este registro todavía no está redactado. Abajo está la ficha "
      + "completa, generada del manifest sellado — que es la fuente de verdad de "
      + "todos los números de esta página.",
    pr_reg_hipotesis: "Hipótesis.",
    pr_reg_razon_decision: "Razón de la decisión",
    pr_reg_lo_que_se_sostuvo: "Lo que se sostuvo, y lo que se cayó",
    pr_reg_preregistro:
      "Cada experimento de MolDesign se registró antes de ejecutarse, con su "
      + "hipótesis y su criterio de decisión escritos por adelantado, y se selló "
      + "con el commit, la semilla, el entorno y los hashes de todo lo que tocó. "
      + "Esta página los abre todos: los que funcionaron y los que no.",
    pr_reg_defecto_detectado: "Un defecto detectado",
    pr_reg_despues: "después",
    pr_reg_hipotesis_derribadas: "hipótesis derribadas",
    pr_reg_otras_poblaciones: "Las otras poblaciones del registro",
    pr_reg_ni_exitos_ni_fracasos:
      "Estas no son ni éxitos ni fracasos, y por eso no entran en el marcador. "
      + "Están aquí porque son la mitad del trabajo.",
    pr_reg_activa_capa: "Activa una capa para ver esos registros.",
    pr_reg_generado_desde: "Generado desde los manifests sellados por",

    // ── Selectividad ──────────────────────────────────────────────
    pr_sel_sin_guardar: "Resultado sin guardar.",
    pr_sel_titulo: "Panel de selectividad",
    pr_sel_en_background:
      "El pipeline está evaluando el panel de selectividad en background. Los "
      + "resultados aparecerán aquí automáticamente al terminar (sin bloquear la "
      + "evaluación).",
    pr_sel_resumen: "Resumen de selectividad (in silico)",
    pr_sel_sin_conclusion:
      "0 umbrales rebasados en el panel; esto no constituye una conclusión de "
      + "seguridad.",
    pr_sel_anti_targets: "Mi panel",
    pr_sel_umbral_minimo: "Umbral mínimo:",
    pr_sel_saber_mas: "Saber más",
    pr_sel_sin_evaluar: "Sin evaluar",
    pr_sel_concentracion: "Concentración implicada por el score:",
    pr_sel_no_es_ki: "Esa concentración no es una Ki ni una IC50.",
    pr_sel_funcion_biologica: "Función biológica y mecanismo",
    pr_sel_relevancia_clinica: "Relevancia clínica y riesgo farmacológico",
    pr_sel_optimizacion: "Optimización química medicinal (SAR)",
    pr_sel_pipeline_running: "Ejecutando el panel del pipeline…",
    pr_sel_evaluating_progress: "Evaluando ({completed}/{total})…",
    pr_sel_evaluate_all: "Evaluar todos (1 a 1)",
    pr_sel_completed: "Completado",
    pr_sel_evaluated: "evaluados",
    pr_sel_incomplete_coverage: "Cobertura incompleta.",
    pr_sel_evaluating: "Evaluando…",
    pr_sel_reevaluate: "Reevaluar",
    pr_sel_fallo_docking: "Fallo en docking local",
    pr_sel_ampliacion_no_disponible_titulo: "No se puede ampliar esta evaluación.",
    pr_sel_ampliacion_no_disponible: "{motivo} Los resultados ya registrados se conservan tal como están.",
    pr_sel_reevaluacion_fallida: "No se pudo reevaluar: {motivo} Se conserva el resultado anterior.",
    pr_sel_evaluate: "Evaluar",

    pr_viewer_legend: "Leyenda",
    pr_viewer_receptor_full: "Receptor completo",
    pr_viewer_ligand_docked: "Ligando acoplado",
    pr_viewer_hide_receptor: "Ocultar receptor",
    pr_viewer_show_receptor: "Mostrar receptor",
    pr_viewer_hide_ligand: "Ocultar ligando",
    pr_viewer_show_ligand: "Mostrar ligando",
    pr_viewer_hide_interactions: "Ocultar interacciones",
    pr_viewer_show_interactions: "Ver interacciones",
    pr_viewer_view: "Ver",
    pr_viewer_relative_importance: "Importancia relativa",
    pr_compare_target: "BLANCO",
    pr_compare_property: "PROPIEDAD",
    pr_compare_difference: "DIFERENCIA",
    pr_compare_close: "Cerrar comparador",
    pr_compare_poses_3d: "Comparar pose n.º {left} y n.º {right} en 3D",

    pr_ev_completed: "COMPLETADA",
    pr_ev_overview_title: "Resumen de la evaluación",
    pr_ev_overview_review: "Revisa las reservas antes de elegir una pose o comparar resultados.",
    pr_ev_overview_available: "La evidencia registrada permite continuar el análisis dentro del mismo protocolo, conservando sus límites.",
    pr_ev_overview_reservations: "Qué requiere revisión",
    pr_ev_overview_sampling: "Muestreo ambiguo",
    pr_ev_overview_universal: "Modelo universal utilizado",
    pr_ev_overview_fallback: "Modelo alternativo utilizado",
    pr_ev_overview_trace_incomplete: "El registro técnico está incompleto; revisa los datos necesarios para reconstruir la corrida en el detalle de reproducibilidad.",
    pr_ev_overview_descriptors_missing: "La corrida no registró descriptores fisicoquímicos.",
    pr_ev_overview_descriptors_partial: "La corrida registró sólo parte de los descriptores fisicoquímicos.",
    pr_ev_overview_selectivity_missing_results: "La evaluación de selectividad no registró resultados.",
    pr_ev_overview_critical: "Aviso crítico",
    pr_ev_overview_caution: "Precaución",
    pr_ev_overview_legacy: "Aviso con severidad no declarada",
    pr_ev_overview_recorded: "Evidencia registrada",
    pr_ev_overview_poses: "{count} poses registradas",
    pr_ev_overview_physical: "Controles físicos superados: {evaluated}/{produced}",
    pr_ev_overview_trace: "Trazas técnicas registradas",
    pr_ev_overview_no_evidence: "No hay poses ni controles superados o trazas completas para resumir.",
    pr_ev_overview_limits: "Límites de esta corrida",
    pr_ev_overview_selectivity: "Selectividad no evaluada",
    pr_sel_margen_amplio: "MARGEN DE SCORE AMPLIO — la diana principal puntúa al menos 2.73 kcal/mol mejor que la peor anti-diana",
    pr_sel_margen_moderado: "MARGEN DE SCORE MODERADO — entre 1.36 y 2.73 kcal/mol a favor de la diana principal",
    pr_sel_margen_estrecho: "MARGEN DE SCORE ESTRECHO — menos de 1.36 kcal/mol, dentro de la dispersión del score de Vina",
    pr_sel_margen_sin: "SIN MARGEN DE SCORE — scores indistinguibles entre diana y anti-diana",
    pr_sel_margen_invertido: "MARGEN DE SCORE NEGATIVO — la molécula puntúa mejor contra una anti-diana que contra su diana",
    pr_sel_margen_sin_datos: "Sin datos suficientes",
    pr_sel_margen_no_es_razon: "Es una diferencia de scores de Vina entre receptores distintos, no una razón de afinidades medida; la dispersión típica del score es de ±{incertidumbre} kcal/mol.",
    pr_ev_sampling_ensemble: "Las poses salen de un ensemble de {count} conformaciones; no se registraron réplicas.",
    pr_ev_sampling_single: "Confórmero único; no se registraron réplicas.",
    pr_ev_sampling_unknown: "El protocolo no informa si hubo ensemble; no se registraron réplicas.",
    pr_ev_overview_transfer: "Reconstrucción por un tercero no demostrada",
    pr_ev_overview_details: "Evidencia y procedencia",
    pr_ev_overview_details_description: "Poses, preparación, controles, modelo y registros técnicos.",
    pr_ev_overview_areas: "{count} áreas de detalle",
    pr_ev_overview_scope: "Esta evidencia no demuestra actividad biológica ni sustituye validación experimental.",
    pr_ev_focus_immediate: "Foco inmediato",
    pr_ev_reproducible_provenance: "Procedencia reproducible",
    pr_ev_status_available: "Evidencia disponible",
    pr_ev_status_review: "Revisión necesaria",
    pr_ev_status_incomplete: "Evidencia incompleta",
    pr_ev_summary_available: "La corrida conserva poses, procedencia y los elementos registrados para intentar reconstruirla; la reconstrucción por un tercero no está demostrada.",
    pr_ev_summary_review: "La corrida produjo evidencia útil, pero contiene reservas que deben revisarse antes de continuar.",
    pr_ev_summary_incomplete: "Faltan afinidad o poses; no debe usarse esta corrida para priorizar el ligando.",
    pr_ev_dimension_system: "Preparación del sistema",
    pr_ev_dimension_docking: "Señal de docking",
    pr_ev_dimension_sampling: "Muestreo de poses",
    pr_ev_dimension_reproducibility: "Reproducibilidad técnica",
    pr_ev_dimension_physical: "Validez física de poses",
    pr_ev_dimension_model: "Dominio del modelo",
    pr_ev_dimension_physicochemical: "Descriptores fisicoquímicos",
    pr_ev_dimension_selectivity: "Evidencia de selectividad",
    pr_ev_label_documented: "Documentada",
    pr_ev_label_review: "Revisar",
    pr_ev_label_insufficient: "Insuficiente",
    pr_ev_label_available: "Disponible",
    pr_ev_label_no_evidence: "Sin evidencia",
    pr_ev_label_not_comparable: "No comparable",
    pr_ev_label_ambiguous: "Ambiguo",
    pr_ev_label_descriptive: "Descriptivo",
    pr_ev_label_recorded: "Registrada",
    pr_ev_label_partial: "Parcial",
    pr_ev_label_controls_passed: "Controles superados",
    pr_ev_label_controls_failed: "Controles fallidos",
    pr_ev_label_review_required: "Requiere revisión",
    pr_ev_label_not_evaluated: "No evaluada",
    pr_ev_label_within_domain: "Dentro del dominio declarado",
    pr_ev_label_outside_domain: "Fuera del dominio",
    pr_ev_label_not_reported: "No informado",
    pr_ev_label_signals_reported: "{count} señales reportadas",
    pr_ev_label_no_data: "Sin datos",
    pr_ev_label_antitarget_count: "{count} anti-targets evaluados",
    pr_ev_label_execution_no_results: "Ejecución sin resultados",
    pr_ev_detail_system_ready: "El inventario registra receptor preparado, grid y referencias estructurales.",
    pr_ev_detail_system_unconfirmed: "El inventario no permite confirmar todos los requisitos de preparación.",
    pr_ev_detail_docking_missing: "Faltan poses o afinidad serializada.",
    pr_ev_detail_docking_present: "{poses} poses serializadas; mejor afinidad cruda {affinity} kcal/mol.",
    pr_ev_detail_sampling_insufficient: "No hay suficientes poses para describir separación interna.",
    pr_ev_detail_sampling_gap: "{count} poses quedan a ≤1 kcal/mol; Δ pose 1–2 {gap} kcal/mol. {muestreo}",
    pr_ev_detail_reproducibility: "Trazas mínimas {available}/{required} (versión del motor, semilla y parser); elementos de reconstrucción {present}/{total}{missing}. Reconstrucción por un tercero: no demostrada.",
    pr_ev_reconstruction_box: "caja de búsqueda efectiva",
    pr_ev_reconstruction_protocol: "protocolo de búsqueda",
    pr_ev_reconstruction_receptor_hash: "hash del receptor",
    pr_ev_reconstruction_ligand_inputs: "hashes de entrada del ligando",
    pr_ev_reconstruction_outputs: "hashes de salida (poses y registro)",
    pr_ev_reconstruction_ligand_prep: "preparación del ligando",
    pr_ev_reconstruction_app_version: "versión de la aplicación",
    pr_ev_missing_items_suffix: " — faltan: {items}",
    pr_ev_detail_model: "{model}{fallback}. El motor de acoplamiento y su versión se declaran en la traza de reproducibilidad.",
    pr_ev_detail_model_with_fallback: "{model}{fallback}. El motor de acoplamiento y su versión se declaran en la traza de reproducibilidad.",
    pr_ev_model_family: "modelo de familia",
    pr_ev_model_universal: "modelo universal",
    pr_ev_fallback_suffix: "; fallback: {reason}",
    pr_ev_detail_physicochemical: "Se reportan valores y reglas por separado; no se convierten en una calificación global.",
    pr_ev_detail_selectivity_evaluated: "Comparación computacional relativa al protocolo; no demuestra selectividad experimental.",
    pr_ev_detail_selectivity_missing: "La corrida no registró un panel de anti-targets.",
    pr_ev_detail_physical_passed: "{evaluated} de {produced} poses recibieron veredicto y ninguna falla los controles de química o geometría.",
    pr_ev_detail_physical_failed: "Al menos la pose principal falla los controles de química o geometría.",
    pr_ev_detail_physical_review: "La batería no corrió entera sobre todas las poses; «requiere revisión» no es una pose aprobada.",
    pr_ev_detail_physical_not_evaluated_reason: "Los controles físicos no llegaron a emitir veredicto ({reason}). Describe lo que le pasó al validador, no a la molécula.",
    pr_ev_detail_physical_not_evaluated: "Esta corrida es anterior a la etapa de validación física: no se ejecutó, y eso no dice nada sobre las poses.",
    pr_ev_assumption_affinity: "Las afinidades se interpretan como señales de ranking dentro del protocolo, no como mediciones de energía libre experimental.",
    pr_ev_assumption_top_pose: "La mejor pose cruda se identifica por el orden de afinidad serializado; ese orden no demuestra validez geométrica.",
    pr_ev_assumption_preparation: "No se atribuyen operaciones de preparación, protonación o minimización que la corrida no haya registrado.",
    pr_ev_uncertainty_near_tie: "{count} poses quedan dentro de 1 kcal/mol; la selección de una sola pose es ambigua.",
    pr_ev_uncertainty_trace: "La traza de reproducibilidad está incompleta.",
    pr_ev_uncertainty_missing_elements: "Faltan elementos para reconstruir la corrida: {items}.",
    pr_ev_uncertainty_outside_domain: "La salida derivada está fuera del dominio de aplicabilidad declarado.",
    pr_ev_uncertainty_domain_unreported: "El dominio de aplicabilidad del modelo no fue informado.",
    pr_ev_next_abstain_label: "Abstención: completar la corrida",
    pr_ev_next_abstain_detail: "No priorizar el ligando ni iniciar cálculos posteriores hasta recuperar poses y resolver los controles fallidos.",
    pr_ev_next_validate_label: "Validar geometría antes de continuar",
    pr_ev_next_validate_detail: "Comprobar choques, valencias, geometría, strain y consistencia del complejo antes de MM-GBSA, dinámica molecular o priorización experimental.",
    pr_ev_next_reservations_label: "Resolver reservas antes de comparar",
    pr_ev_next_reservations_detail: "Documentar las reservas de preparación, dominio o reproducibilidad antes de comparar esta corrida con otras.",
    pr_ev_next_proceed_label: "Apta para análisis posterior",
    pr_ev_next_proceed_detail: "La evidencia disponible permite continuar dentro del mismo protocolo, conservando las limitaciones documentadas.",
    pr_ev_focus_structural: "Evidencia estructural disponible",
    pr_ev_focus_structural_detail: "La decisión justificable y sus límites se conservan en el expediente de la corrida.",
    pr_ev_focus_reservations: "Reservas documentadas",
    pr_ev_focus_reservations_detail: "Consulta la matriz de evidencia antes de comparar o encadenar cálculos posteriores.",
    pr_ev_protocol_conformers: "{generated} de {requested} conformaciones",
    pr_ev_protocol_exhaustiveness: "exhaustividad {value}",
    pr_ev_protocol_seed: "semilla {value}",
    pr_ev_protocol_pose_one: "pose",
    pr_ev_protocol_pose_many: "poses",
    pr_ev_protocol_executed: "Protocolo ejecutado",
    pr_pipeline_label_default: "Pipeline por defecto · target no curado",
    pr_pipeline_label_protease: "M4 Proteasa · pesos por defecto",
    pr_pipeline_label_kinase: "M4 Kinasa · pesos por defecto",
    pr_pipeline_label_nuclear_receptor: "M4 Nuclear Receptor · pesos por defecto",
    pr_pipeline_label_soluble_enzyme: "M4 Soluble Enzyme · pesos por defecto",
    pr_pipeline_label_metalloenzyme: "M4 Metaloenzima · pesos por defecto",
    pr_pipeline_family_default: "Default",
    pr_pipeline_family_gpcr: "GPCR",
    pr_pipeline_family_protease: "Proteasa",
    pr_pipeline_family_kinase: "Kinasa",
    pr_pipeline_family_nuclear_receptor: "Nuclear Receptor",
    pr_pipeline_family_soluble_enzyme: "Soluble Enzyme",
    pr_pipeline_family_metalloenzyme: "Metaloenzima",
    pr_pipeline_note_default: "Target sin curación científica: familia estructural desconocida, Spearman ρ no calibrado. XGBoost se muestra sin peso de release. Interpreta los scores con precaución — no aplica family-gating validado.",
    pr_pipeline_note_provisional: "Contrato provisional: Vina 1.00; XGBoost 0.00; CL-GNN se ejecuta y reporta como senal experimental con peso cero hasta validar externamente el checkpoint exacto.",
    pr_pipeline_note_m4_m5: "M4 usa el contrato provisional Vina solo. M5-Zn se ejecuta y persiste aparte con sus estados de abstencion o revision; UMS y MolChamb siguen como senales informativas.",
    pr_pipeline_node_uncurated_clgnn: "target sin familia curada — CL-GNN no validado",
    pr_pipeline_node_no_default_weight: "sin peso en los pesos por defecto",
    pr_pipeline_node_gpcr_zero_weight: "el artefacto vigente no le asigna peso en GPCR",
    pr_pipeline_node_deprecated: "deprecada; no participa en el contrato de release",
    pr_pipeline_node_ums_excluded: "no entra en el ranking: el ADR 75 retiró el empujón aditivo de 0.06",
    pr_pipeline_node_molchamb_historical: "participa dentro del UMS histórico, no en el stacking",
    pr_pipeline_sub_clgnn: "v3.1 - senal experimental - w=0",
    pr_pipeline_sub_legacy_gnn: "RTMScore, deprecada",
    pr_pipeline_value_unavailable: "No disponible",
    pr_pipeline_sub_invalidated_legacy: "Motor legacy invalidado",
    pr_pipeline_sub_informative: "señal informativa",
    pr_ev_exact_receptor: "Receptor exacto",
    pr_ev_assumptions_registered: "Supuestos registrados",
    pr_docking_pose_counts: "Poses: {poses} · puntos calientes: {hotspots}",
    pr_pep_experimental_aviso:
      "Experimental: ESMFold predice la estructura del péptido y su calidad no está validada en MolDesign. El acoplamiento lo hace después Vina.",
    pr_docking_poses_generated: "Poses generadas",
    pr_sar_key_change: "Cambio clave",
    pr_sar_similarity: "Similitud",
    pr_alert_positive_badge: "DESTACADO POSITIVO",
    pr_m5_protocol_label: "Protocolo M5-Zn",
    pr_m5_applied_profile: "Perfil M5-Zn aplicado",
    pr_m5_applicability_check: "Comprobación de aplicabilidad · M5-Zn",
    pr_signals_recorded_title: "Señales registradas en esta corrida",
    pr_signals_effective_weights: "Pesos efectivos registrados: {weights}",
    pr_signals_individual_weights: "Pesos individuales registrados: {weights}. No se registró su normalización efectiva.",
    pr_signals_weights_missing: "Esta corrida no registró sus pesos. La familia del receptor no permite reconstruirlos.",
    pr_signals_missing_weighted: "Señales con peso registrado que no produjeron salida: {signals}.",
    pr_pipeline_run_label: "Protocolo de la corrida",
    pr_pipeline_used: "Protocolo utilizado: {protocol}",
    pr_pipeline_m4_description: "Protocolo general de evaluación: reúne los resultados del docking y combina las señales disponibles con los pesos registrados de la corrida.",
    pr_pipeline_m5_description: "Protocolo para dianas de zinc: combina las señales requeridas por el perfil específico de la estructura evaluada.",
    pr_pipeline_not_recorded: "Protocolo utilizado: no registrado",
    pr_pipeline_details: "Detalles del protocolo",
    pr_pipeline_audit_review: "Resultado de auditoría: requiere revisión.",
    pr_m5_composite_score: "Puntuación compuesta",
    pr_ligand_species_ph: "Especie acoplada a pH {ph}",
    pr_ligand_species_no_protonation: "Especie acoplada: protonación no aplicada",
    pr_ligand_species_protonation_unknown: "Especie acoplada: protonación no consta completa",
    pr_reg_paper_badge: "ARTÍCULO",
    pr_reg_corrigendum: "FE DE ERRATAS",
    pr_reg_figures_replaced: "cifras reemplazadas",
    pr_reg_pre_registered_gate: "Criterio preregistrado.",
    pr_reg_protocol_label: "Protocolo.",
    pr_reg_sealed_artifacts: "artefactos sellados",
    pr_reg_hash_count: "{count} valores hash",
    pr_reg_gates_passed: "controles superados",
    pr_reg_versus: "frente a",
    pr_reg_records_have_paper: "{paper} de {total} registros tienen un artículo redactado.",
    pr_reg_figures_replaced_sentence: "Cifras reemplazadas.",
    pr_xai_feature_vina_best: "Afinidad Vina (mejor pose)",
    pr_xai_feature_contacts_cc: "Contactos C-C (Van der Waals)",
    pr_xai_feature_contacts_cn: "Contactos C-N",
    pr_xai_feature_contacts_co: "Contactos C-O",
    pr_xai_value_shap: "Valor SHAP",
    pr_xai_effect: "Efecto",
    pr_xai_right_green: "derecha (verdes)",
    pr_xai_left_red: "izquierda (rojas)",
    pr_xai_feature_mw: "Peso molecular (MW)",

    // ── Explicabilidad ────────────────────────────────────────────
    pr_xai_shap_nativo: "SHAP NATIVO DE XGBOOST",
    pr_xai_abejas_a: "Diagrama de abejas direccional. Las características hacia la",
    pr_xai_abejas_b: "aumentan la afinidad, hacia la",
    pr_xai_abejas_c: "la penalizan.",
    pr_xai_atencion_gnn: "Atención GNN (RTMScore)",
    pr_xai_mapa_hotspots: "MAPA DE HOTSPOTS",
    pr_xai_topologia: "Topología 2D",
    pr_xai_generando: "Generando proyección…",
    pr_xai_farmacoforos: "Desglose de farmacóforos",
    pr_xai_sin_datos: "Sin datos de explicabilidad.",
    pr_xai_shap_poblara:
      "El motor SHAP nativo poblará esta área al completar una evaluación de "
      + "ligando exitosa.",
    pr_xai_dominio: "Dominio de aplicabilidad",
    pr_xai_fuera_dominio: "✗ Fuera de dominio",

    // ── Motor de docking ──────────────────────────────────────────
    pr_mot_clasico: "CLÁSICO",
    pr_mot_clasico_d:
      "Motor de docking estándar. Exhaustiveness=8. ~20 s por ligando.",
    pr_mot_rapido: "RÁPIDO",
    pr_mot_rapido_d: "Smart sampling, 2–3× más rápido que Vina. Misma precisión.",
    pr_mot_difusion: "DIFUSIÓN",
    pr_mot_difusion_d:
      "Docking generativo por difusión (Corso et al. ICLR 2023).",
    pr_mot_peptido:
      "Se habilita al detectar un péptido (≥3 enlaces C(=O)N) o al seleccionar "
      + "manualmente uno de estos motores.",
    pr_mot_aviso_vina:
      "Con Vina seleccionado, sólo verás un aviso si la molécula parece un "
      + "péptido.",
    pr_mot_precision_completa: "Precisión completa",
    pr_mot_precision_media: "Precisión media (CUDA)",

    // ── Selectividad ──────────────────────────────────────────────
    pr_sel_sin_evaluacion: "no hay una evaluación a la que asociar el panel",

    // ── Timeline ──────────────────────────────────────────────────
    pr_timeline_etapas: "etapas",
  },
  en: {
    pr_pipeline_sub_this_run: "from this run",
    // ── Run pre-flight ────────────────────────────────────────────
    pr_preflight_state_blocking: "Blocks",
    pr_preflight_state_warning: "Warning",
    pr_preflight_state_not_evaluated: "Not evaluated",
    pr_preflight_state_pass: "Passes",
    pr_preflight_method_qvina: "Molecular docking with QuickVina 2",
    pr_preflight_method_vina: "Molecular docking with AutoDock Vina",
    pr_preflight_method_vina_compatible: "Vina-compatible docking route",
    pr_preflight_method_configured: "Configured docking route",
    pr_preflight_ensemble: "Conformer ensemble",
    pr_comprobacion_automatica:
      "The ligand, receptor and configuration will be checked automatically when you run the evaluation.",
    pr_comprobacion_pendiente: "Pending",
    pr_conformeros_resumen_uno: "1 initial conformer",
    pr_conformeros_resumen_varios: "{cantidad} initial conformers",
    pr_preflight_receptor: "Receptor",
    pr_preflight_ligand: "Ligand",
    pr_preflight_effective_box: "Effective search box",
    pr_preflight_blocker_one: "blocker",
    pr_preflight_blocker_many: "blockers",
    pr_preflight_warning_one: "warning",
    pr_preflight_warning_many: "warnings",
    pr_preflight_fingerprint: "fingerprint",
    pr_preflight_species: "Species",
    pr_preflight_source: "Source",
    pr_preflight_after_filtering: "After filtering",
    pr_preflight_removed: "Removed",
    pr_preflight_waters: "Waters",
    pr_preflight_metals: "Metals",
    pr_preflight_not_evaluated: "Not evaluated.",
    pr_preflight_controls: "Controls",
    pr_preflight_species_water: "water",
    pr_preflight_species_metal: "metal",
    pr_preflight_species_organic_cofactor: "organic cofactor",
    pr_preflight_species_other_component: "other structure component",
    pr_preflight_declared_cofactors: "Only the declared cofactors are retained: {cofactors}",
    pr_stage_required: "Required",
    pr_stage_move_up: "Move up",
    pr_stage_move_down: "Move down",
    pr_stage_running: "RUNNING",
    pr_stage_done: "DONE",
    pr_stage_failed: "FAILED",

    // ── Advanced configuration and engines ────────────────────────
    pr_cfg_activos: "active",
    pr_cfg_ad: "AD",
    pr_cfg_abrir_gestor: "Open model manager",
    pr_cfg_centro: "CENTER",
    pr_cfg_cpu_only: "CPU only",
    pr_cfg_cuda: "CUDA",
    pr_cfg_docks_paralelos: "Parallel docking runs",
    pr_cfg_encender: "Enable",
    pr_cfg_estimado: "estimated",
    pr_cfg_experimental: "Experimental",
    pr_cfg_num_modes: "Number of modes",
    pr_cfg_opencl: "OpenCL",
    pr_cfg_openmm_refinement: "Folding + refinement with OpenMM.",
    pr_cfg_pasos_mmgbsa: "MM-GBSA steps",
    pr_cfg_perfil_admet: "ADMET profile",
    pr_cfg_plegado: "FOLDING",
    pr_cfg_preciso: "HIGH ACCURACY",
    pr_cfg_predictivo: "PREDICTIVE",
    pr_cfg_procesos: "Processes",
    pr_cfg_pose: "pose",
    pr_cfg_poses: "poses",
    pr_cfg_quickvina: "QuickVina 2",
    pr_cfg_selectividad_antitarget: "Anti-target selectivity",
    pr_cfg_tuyo: "Yours",
    pr_cfg_volver_ph: "Reset to 7.4",
    pr_cfg_workers: "Workers",
    pr_engine_vina_fp64: "AutoDock Vina (FP64)",
    pr_engine_diffdock_fp32: "DiffDock (FP32)",
    pr_engine_fp16: "FP16",
    pr_engine_fp32: "FP32",
    pr_engine_quickvina_fp64: "QuickVina 2 (FP64)",
    pr_engine_auto_detect: "auto-detection",
    pr_engine_folding_refinement: "Full folding + refinement with OpenMM.",
    pr_engine_requires_gpu: "Requires a GPU",

    pr_tab_structure_evidence: "Structure and evidence",
    pr_tab_properties: "Properties",
    pr_tab_explainability: "Explainability",
    pr_analysis_alerts_reservations: "Alerts and limitations",
    pr_admet_available: "ADMET available",
    pr_admet_calculate: "Calculate ADMET",
    pr_sar_evidence_available: "SAR evidence available",
    pr_pose_a: "Pose A",
    pr_pose_b: "Pose B",
    pr_pose_label: "Pose",
    pr_selector_label: "Selector",
    pr_pose_comparison_3d: "Compare poses in 3D",
    pr_pose_coordinates_recorded: "recorded coordinates",

    // ── Parameters and chemical nomenclature ──────────────────────
    pr_param_admet_no_disponible: "ADMET-AI unavailable",
    pr_param_admet_ai: "ADMET-AI",
    pr_param_cns_mpo: "CNS MPO",
    pr_param_coincidencias: "matches",
    pr_param_filtro_egan: "Egan",
    pr_param_filtro_ghose: "Ghose",
    pr_param_filtro_lipinski: "Lipinski",
    pr_param_filtro_muegge: "Muegge",
    pr_param_filtro_veber: "Veber",
    pr_param_hbd_hba: "HBD / HBA",
    pr_param_hia: "HIA",
    pr_param_le: "LE",
    pr_param_lle: "LLE",
    pr_param_logp: "LogP",
    pr_param_ml_stacking: "Stacked model ensemble (ML)",
    pr_param_modelo_universal: "Universal",
    pr_param_modelo_usado: "Model used",
    pr_param_mw: "MW",
    pr_param_no: "not",
    pr_param_pains: "PAINS",
    pr_param_permeable: "✓ Permeable",
    pr_param_ppb: "PPB",
    pr_param_rings: "Rings",
    pr_param_rotatable_bonds: "Rotatable bonds",
    pr_param_solubilidad: "Solubility",
    pr_param_tpsa: "TPSA",

    pr_analisis_corrida: "Run analysis",
    pr_areas_analisis: "Analysis areas",
    pr_metodos_avanzados: "Advanced analysis methods",
    pr_elegir_poses: "Choose poses to compare",
    pr_comparar_explicacion:
      "Choose any pair of poses produced by this run. The comparison keeps "
      + "affinity, selector signal and physical state; it does not turn that data "
      + "into a single grade.",
    pr_sin_poses: "There are no serialised poses to compare yet.",
    pr_abrir_comparacion: "Open 3D comparison",
    pr_minimo_dos_poses: "At least two poses are needed to open a comparison.",
    pr_resumen_poses: "Comparable summary of every pose produced",
    pr_controles_fisicos: "Physical controls",
    pr_post_docking: "Post-docking analysis",
    pr_post_docking_limite:
      "These actions widen the evidence of the run; they do not turn a docking "
      + "affinity into experimental activity, efficacy or selectivity.",
    pr_refinar_mmgbsa: "MM-GBSA unavailable",
    pr_mmgbsa_retirado: "Legacy parameterisation fails the integrity check. Historical values without a recorded engine version are invalid.",
    pr_mmgbsa_indisponible: "Unavailable",
    pr_mmgbsa_control_retirado: "MM-GBSA unavailable: inconsistent legacy parameterisation.",
    pr_ordenar_poses: "rank poses of this same molecule",
    pr_mmgbsa_no_comparable:
      "It is not comparable between different molecules, nor against an "
      + "experimental ΔG: the ligand is parameterised with protein atom types "
      + "(AMBER14), not with a small-molecule force field. It requires C, H, O, "
      + "N, S or P — with halogens the calculation cannot run.",
    pr_calcular_admet: "Calculate the ADMET profile",
    pr_admet_predice:
      "It predicts solubility, intestinal absorption, BBB permeability and plasma "
      + "protein binding with ADMET-AI, on this machine. It depends",
    pr_solo_smiles: "from the SMILES only",
    pr_admet_no_repite:
      ": it uses neither the pose nor the receptor, so there is no need to repeat "
      + "the docking.",
    pr_admet_predicciones:
      "These are predictions from a model, not measurements: they are cited as "
      + "such. The first run loads the ensemble and can take a while — especially "
      + "in a virtual machine or without a GPU.",
    pr_viaja_en_dossier: "and it travels in the dossier.",
    pr_sar_explicacion:
      "It looks up analogues that already exist in the history. This version does "
      + "not generate activity and does not invent an SAR series when there are no "
      + "comparable measurements.",

    pr_receptor_intro:
      "Add your own proteins to MolDesign's private database.",
    pr_modo_automatico: "Automatic mode (.PDB)",
    pr_sube_archivo: "Upload a file",
    pr_por_ejemplo_rcsb: "(for example, taken from the RCSB PDB).",
    pr_pipeline_filtrara:
      "The pipeline will filter the chain and the water, and generate the PDBQT "
      + "with Meeko.",
    pr_se_autodescubrira: "It will auto-discover the",
    pr_basado_cocristal: "based on the co-crystallised ligand.",
    pr_ya_preparado: "already prepared in your workspace.",
    pr_no_modificaremos:
      "We will not modify the structure; it will be fed straight to the Vina "
      + "engine.",
    pr_indicar_coordenadas:
      "give the (X, Y, Z) coordinates of the box center.",
    pr_nombre_receptor: "Receptor name",
    pr_tamano_caja: "Box size (grid size)",
    pr_automatizacion: "Smart automation",
    pr_servidor_rastreara:
      "The server will scan the PDB structure and compute a spatial center on the "
      + "main co-crystallised ligand.",
    pr_compartir_comunidad: "Share with the community",
    pr_cerrar_subida: "Close receptor upload",
    // ── Subida de un receptor propio: tres caminos ──
    pr_rp_camino_titulo:
      "What are you uploading?",
    pr_rp_a_titulo:
      "Raw structure",
    pr_rp_a_desc:
      "Experimental or predicted. MolDesign prepares it, removes what does not belong and audits what changed.",
    pr_rp_a_punto1:
      "Chains, gaps, waters, metals and cofactors are resolved or declared in Preparation.",
    pr_rp_a_punto2:
      "If it is a prediction (AlphaFold DB), the confidence (pLDDT) of the site is read and Preparation asks for review where it is low.",
    pr_rp_a_punto3:
      "If the file does not contain the crystal ligand, give the center of the search box.",
    pr_rp_b_titulo:
      "Already prepared by your team",
    pr_rp_b_desc:
      "MolDesign respects your protonation, waters, metals and cofactors; it does not protonate again.",
    pr_rp_b_punto1:
      "The protonation is declared by you: it is checked that Meeko applied the templates your file names (HID, HIE, HIP, CYX…), not that they are correct.",
    pr_rp_b_punto2:
      "A species that cannot be represented for Vina is rejected with the reason; it is not removed silently.",
    pr_rp_b_punto3:
      "A PQR from PDB2PQR is read; Vina does not use its charges and this is declared.",
    pr_rp_c_titulo:
      "PDBQT ready for Vina",
    pr_rp_c_desc:
      "It is evaluated as is, without going through Meeko or protonating again.",
    pr_rp_c_punto1:
      "A PDBQT does not say where the site is: give the center of the search box.",
    pr_rp_c_punto2:
      "Without the source structure, Preparation cannot audit what was removed and says so; with it, it compares the source with the PDBQT.",
    pr_rp_archivo:
      "Receptor file",
    pr_rp_elegir_archivo:
      "Choose file",
    pr_rp_sin_archivo:
      "No file chosen",
    pr_rp_extensiones:
      "Accepted: {ext}",
    pr_rp_tambien_gz:
      "also compressed with .gz",
    pr_rp_origen:
      "Source structure (optional)",
    pr_rp_origen_nota:
      "The structure the PDBQT came from. MolDesign checks that it is the same receptor and audits what was removed when preparing it.",
    pr_rp_origen_quitar:
      "Remove",
    pr_rp_extension_invalida:
      "«{name}» does not have an extension accepted in this path ({ext}). Choose another file or change path.",
    pr_rp_falta_archivo:
      "Choose the receptor file.",
    pr_rp_caja_opcional:
      "Search box (optional)",
    pr_rp_caja_obligatoria:
      "Search box (required)",
    pr_rp_caja_incompleta:
      "Give all three center coordinates (X, Y, Z) or none.",
    pr_rp_caja_obligatoria_falta:
      "A PDBQT does not say where the site is: give the coordinates (X, Y, Z) of the box center.",
    pr_rp_cadena_otra:
      "Other chain",
    pr_rp_cadena_nota:
      "Type the chain as it appears in the file (an mmCIF may call them, for example, «AAA»).",
    pr_custom_receptor_title: "Upload custom receptor",
    pr_custom_manual_mode: "Manual mode (.PDBQT)",
    pr_custom_active_site: "active site",
    pr_custom_required: "required",
    pr_custom_name_placeholder: "e.g. my mutant kinase",
    pr_custom_chain_to_evaluate: "Chain to evaluate",
    pr_custom_cofactors_optional: "Cofactors to keep (optional)",
    pr_custom_grid_center: "Search box center coordinates",
    pr_custom_grid_size_x: "Size X",
    pr_custom_grid_size_y: "Size Y",
    pr_custom_grid_size_z: "Size Z",
    pr_custom_processing: "Processing…",
    pr_custom_select_file: "Select file",
    pr_custom_process_file: "Process: {name}…",
    pr_viewer_switch: "Switch viewer",
    pr_viewer_switch_to: "Switch to {viewer} viewer",
    pr_viewer_switch_label: "View {viewer}",
    pr_viewer_waiting_coordinates: "Waiting for structural coordinates…",
    pr_viewer_grid_box: "Search box",
    pr_contact_label: "Contact",
    pr_viewer_omitted: "Omitted",

    pr_preparacion_titulo: "Preflight check",
    pr_preparacion_explicacion:
      "A pre-flight check over the real files. It does not run the docking and "
      + "issues no verdict about the molecule. If it detects a technical blocker, "
      + "the run does not start and the reason is shown here.",
    pr_revisada_aceptada: "Reviewed and accepted by you",
    pr_marcar_revisada: "Mark as reviewed",
    pr_conformero_unico: "Single conformer",
    pr_inputs_cambiaron:
      "The inputs changed since the last check, so it no longer describes what "
      + "would run. It repeats by itself when you press “Run evaluation”.",
    pr_resumen_guardado:
      "Summary stored with the case. The control detail and the diff are "
      + "recalculated when anything about the run changes.",
    pr_ligando_canonico: "Ligand (canonical)",
    pr_de_la_fuente: "From the source to the preparer's input",
    pr_especies_retiradas: "Chemical species identified as removed",
    pr_codigos_residuo:
      "The codes correspond to the residue names in the PDB file; the count is "
      + "the number of atom records removed.",
    pr_politica_preparacion: "Preparation policy for this route",
    pr_metodo: "Method:",
    pr_aguas_eliminadas: "All of them are removed before docking",
    pr_cofactores_reconocidos: "Recognized organic cofactors:",
    pr_num_conformaciones: "Number of ensemble conformations",

    pr_reg_cargando_paper: "Loading the paper…",
    pr_reg_cargando: "Loading the record…",
    pr_reg_no_cargado: "The scientific record could not be loaded.",
    pr_reg_sin_paper:
      "The paper for this record has not been written yet. Below is the full "
      + "sheet, generated from the sealed manifest — which is the source of truth "
      + "for every number on this page.",
    pr_reg_hipotesis: "Hypothesis.",
    pr_reg_razon_decision: "Reason for the decision",
    pr_reg_lo_que_se_sostuvo: "What held up, and what fell",
    pr_reg_preregistro:
      "Every MolDesign experiment was registered before it ran, with its "
      + "hypothesis and its decision criterion written in advance, and sealed with "
      + "the commit, the seed, the environment and the hashes of everything it "
      + "touched. This page opens all of them: the ones that worked and the ones "
      + "that did not.",
    pr_reg_defecto_detectado: "A defect found",
    pr_reg_despues: "afterwards",
    pr_reg_hipotesis_derribadas: "hypotheses knocked down",
    pr_reg_otras_poblaciones: "The other populations in the record",
    pr_reg_ni_exitos_ni_fracasos:
      "These are neither successes nor failures, which is why they do not enter "
      + "the scoreboard. They are here because they are half of the work.",
    pr_reg_activa_capa: "Turn on a layer to see those records.",
    pr_reg_generado_desde: "Generated from the manifests sealed by",

    pr_sel_sin_guardar: "Result not saved.",
    pr_sel_titulo: "Selectivity panel",
    pr_sel_en_background:
      "The pipeline is evaluating the selectivity panel in the background. The "
      + "results will appear here automatically when it finishes (without "
      + "blocking the evaluation).",
    pr_sel_resumen: "Selectivity summary (in silico)",
    pr_sel_sin_conclusion:
      "0 thresholds exceeded in the panel; this does not constitute a safety "
      + "conclusion.",
    pr_sel_anti_targets: "My panel",
    pr_sel_umbral_minimo: "Minimum threshold:",
    pr_sel_saber_mas: "Learn more",
    pr_sel_sin_evaluar: "Not evaluated",
    pr_sel_concentracion: "Concentration implied by the score:",
    pr_sel_no_es_ki: "That concentration is neither a Ki nor an IC50.",
    pr_sel_funcion_biologica: "Biological function and mechanism",
    pr_sel_relevancia_clinica: "Clinical relevance and pharmacological risk",
    pr_sel_optimizacion: "Medicinal chemistry optimization (SAR)",
    pr_sel_pipeline_running: "Running the pipeline panel…",
    pr_sel_evaluating_progress: "Evaluating ({completed}/{total})…",
    pr_sel_evaluate_all: "Evaluate all (one at a time)",
    pr_sel_completed: "Done",
    pr_sel_evaluated: "evaluated",
    pr_sel_incomplete_coverage: "Incomplete coverage.",
    pr_sel_evaluating: "Evaluating…",
    pr_sel_reevaluate: "Re-evaluate",
    pr_sel_fallo_docking: "Local docking failure",
    pr_sel_ampliacion_no_disponible_titulo: "This evaluation cannot be extended.",
    pr_sel_ampliacion_no_disponible: "{motivo} Results already recorded are kept as they are.",
    pr_sel_reevaluacion_fallida: "Re-evaluation failed: {motivo} The previous result is kept.",
    pr_sel_evaluate: "Evaluate",

    pr_viewer_legend: "Legend",
    pr_viewer_receptor_full: "Full receptor",
    pr_viewer_ligand_docked: "Docked ligand",
    pr_viewer_hide_receptor: "Hide receptor",
    pr_viewer_show_receptor: "Show receptor",
    pr_viewer_hide_ligand: "Hide ligand",
    pr_viewer_show_ligand: "Show ligand",
    pr_viewer_hide_interactions: "Hide interactions",
    pr_viewer_show_interactions: "Show interactions",
    pr_viewer_view: "View",
    pr_viewer_relative_importance: "Relative importance",
    pr_compare_target: "TARGET",
    pr_compare_property: "PROPERTY",
    pr_compare_difference: "DIFFERENCE",
    pr_compare_close: "Close comparison",
    pr_compare_poses_3d: "Compare poses #{left} and #{right} in 3D",

    pr_ev_completed: "COMPLETED",
    pr_ev_overview_title: "Evaluation summary",
    pr_ev_overview_review: "Review the reservations before choosing a pose or comparing results.",
    pr_ev_overview_available: "The recorded evidence supports further analysis within the same protocol, retaining its limitations.",
    pr_ev_overview_reservations: "What needs review",
    pr_ev_overview_sampling: "Ambiguous sampling",
    pr_ev_overview_universal: "Universal model used",
    pr_ev_overview_fallback: "Alternative model used",
    pr_ev_overview_trace_incomplete: "The technical record is incomplete; review the information needed to reconstruct the run in the reproducibility details.",
    pr_ev_overview_descriptors_missing: "The run did not record physicochemical descriptors.",
    pr_ev_overview_descriptors_partial: "The run recorded only some of the physicochemical descriptors.",
    pr_ev_overview_selectivity_missing_results: "The selectivity evaluation did not record results.",
    pr_ev_overview_critical: "Critical warning",
    pr_ev_overview_caution: "Caution",
    pr_ev_overview_legacy: "Warning with undeclared severity",
    pr_ev_overview_recorded: "Recorded evidence",
    pr_ev_overview_poses: "{count} poses recorded",
    pr_ev_overview_physical: "Physical checks passed: {evaluated}/{produced}",
    pr_ev_overview_trace: "Technical traces recorded",
    pr_ev_overview_no_evidence: "There are no poses, passed checks or complete traces to summarize.",
    pr_ev_overview_limits: "Limitations of this run",
    pr_ev_overview_selectivity: "Selectivity not evaluated",
    pr_sel_margen_amplio: "WIDE SCORE MARGIN — the main target scores at least 2.73 kcal/mol better than the worst anti-target",
    pr_sel_margen_moderado: "MODERATE SCORE MARGIN — between 1.36 and 2.73 kcal/mol in favor of the main target",
    pr_sel_margen_estrecho: "NARROW SCORE MARGIN — less than 1.36 kcal/mol, within the dispersion of the Vina score",
    pr_sel_margen_sin: "NO SCORE MARGIN — scores indistinguishable between target and anti-target",
    pr_sel_margen_invertido: "NEGATIVE SCORE MARGIN — the molecule scores better against an anti-target than against its target",
    pr_sel_margen_sin_datos: "Insufficient data",
    pr_sel_margen_no_es_razon: "This is a difference between Vina scores from different receptors, not a measured affinity ratio; the typical dispersion of the score is ±{incertidumbre} kcal/mol.",
    pr_ev_sampling_ensemble: "The poses come from an ensemble of {count} conformers; no replicates were recorded.",
    pr_ev_sampling_single: "Single conformer; no replicates were recorded.",
    pr_ev_sampling_unknown: "The protocol does not report whether there was an ensemble; no replicates were recorded.",
    pr_ev_overview_transfer: "Reconstruction by a third party has not been demonstrated",
    pr_ev_overview_details: "Evidence and provenance",
    pr_ev_overview_details_description: "Poses, preparation, checks, model and technical records.",
    pr_ev_overview_areas: "{count} areas of detail",
    pr_ev_overview_scope: "This evidence does not demonstrate biological activity or replace experimental validation.",
    pr_ev_focus_immediate: "Immediate focus",
    pr_ev_reproducible_provenance: "Reproducible provenance",
    pr_ev_status_available: "Evidence available",
    pr_ev_status_review: "Review needed",
    pr_ev_status_incomplete: "Incomplete evidence",
    pr_ev_summary_available: "This run retains poses, provenance, and the recorded items needed to attempt reconstruction; reconstruction by a third party has not been demonstrated.",
    pr_ev_summary_review: "This run produced useful evidence, but it has reservations that should be reviewed before proceeding.",
    pr_ev_summary_incomplete: "Affinity or poses are missing; do not use this run to prioritize the ligand.",
    pr_ev_dimension_system: "System preparation",
    pr_ev_dimension_docking: "Docking signal",
    pr_ev_dimension_sampling: "Pose sampling",
    pr_ev_dimension_reproducibility: "Technical reproducibility",
    pr_ev_dimension_physical: "Physical validity of poses",
    pr_ev_dimension_model: "Model applicability domain",
    pr_ev_dimension_physicochemical: "Physicochemical descriptors",
    pr_ev_dimension_selectivity: "Selectivity evidence",
    pr_ev_label_documented: "Documented",
    pr_ev_label_review: "Review",
    pr_ev_label_insufficient: "Insufficient",
    pr_ev_label_available: "Available",
    pr_ev_label_no_evidence: "No evidence",
    pr_ev_label_not_comparable: "Not comparable",
    pr_ev_label_ambiguous: "Ambiguous",
    pr_ev_label_descriptive: "Descriptive",
    pr_ev_label_recorded: "Recorded",
    pr_ev_label_partial: "Partial",
    pr_ev_label_controls_passed: "Checks passed",
    pr_ev_label_controls_failed: "Checks failed",
    pr_ev_label_review_required: "Review required",
    pr_ev_label_not_evaluated: "Not evaluated",
    pr_ev_label_within_domain: "Within the stated domain",
    pr_ev_label_outside_domain: "Outside the domain",
    pr_ev_label_not_reported: "Not reported",
    pr_ev_label_signals_reported: "{count} signals reported",
    pr_ev_label_no_data: "No data",
    pr_ev_label_antitarget_count: "{count} anti-targets evaluated",
    pr_ev_label_execution_no_results: "Run produced no results",
    pr_ev_detail_system_ready: "The inventory records a prepared receptor, grid, and structural references.",
    pr_ev_detail_system_unconfirmed: "The inventory does not confirm every preparation requirement.",
    pr_ev_detail_docking_missing: "Serialized poses or affinity are missing.",
    pr_ev_detail_docking_present: "{poses} poses serialized; best raw affinity {affinity} kcal/mol.",
    pr_ev_detail_sampling_insufficient: "There are not enough poses to describe internal separation.",
    pr_ev_detail_sampling_gap: "{count} poses are within 1 kcal/mol; Δ pose 1–2 is {gap} kcal/mol. {muestreo}",
    pr_ev_detail_reproducibility: "Minimum traces {available}/{required} (engine version, seed, and parser); reconstruction items {present}/{total}{missing}. Reconstruction by a third party has not been demonstrated.",
    pr_ev_reconstruction_box: "effective search box",
    pr_ev_reconstruction_protocol: "search protocol",
    pr_ev_reconstruction_receptor_hash: "receptor hash",
    pr_ev_reconstruction_ligand_inputs: "ligand input hashes",
    pr_ev_reconstruction_outputs: "output hashes (poses and log)",
    pr_ev_reconstruction_ligand_prep: "ligand preparation",
    pr_ev_reconstruction_app_version: "application version",
    pr_ev_missing_items_suffix: " — missing: {items}",
    pr_ev_detail_model: "{model}{fallback}. The docking engine and its version are listed in the reproducibility trace.",
    pr_ev_detail_model_with_fallback: "{model}{fallback} The docking engine and its version are listed in the reproducibility trace.",
    pr_ev_model_family: "family model",
    pr_ev_model_universal: "universal model",
    pr_ev_fallback_suffix: "; fallback reason: {reason}",
    pr_ev_detail_physicochemical: "Values and rules are reported separately; they are not combined into a global rating.",
    pr_ev_detail_selectivity_evaluated: "A computational comparison within this protocol; it does not demonstrate experimental selectivity.",
    pr_ev_detail_selectivity_missing: "This run did not record an anti-target panel.",
    pr_ev_detail_physical_passed: "{evaluated} of {produced} poses received a verdict, and none failed chemistry or geometry checks.",
    pr_ev_detail_physical_failed: "At least the primary pose fails chemistry or geometry checks.",
    pr_ev_detail_physical_review: "The full check suite did not run on every pose; “review required” does not mean any pose passed.",
    pr_ev_detail_physical_not_evaluated_reason: "The physical checks did not issue a verdict ({reason}). This describes what happened to the validator, not the molecule.",
    pr_ev_detail_physical_not_evaluated: "This run predates the physical validation stage: it was not run, which says nothing about the poses.",
    pr_ev_assumption_affinity: "Affinities are ranking signals within this protocol, not experimental free-energy measurements.",
    pr_ev_assumption_top_pose: "The best raw pose is identified by the serialized affinity order; that order does not demonstrate geometric validity.",
    pr_ev_assumption_preparation: "Preparation, protonation, or minimization steps are not attributed unless the run recorded them.",
    pr_ev_uncertainty_near_tie: "{count} poses are within 1 kcal/mol; selecting a single pose is ambiguous.",
    pr_ev_uncertainty_trace: "The reproducibility trace is incomplete.",
    pr_ev_uncertainty_missing_elements: "Items needed to reconstruct the run are missing: {items}.",
    pr_ev_uncertainty_outside_domain: "The derived output is outside the stated applicability domain.",
    pr_ev_uncertainty_domain_unreported: "The model's applicability domain was not reported.",
    pr_ev_next_abstain_label: "Abstain: complete the run",
    pr_ev_next_abstain_detail: "Do not prioritize the ligand or start later calculations until poses are recovered and failed controls are resolved.",
    pr_ev_next_validate_label: "Validate geometry before proceeding",
    pr_ev_next_validate_detail: "Check clashes, valences, geometry, strain, and complex consistency before MM-GBSA, molecular dynamics, or experimental prioritization.",
    pr_ev_next_reservations_label: "Resolve reservations before comparison",
    pr_ev_next_reservations_detail: "Document preparation, domain, or reproducibility reservations before comparing this run with others.",
    pr_ev_next_proceed_label: "Suitable for later analysis",
    pr_ev_next_proceed_detail: "The available evidence supports continuing within the same protocol, subject to the documented limitations.",
    pr_ev_focus_structural: "Structural evidence available",
    pr_ev_focus_structural_detail: "The justifiable decision and its limits are retained in the run record.",
    pr_ev_focus_reservations: "Documented reservations",
    pr_ev_focus_reservations_detail: "Review the evidence matrix before comparing or chaining later calculations.",
    pr_ev_protocol_conformers: "{generated} of {requested} conformers",
    pr_ev_protocol_exhaustiveness: "exhaustiveness {value}",
    pr_ev_protocol_seed: "seed {value}",
    pr_ev_protocol_pose_one: "pose",
    pr_ev_protocol_pose_many: "poses",
    pr_ev_protocol_executed: "Executed protocol",
    pr_pipeline_label_default: "Default pipeline · uncured target",
    pr_pipeline_label_protease: "M4 Protease · default weights",
    pr_pipeline_label_kinase: "M4 Kinase · default weights",
    pr_pipeline_label_nuclear_receptor: "M4 Nuclear Receptor · default weights",
    pr_pipeline_label_soluble_enzyme: "M4 Soluble Enzyme · default weights",
    pr_pipeline_label_metalloenzyme: "M4 Metalloenzyme · default weights",
    pr_pipeline_family_default: "Default",
    pr_pipeline_family_gpcr: "GPCR",
    pr_pipeline_family_protease: "Protease",
    pr_pipeline_family_kinase: "Kinase",
    pr_pipeline_family_nuclear_receptor: "Nuclear Receptor",
    pr_pipeline_family_soluble_enzyme: "Soluble Enzyme",
    pr_pipeline_family_metalloenzyme: "Metalloenzyme",
    pr_pipeline_note_default: "Target has not been scientifically curated: its structural family is unknown, and Spearman ρ has not been calibrated. XGBoost is shown with no release weight. Interpret scores with caution — validated family gating does not apply.",
    pr_pipeline_note_provisional: "Provisional contract: Vina 1.00; XGBoost 0.00; CL-GNN runs and is reported as an experimental signal with zero weight until the exact checkpoint is validated externally.",
    pr_pipeline_note_m4_m5: "M4 uses the provisional Vina-only contract. M5-Zn runs and is persisted separately with its abstention or review states; UMS and MolChamb remain informative signals.",
    pr_pipeline_node_uncurated_clgnn: "target has no curated family — CL-GNN not validated",
    pr_pipeline_node_no_default_weight: "no weight in the default weights",
    pr_pipeline_node_gpcr_zero_weight: "the current artifact assigns it no weight in GPCR",
    pr_pipeline_node_deprecated: "deprecated; it is not part of the release contract",
    pr_pipeline_node_ums_excluded: "not included in ranking: ADR 75 removed the additive 0.06 boost",
    pr_pipeline_node_molchamb_historical: "included within historical UMS, not in stacking",
    pr_pipeline_sub_clgnn: "v3.1 · experimental signal · w=0",
    pr_pipeline_sub_legacy_gnn: "RTMScore, deprecated",
    pr_pipeline_value_unavailable: "Unavailable",
    pr_pipeline_sub_invalidated_legacy: "Invalidated legacy engine",
    pr_pipeline_sub_informative: "informative signal",
    pr_ev_exact_receptor: "Exact receptor",
    pr_ev_assumptions_registered: "Recorded assumptions",
    pr_docking_pose_counts: "Poses: {poses} · hotspots: {hotspots}",
    pr_pep_experimental_aviso:
      "Experimental: ESMFold predicts the peptide structure and its quality has not been validated in MolDesign. Vina then does the docking.",
    pr_docking_poses_generated: "Generated poses",
    pr_sar_key_change: "Key change",
    pr_sar_similarity: "Similarity",
    pr_alert_positive_badge: "POSITIVE HIGHLIGHT",
    pr_m5_protocol_label: "M5-Zn protocol",
    pr_m5_applied_profile: "M5-Zn profile applied",
    pr_m5_applicability_check: "Applicability check · M5-Zn",
    pr_signals_recorded_title: "Signals recorded in this run",
    pr_signals_effective_weights: "Recorded effective weights: {weights}",
    pr_signals_individual_weights: "Recorded individual weights: {weights}. Their effective normalization was not recorded.",
    pr_signals_weights_missing: "This run did not record its weights. The receptor family cannot reconstruct them.",
    pr_signals_missing_weighted: "Signals with recorded weights that produced no output: {signals}.",
    pr_pipeline_run_label: "Run protocol",
    pr_pipeline_used: "Protocol used: {protocol}",
    pr_pipeline_m4_description: "General evaluation protocol: gathers docking results and combines the available signals using the weights recorded for this run.",
    pr_pipeline_m5_description: "Protocol for zinc targets: combines the signals required by the specific profile of the evaluated structure.",
    pr_pipeline_not_recorded: "Protocol used: not recorded",
    pr_pipeline_details: "Protocol details",
    pr_pipeline_audit_review: "Audit result: review required.",
    pr_m5_composite_score: "Composite score",
    pr_ligand_species_ph: "Species docked at pH {ph}",
    pr_ligand_species_no_protonation: "Docked species: protonation not applied",
    pr_ligand_species_protonation_unknown: "Docked species: protonation record incomplete",
    pr_reg_paper_badge: "PAPER",
    pr_reg_corrigendum: "CORRIGENDUM",
    pr_reg_figures_replaced: "figures replaced",
    pr_reg_pre_registered_gate: "Pre-registered criterion.",
    pr_reg_protocol_label: "Protocol.",
    pr_reg_sealed_artifacts: "sealed artifacts",
    pr_reg_hash_count: "{count} hash values",
    pr_reg_gates_passed: "gates passed",
    pr_reg_versus: "vs",
    pr_reg_records_have_paper: "{paper} of {total} records have a drafted paper.",
    pr_reg_figures_replaced_sentence: "Figures replaced.",
    pr_xai_feature_vina_best: "Vina affinity (best pose)",
    pr_xai_feature_contacts_cc: "C–C contacts (van der Waals)",
    pr_xai_feature_contacts_cn: "C–N contacts",
    pr_xai_feature_contacts_co: "C–O contacts",
    pr_xai_value_shap: "SHAP value",
    pr_xai_effect: "Effect",
    pr_xai_right_green: "right (green)",
    pr_xai_left_red: "left (red)",
    pr_xai_feature_mw: "Molecular weight (MW)",

    pr_xai_shap_nativo: "NATIVE XGBOOST SHAP",
    pr_xai_abejas_a: "Directional beeswarm plot. Features toward the",
    pr_xai_abejas_b: "raise the affinity; toward the",
    pr_xai_abejas_c: "they penalise it.",
    pr_xai_atencion_gnn: "GNN attention (RTMScore)",
    pr_xai_mapa_hotspots: "HOTSPOT MAP",
    pr_xai_topologia: "2D topology",
    pr_xai_generando: "Generating projection…",
    pr_xai_farmacoforos: "Pharmacophore breakdown",
    pr_xai_sin_datos: "No explainability data.",
    pr_xai_shap_poblara:
      "The native SHAP engine will fill this area once a ligand evaluation "
      + "completes successfully.",
    pr_xai_dominio: "Applicability domain",
    pr_xai_fuera_dominio: "✗ Outside the domain",

    pr_mot_clasico: "CLASSIC",
    pr_mot_clasico_d:
      "Standard docking engine. Exhaustiveness=8. ~20 s per ligand.",
    pr_mot_rapido: "FAST",
    pr_mot_rapido_d:
      "Smart sampling, 2–3× faster than Vina. Same accuracy.",
    pr_mot_difusion: "DIFFUSION",
    pr_mot_difusion_d:
      "Generative diffusion docking (Corso et al. ICLR 2023).",
    pr_mot_peptido:
      "It is enabled when a peptide is detected (≥3 C(=O)N bonds) or when one of "
      + "these engines is selected manually.",
    pr_mot_aviso_vina:
      "With Vina selected, you will only see a notice if the molecule looks like "
      + "a peptide.",
    pr_mot_precision_completa: "Full precision",
    pr_mot_precision_media: "Half precision (CUDA)",

    // ── Selectividad ──────────────────────────────────────────────
    pr_sel_sin_evaluacion: "there is no evaluation to attach the panel to",

    // ── Timeline ──────────────────────────────────────────────────
    pr_timeline_etapas: "stages",
  },
};
