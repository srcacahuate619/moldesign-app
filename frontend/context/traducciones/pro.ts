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
    pr_refinar_mmgbsa: "Refinar una pose con MM-GBSA",
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

    // ── Preparación de la corrida ─────────────────────────────────
    pr_preparacion_titulo: "Preparación de la corrida",
    pr_preparacion_explicacion:
      "Comprobación previa sobre los archivos reales. No ejecuta el acoplamiento "
      + "y no emite ningún veredicto sobre la molécula.",
    pr_revisada_aceptada: "Revisada y aceptada por ti",
    pr_marcar_revisada: "Marcar como revisada",
    pr_conformero_unico: "Confórmero único",
    pr_inputs_cambiaron:
      "Los inputs cambiaron desde la última comprobación, así que ya no describe "
      + "lo que se ejecutaría. Vuelve a comprobar la preparación.",
    pr_resumen_guardado:
      "Resumen guardado con el caso. Vuelve a comprobar para recuperar el detalle "
      + "de controles y el diff actualizado.",
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
    pr_sel_titulo: "PANEL DE SELECTIVIDAD 1 A 1 (REGULATORIO)",
    pr_sel_en_background:
      "El pipeline está evaluando el panel de selectividad en background. Los "
      + "resultados aparecerán aquí automáticamente al terminar (sin bloquear la "
      + "evaluación).",
    pr_sel_resumen: "Resumen de selectividad (in silico)",
    pr_sel_sin_conclusion:
      "0 umbrales rebasados en el panel; esto no constituye una conclusión de "
      + "seguridad.",
    pr_sel_anti_targets: "Anti-targets del panel (5 receptores)",
    pr_sel_umbral_minimo: "Umbral mínimo:",
    pr_sel_saber_mas: "Saber más",
    pr_sel_sin_evaluar: "Sin evaluar",
    pr_sel_concentracion: "Concentración implicada por el score:",
    pr_sel_no_es_ki: "Esa concentración no es una Ki ni una IC50.",
    pr_sel_funcion_biologica: "Función biológica y mecanismo",
    pr_sel_relevancia_clinica: "Relevancia clínica y riesgo farmacológico",
    pr_sel_optimizacion: "Optimización química medicinal (SAR)",

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
  },
  en: {
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
    pr_refinar_mmgbsa: "Refine a pose with MM-GBSA",
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
      "give the (X, Y, Z) coordinates of the box centre.",
    pr_nombre_receptor: "Receptor name",
    pr_tamano_caja: "Box size (grid size)",
    pr_automatizacion: "Smart automation",
    pr_servidor_rastreara:
      "The server will scan the PDB structure and compute a spatial centre on the "
      + "main co-crystallised ligand.",
    pr_compartir_comunidad: "Share with the community",
    pr_cerrar_subida: "Close receptor upload",

    pr_preparacion_titulo: "Run preparation",
    pr_preparacion_explicacion:
      "A pre-flight check over the real files. It does not run the docking and "
      + "issues no verdict about the molecule.",
    pr_revisada_aceptada: "Reviewed and accepted by you",
    pr_marcar_revisada: "Mark as reviewed",
    pr_conformero_unico: "Single conformer",
    pr_inputs_cambiaron:
      "The inputs changed since the last check, so it no longer describes what "
      + "would run. Check the preparation again.",
    pr_resumen_guardado:
      "Summary stored with the case. Check again to recover the control detail "
      + "and the updated diff.",
    pr_ligando_canonico: "Ligand (canonical)",
    pr_de_la_fuente: "From the source to the preparer's input",
    pr_especies_retiradas: "Chemical species identified as removed",
    pr_codigos_residuo:
      "The codes correspond to the residue names in the PDB file; the count is "
      + "the number of atom records removed.",
    pr_politica_preparacion: "Preparation policy for this route",
    pr_metodo: "Method:",
    pr_aguas_eliminadas: "All of them are removed before docking",
    pr_cofactores_reconocidos: "Recognised organic cofactors:",
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
    pr_sel_titulo: "ONE-TO-ONE SELECTIVITY PANEL (REGULATORY)",
    pr_sel_en_background:
      "The pipeline is evaluating the selectivity panel in the background. The "
      + "results will appear here automatically when it finishes (without "
      + "blocking the evaluation).",
    pr_sel_resumen: "Selectivity summary (in silico)",
    pr_sel_sin_conclusion:
      "0 thresholds exceeded in the panel; this does not constitute a safety "
      + "conclusion.",
    pr_sel_anti_targets: "Panel anti-targets (5 receptors)",
    pr_sel_umbral_minimo: "Minimum threshold:",
    pr_sel_saber_mas: "Learn more",
    pr_sel_sin_evaluar: "Not evaluated",
    pr_sel_concentracion: "Concentration implied by the score:",
    pr_sel_no_es_ki: "That concentration is neither a Ki nor an IC50.",
    pr_sel_funcion_biologica: "Biological function and mechanism",
    pr_sel_relevancia_clinica: "Clinical relevance and pharmacological risk",
    pr_sel_optimizacion: "Medicinal chemistry optimisation (SAR)",

    pr_xai_shap_nativo: "NATIVE XGBOOST SHAP",
    pr_xai_abejas_a: "Directional beeswarm plot. Features towards the",
    pr_xai_abejas_b: "raise the affinity; towards the",
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
  },
};
