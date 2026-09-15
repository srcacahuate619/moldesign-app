// =====================================================================
// Paneles — lo que queda: métricas, visores, avisos y ajustes
// =====================================================================
//
// Es la cola larga: treinta y tantos componentes con entre una y once cadenas
// cada uno. Van juntos porque ninguno justifica su propio módulo y porque
// comparten el mismo trabajo: poner un número en su sitio.
//
// LA FRASE MÁS IMPORTANTE DEL MÓDULO, y la que fija el tono de todas:
//
//   «AutoDock Vina devuelve un score empírico para ordenar poses dentro de la
//    caja declarada. No equivale a energía libre experimental, afinidad medida
//    ni validación clínica.»
//
// «No equivale a» es una identidad negada, no una advertencia. En inglés, «It is
// not equivalent to» — nunca «should not be confused with», que deja la puerta
// abierta a que alguien sí lo confunda y sea culpa suya.
//
// Y las tres de M5-Zn, PAINS y el visor sin WebGL dicen, cada una a su manera,
// «esto no cambia lo que ya tienes». Esa tranquilidad es su función.

import type { ModuloDeTraduccion } from "./index";

export const paneles: ModuloDeTraduccion = {
  es: {
    // ── Limitaciones y metodología ────────────────────────────────
    pn_limitaciones: "Limitaciones y metodología",
    pn_vina_devuelve: "AutoDock Vina devuelve un",
    pn_score_empirico: "score empírico",
    pn_vina_no_equivale:
      "para ordenar poses dentro de la caja declarada. No equivale a energía libre "
      + "experimental, afinidad medida ni validación clínica.",
    pn_rescoring_dominio:
      "XGBoost, CL-GNN y otras señales de rescoring sólo se interpretan cuando el "
      + "perfil declara modelo, pesos, cohorte y dominio de aplicabilidad. Fuera de "
      + "dominio prevalece la observación de Vina y la interpretación puede quedar "
      + "en revisión.",
    pn_admet_descriptores:
      "Las propiedades ADMET, drug-likeness y accesibilidad sintética son "
      + "descriptores o heurísticas computacionales. No garantizan absorción, "
      + "seguridad, actividad ni que una síntesis sea viable en laboratorio.",
    pn_ums_abstencion:
      "UMS se integra únicamente en perfiles M5-Zn exactos. Si falta un componente "
      + "o la diana está fuera del perfil, el resultado correcto es una abstención; "
      + "no se redistribuyen pesos ni se fabrica un score.",
    pn_prioriza_no_sustituye:
      "Un resultado computacional prioriza qué revisar después. No sustituye "
      + "controles positivos, negativos y neutrales ni validación experimental "
      + "independiente.",

    // ── Expediente de la corrida ──────────────────────────────────
    pn_expediente: "Expediente de la corrida",
    pn_pregunta_dossier: "Pregunta del dossier",
    pn_pregunta_dossier_texto:
      "¿Qué evidencia produjo esta corrida, qué controles superó, qué "
      + "incertidumbres permanecen y qué es justificable hacer después?",
    pn_no_califica:
      "No califica si la molécula es un buen fármaco ni estima una probabilidad "
      + "de éxito.",
    pn_revisar_controles: "Revisar controles físicos y poses",
    pn_matriz_evidencia: "Matriz de evidencia",
    pn_identidad_sellada: "Identidad y protocolo sellados con esta corrida",
    pn_no_registrado_corrida: "No registrado en esta corrida.",
    pn_sin_incertidumbres:
      "No se registraron incertidumbres adicionales a las limitaciones generales "
      + "del protocolo.",

    // ── Catálogo de receptores ────────────────────────────────────
    pn_catalogo_titulo: "Catálogo de receptores",
    pn_catalogo_sub:
      "Selecciona una estructura biológica para la simulación de acoplamiento "
      + "molecular",
    pn_familia_quimica: "Familia química",
    pn_familia_terapeutica: "Familia terapéutica",
    pn_comunidad_cientifica: "Comunidad científica",
    pn_sin_receptores: "No se encontraron receptores en esta sección",
    pn_calibracion: "Calibración",
    pn_resolucion: "Resolución",
    pn_cerrar_catalogo: "Cerrar catálogo de receptores",
    pn_buscar_receptor: "Buscar por PDB ID, nombre de la proteína o familia…",
    pn_targets_comunidad: "Targets de la comunidad",

    // ── Menú de opciones ──────────────────────────────────────────
    pn_sonidos: "Sonidos de interfaz",
    pn_volumen_sonidos: "Volumen de los sonidos de interfaz",
    pn_exportar_json: "Exportar bioteca como JSON",
    pn_exportar_csv: "Exportar bioteca como CSV",
    pn_legal_info: "Legal e información",
    pn_acerca_de: "Acerca de MolDesign",
    pn_como_construido: "Cómo está construido",
    pn_acerca_intro:
      "Aquí se explican funciones y créditos. Las condiciones jurídicas completas "
      + "viven en Licencias.",
    pn_capacidades_desktop:
      "Capacidades reales de la edición Desktop y su procedencia.",
    pn_codigo_fuente: "Código fuente",
    pn_cerrar_acerca: "Cerrar Acerca de MolDesign",
    pn_areas_stack: "Áreas del stack",
    pn_ruta_pdf: "Ruta de descarga de PDF e informes",
    pn_ruta_pdf_detalle:
      "Directorio local donde se guardarán los informes científicos y certificados "
      + "PDF.",
    pn_datos_eliminados:
      "✓ Datos locales eliminados. Por favor, reinicia la aplicación.",

    // ── Propiedades y filtros ─────────────────────────────────────
    pn_propiedades: "Propiedades fisicoquímicas",
    pn_propiedades_rdkit:
      "Calculadas con RDKit. Valores reales, no estimaciones de IA. Toca una "
      + "propiedad para aprender más.",
    pn_alertas_sa: "Alertas de accesibilidad (SA)",
    pn_atomos_pesados: "Átomos pesados",
    pn_absorcion_intestinal: "Absorción intestinal",
    pn_propiedades_fq: "Propiedades fisicoquímicas",
    pn_contexto_scoring: "Contexto de scoring",
    pn_filtros_farmacologicos: "Filtros farmacológicos",
    pn_sin_datos_simulacion:
      "Sin datos. Ejecuta una simulación para extraer los coeficientes "
      + "fisicoquímicos detallados.",
    pn_puedes_calcularlo: "Puedes calcularlo ahora desde Análisis avanzado → ADMET",
    pn_solo_smiles_no_repite:
      ": no hace falta repetir el acoplamiento, porque sólo depende del SMILES.",
    pn_reactividad_sistemica: "Señales de reactividad sistémica:",
    pn_reactividad_tabpfn:
      "Señales de reactividad sistémica producidas por TabPFN; requieren "
      + "validación experimental.",
    pn_toxicidad_sin_evaluar:
      "— Sin evaluar: el clasificador de toxicidad no corrió en este equipo.",
    pn_sin_alertas_reactividad:
      "✓ Sin alertas de reactividad sistémica identificadas por TabPFN.",
    pn_perfil_sanguineo: "Perfil sanguíneo (índice)",

    // ── Drug-likeness y PAINS ─────────────────────────────────────
    pn_drug_likeness: "Perfil de reglas de drug-likeness",
    pn_peso_molecular_lipinski: "Peso molecular: se evalúa en Lipinski/Ghose",
    pn_pains_detectado:
      "Esta molécula contiene subestructuras que suelen dar falsos positivos en "
      + "experimentos. Se recomienda validación adicional antes de considerarla un "
      + "hallazgo real.",
    pn_pains_explicacion:
      "Los PAINS son falsos positivos frecuentes en ensayos biológicos (Baell y "
      + "Holloway, 2010). Se recomienda validación experimental exhaustiva antes de "
      + "considerar esta molécula como hit.",
    pn_sin_pains:
      "Sin patrón PAINS detectado (no descarta actividad ni riesgo)",
    pn_red_lipinski: "Red de viabilidad (Lipinski)",
    pn_limite_ideal: "Límite ideal",

    // ── Puntuación ────────────────────────────────────────────────
    pn_puntuacion: "Puntuación del compuesto",
    pn_heuristica_compuesta:
      "Heurística compuesta prioritaria (0–100). No equivale a validación in vitro.",
    pn_ef_ligando: "Ef. de ligando",
    pn_inicia_sesion: "Inicia sesión",
    pn_para_guardar: "para guardar y certificar protocolos.",

    // ── Visores ───────────────────────────────────────────────────
    pn_3d_no_dibuja: "La vista 3D no se puede dibujar en este equipo",
    pn_3d_datos_intactos:
      "Los datos de esta pose y sus descargas no dependen del visor: siguen "
      + "disponibles, y el archivo descargado se abre en cualquier visor externo.",
    pn_3d_aparece_al_terminar:
      "La vista 3D aparece cuando termina el acoplamiento",
    pn_sin_estructura: "Sin estructura para visualizar",
    pn_atomos: "átomos",
    pn_residuos_sitio: "residuos del sitio activo",
    pn_selecciona_residuo: "Selecciona un residuo para ver su función química",
    pn_caja_acoplamiento: "Caja de acoplamiento",
    pn_evaluacion_no_afectada: "Tu evaluación no se ve afectada.",
    pn_sin_webgl:
      "El docking, el rescoring, la validez física de las poses y el dossier se "
      + "calculan en el procesador y no dependen del visor. Lo único que no podrás "
      + "hacer aquí es mirar la estructura en 3D; las poses se descargan y se abren "
      + "en cualquier visor externo.",
    pn_3d_software: "3D por software · girar la escena irá lento",
    pn_identificar_diseno: "Identificar mi diseño",
    pn_sin_vista_previa: "Sin vista previa",
    pn_recuperando_poses: "Recuperando receptor y poses de la corrida…",
    pn_cerrar_comparador: "Cerrar comparador de poses",

    // ── Poses y hotspots ──────────────────────────────────────────
    pn_selecciona_pose:
      "Selecciona una pose para revisar sus controles físicos individuales.",
    pn_sin_poses_aun: "Sin poses disponibles todavía.",
    pn_hotspots_sitio: "Hotspots del sitio activo",
    pn_hotspots_explicacion:
      "Residuos clave del bolsillo de unión. Los marcados en púrpura fueron "
      + "contactados por el ligando (hotspot hit).",
    pn_sin_hotspots: "Sin hotspots definidos para este target.",
    pn_ver_controles_pose: "Ver controles físicos de la pose #{rango}",

    // ── Estado del ligando ────────────────────────────────────────
    pn_lo_que_escribiste: "Lo que escribiste",
    pn_no_es_la_que_escribiste:
      "La molécula acoplada no es la que escribiste.",
    pn_alternativas_descartadas:
      "Las alternativas descartadas no se evaluaron. Los descriptores de abajo "
      + "(MW, LogP, TPSA) se calculan sobre la forma neutra que escribiste, no "
      + "sobre la especie acoplada.",
    pn_ph_no_cambia:
      "A pH 7.4 la especie no cambia respecto a lo que escribiste: se acopló tal "
      + "cual.",

    // ── SAR ───────────────────────────────────────────────────────
    pn_sar_titulo: "Análisis SAR — estructura-actividad",
    pn_sar_comparables: "Moléculas estructuralmente comparables",
    pn_sar_consultando: "Consultando análogos estructurales…",
    pn_sar_sin_analogos:
      "Sin análogos disponibles aún — evalúa más moléculas contra el mismo "
      + "receptor para poblar el SAR.",

    // ── Variante de receptor ──────────────────────────────────────
    pn_variante_titulo: "Nueva variante de preparación",
    pn_variante_nombre: "Nombre de la variante",
    pn_variante_metales: "Metales y cofactores que deben conservarse",
    pn_variante_separados:
      "Separados por comas. Las aguas se eliminan en este MVP; la preparación real "
      + "y sus hashes se registrarán al crear la variante.",

    // ── Comparador ────────────────────────────────────────────────
    pn_comparador_titulo: "Comparador de ligandos",
    pn_comparador_no_cargo:
      "No se pudieron cargar la pose y el receptor de esta molécula. El archivo "
      + "puede no estar disponible o no estar autorizado para tu cuenta.",
    pn_no_comparables: "Estas moléculas no son comparables",
    pn_no_comparables_detalle:
      "Las propiedades fisicoquímicas de cada molécula se muestran arriba y siguen "
      + "siendo válidas por separado. Lo que no puede calcularse es la diferencia "
      + "entre ellas.",

    // ── Soporte y donación ────────────────────────────────────────
    pn_soporte_error:
      "¿Encontraste un error o tienes una propuesta? Escríbenos e incluye los "
      + "pasos para reproducirlo.",
    pn_apoyar: "Apoyar el proyecto",
    pn_apoyar_detalle:
      "MolDesign es software libre. Si te resulta útil, puedes apoyar su "
      + "mantenimiento con una donación en SOL.",
    pn_solana_opcional:
      "Red Solana. La certificación y las donaciones son funciones opcionales.",

    // ── Traspaso del invitado ─────────────────────────────────────
    pn_traspaso_titulo: "Trabajo hecho como invitado",
    pn_traspaso_tienes:
      "Tienes trabajo hecho como invitado en este equipo",
    pn_traspaso_ahora_no: "Ahora no",
    pn_traspaso_sin_batch: "Los cribados de Batch no entran aquí todavía.",

    // ── Selectividad y MM-GBSA en el panel de configuración ───────
    pn_panel_selectividad: "Panel de selectividad",
    pn_panel_selectividad_d: "Acopla contra el panel declarado de anti-targets",
    pn_catalogo: "CATÁLOGO",
    pn_reevaluacion_mmgbsa: "Reevaluación MM-GBSA",
    pn_admet_optin:
      "Experimental · opt-in. Produce señales ADMET (hERG, CYP, BBB) en local; la "
      + "primera carga puede tardar varios minutos, sobre todo en una máquina "
      + "virtual. No es necesaria para el docking.",

    // ── Recuperación del runner ───────────────────────────────────
    pn_cargando_pro: "Cargando evaluación pro…",
    pn_resultado_limpiado:
      "El resultado visible se limpió al cambiar de sesión. La corrida terminada "
      + "conserva su identificador; vuelve a autenticarte para recuperarla.",
    pn_conexion_perdida:
      "Se perdió la conexión con el servidor de evaluación.",
    pn_no_se_sabe_como_termino: "No se sabe cómo terminó la tarea",
    pn_puede_seguir_corriendo:
      ": puede seguir corriendo. Su identificador se ha conservado.",

    // ── Avisos, dossier y resto ───────────────────────────────────
    pn_advertencias: "⚠ Advertencias científicas",
    pn_notas_integridad: "Notas de integridad de datos",
    pn_sin_advertencias_simulacion:
      "✓ No se han registrado advertencias ni fallos para esta simulación.",
    pn_dossier_no_cargo: "No se pudo cargar el dossier",
    pn_dossier_sin_registro:
      "La integridad de este dossier aún no está registrada",
    pn_dossier_vista_previa: "Vista previa del dossier PDF",
    pn_m5zn_titulo: "Protocolo M5-Zn · metaloenzimas de zinc",
    pn_m5zn_no_entra:
      "Este número no entra en el score total, ni en el ranking, ni en la "
      + "recomendación, ni en el veredicto. Se muestra para que pueda auditarse.",
    pn_reproducibilidad: "Parámetros clave para reproducir este resultado.",
    pn_spearman_pendiente: "(Spearman: pendiente de recálculo)",
    pn_editor_no_cargo: "No se pudo cargar el editor",
    pn_editor_smiles: "Edita o copia el SMILES aquí",
    pn_verificar_instalacion: "Verificar instalación",
    pn_descargas_huggingface:
      "Las descargas pesadas se obtienen bajo demanda desde Hugging Face. Revisa "
      + "el origen y la licencia de cada módulo antes de instalarlo.",
    pn_modelos_sin_descargar:
      "Algunos modelos de IA aún no se han descargado. Algunas funciones pueden no "
      + "estar disponibles.",
    pn_navegacion: "Navegación",
    pn_evaluacion_mayus: "EVALUACIÓN",
    pn_acelerador: "Acelerador de partículas",
    pn_simulacion_visual: "Simulación visual",
    pn_registro_telemetria: "Registro de telemetría",
    pn_esperando_pipeline: "Esperando datos del pipeline…",
    pn_config_parametros: "Configuración de parámetros",
    pn_cargando_sesion: "Cargando sesión…",
    pn_tamano: "Tamaño:",
    pn_descarga_de: "Descarga de {nombre}",
    pn_benzaldehido: "C₇H₆O · Benzaldehído · Pipeline tecnológico",
  },
  en: {
    pn_limitaciones: "Limitations and methodology",
    pn_vina_devuelve: "AutoDock Vina returns an",
    pn_score_empirico: "empirical score",
    pn_vina_no_equivale:
      "for ranking poses inside the declared box. It is not equivalent to "
      + "experimental free energy, to a measured affinity, or to clinical "
      + "validation.",
    pn_rescoring_dominio:
      "XGBoost, CL-GNN and other rescoring signals are only interpreted when the "
      + "profile declares model, weights, cohort and applicability domain. Outside "
      + "the domain, the Vina observation prevails and the interpretation may be "
      + "left under review.",
    pn_admet_descriptores:
      "ADMET properties, drug-likeness and synthetic accessibility are "
      + "computational descriptors or heuristics. They do not guarantee absorption, "
      + "safety, activity, or that a synthesis is feasible in the laboratory.",
    pn_ums_abstencion:
      "UMS is integrated only in exact M5-Zn profiles. If a component is missing "
      + "or the target falls outside the profile, the correct result is an "
      + "abstention; weights are not redistributed and no score is fabricated.",
    pn_prioriza_no_sustituye:
      "A computational result prioritises what to review next. It does not replace "
      + "positive, negative and neutral controls, nor independent experimental "
      + "validation.",

    pn_expediente: "Run file",
    pn_pregunta_dossier: "The dossier's question",
    pn_pregunta_dossier_texto:
      "What evidence did this run produce, which controls did it pass, which "
      + "uncertainties remain, and what is it justifiable to do next?",
    pn_no_califica:
      "It does not grade whether the molecule is a good drug and does not estimate "
      + "a probability of success.",
    pn_revisar_controles: "Review physical controls and poses",
    pn_matriz_evidencia: "Evidence matrix",
    pn_identidad_sellada: "Identity and protocol sealed with this run",
    pn_no_registrado_corrida: "Not recorded in this run.",
    pn_sin_incertidumbres:
      "No uncertainties beyond the general limitations of the protocol were "
      + "recorded.",

    pn_catalogo_titulo: "Receptor catalogue",
    pn_catalogo_sub:
      "Select a biological structure for the molecular docking simulation",
    pn_familia_quimica: "Chemical family",
    pn_familia_terapeutica: "Therapeutic family",
    pn_comunidad_cientifica: "Scientific community",
    pn_sin_receptores: "No receptors were found in this section",
    pn_calibracion: "Calibration",
    pn_resolucion: "Resolution",
    pn_cerrar_catalogo: "Close the receptor catalogue",
    pn_buscar_receptor: "Search by PDB ID, protein name or family…",
    pn_targets_comunidad: "Community targets",

    pn_sonidos: "Interface sounds",
    pn_volumen_sonidos: "Interface sound volume",
    pn_exportar_json: "Export library as JSON",
    pn_exportar_csv: "Export library as CSV",
    pn_legal_info: "Legal and information",
    pn_acerca_de: "About MolDesign",
    pn_como_construido: "How it is built",
    pn_acerca_intro:
      "Features and credits are explained here. The full legal terms live under "
      + "Licences.",
    pn_capacidades_desktop:
      "Real capabilities of the Desktop edition and where they come from.",
    pn_codigo_fuente: "Source code",
    pn_cerrar_acerca: "Close About MolDesign",
    pn_areas_stack: "Stack areas",
    pn_ruta_pdf: "Download path for PDFs and reports",
    pn_ruta_pdf_detalle:
      "Local directory where scientific reports and PDF certificates will be "
      + "saved.",
    pn_datos_eliminados:
      "✓ Local data deleted. Please restart the application.",

    pn_propiedades: "Physicochemical properties",
    pn_propiedades_rdkit:
      "Calculated with RDKit. Real values, not AI estimates. Tap a property to "
      + "learn more.",
    pn_alertas_sa: "Accessibility alerts (SA)",
    pn_atomos_pesados: "Heavy atoms",
    pn_absorcion_intestinal: "Intestinal absorption",
    pn_propiedades_fq: "Physicochemical properties",
    pn_contexto_scoring: "Scoring context",
    pn_filtros_farmacologicos: "Pharmacological filters",
    pn_sin_datos_simulacion:
      "No data. Run a simulation to extract the detailed physicochemical "
      + "coefficients.",
    pn_puedes_calcularlo:
      "You can calculate it now from Advanced analysis → ADMET",
    pn_solo_smiles_no_repite:
      ": there is no need to repeat the docking, because it depends on the SMILES "
      + "alone.",
    pn_reactividad_sistemica: "Systemic reactivity signals:",
    pn_reactividad_tabpfn:
      "Systemic reactivity signals produced by TabPFN; they require experimental "
      + "validation.",
    pn_toxicidad_sin_evaluar:
      "— Not evaluated: the toxicity classifier did not run on this machine.",
    pn_sin_alertas_reactividad:
      "✓ No systemic reactivity alerts identified by TabPFN.",
    pn_perfil_sanguineo: "Blood profile (index)",

    pn_drug_likeness: "Drug-likeness rule profile",
    pn_peso_molecular_lipinski:
      "Molecular weight: evaluated under Lipinski/Ghose",
    pn_pains_detectado:
      "This molecule contains substructures that often give false positives in "
      + "experiments. Additional validation is recommended before treating it as a "
      + "real finding.",
    pn_pains_explicacion:
      "PAINS are frequent false positives in biological assays (Baell and "
      + "Holloway, 2010). Thorough experimental validation is recommended before "
      + "treating this molecule as a hit.",
    pn_sin_pains:
      "No PAINS pattern detected (this rules out neither activity nor risk)",
    pn_red_lipinski: "Viability web (Lipinski)",
    pn_limite_ideal: "Ideal limit",

    pn_puntuacion: "Compound score",
    pn_heuristica_compuesta:
      "Priority composite heuristic (0–100). It is not equivalent to in vitro "
      + "validation.",
    pn_ef_ligando: "Ligand eff.",
    pn_inicia_sesion: "Sign in",
    pn_para_guardar: "to save and certify protocols.",

    pn_3d_no_dibuja: "The 3D view cannot be drawn on this machine",
    pn_3d_datos_intactos:
      "The data of this pose and its downloads do not depend on the viewer: they "
      + "remain available, and the downloaded file opens in any external viewer.",
    pn_3d_aparece_al_terminar: "The 3D view appears when the docking finishes",
    pn_sin_estructura: "No structure to display",
    pn_atomos: "atoms",
    pn_residuos_sitio: "active-site residues",
    pn_selecciona_residuo: "Select a residue to see its chemical function",
    pn_caja_acoplamiento: "Docking box",
    pn_evaluacion_no_afectada: "Your evaluation is not affected.",
    pn_sin_webgl:
      "The docking, the rescoring, the physical validity of the poses and the "
      + "dossier are all calculated on the processor and do not depend on the "
      + "viewer. The only thing you will not be able to do here is look at the "
      + "structure in 3D; the poses download and open in any external viewer.",
    pn_3d_software: "Software 3D · rotating the scene will be slow",
    pn_identificar_diseno: "Identify my design",
    pn_sin_vista_previa: "No preview",
    pn_recuperando_poses: "Recovering receptor and poses from the run…",
    pn_cerrar_comparador: "Close the pose comparator",

    pn_selecciona_pose:
      "Select a pose to review its individual physical controls.",
    pn_sin_poses_aun: "No poses available yet.",
    pn_hotspots_sitio: "Active-site hotspots",
    pn_hotspots_explicacion:
      "Key residues of the binding pocket. The ones marked in purple were "
      + "contacted by the ligand (hotspot hit).",
    pn_sin_hotspots: "No hotspots defined for this target.",
    pn_ver_controles_pose: "See the physical controls of pose #{rango}",

    pn_lo_que_escribiste: "What you typed",
    pn_no_es_la_que_escribiste:
      "The docked molecule is not the one you typed.",
    pn_alternativas_descartadas:
      "The discarded alternatives were not evaluated. The descriptors below (MW, "
      + "LogP, TPSA) are calculated on the neutral form you typed, not on the "
      + "docked species.",
    pn_ph_no_cambia:
      "At pH 7.4 the species does not change from what you typed: it was docked as "
      + "it is.",

    pn_sar_titulo: "SAR analysis — structure-activity",
    pn_sar_comparables: "Structurally comparable molecules",
    pn_sar_consultando: "Looking up structural analogues…",
    pn_sar_sin_analogos:
      "No analogues available yet — evaluate more molecules against the same "
      + "receptor to populate the SAR.",

    pn_variante_titulo: "New preparation variant",
    pn_variante_nombre: "Variant name",
    pn_variante_metales: "Metals and cofactors that must be kept",
    pn_variante_separados:
      "Comma-separated. Waters are removed in this MVP; the real preparation and "
      + "its hashes will be recorded when the variant is created.",

    pn_comparador_titulo: "Ligand comparator",
    pn_comparador_no_cargo:
      "The pose and the receptor of this molecule could not be loaded. The file "
      + "may be unavailable or not authorised for your account.",
    pn_no_comparables: "These molecules are not comparable",
    pn_no_comparables_detalle:
      "The physicochemical properties of each molecule are shown above and remain "
      + "valid separately. What cannot be calculated is the difference between "
      + "them.",

    pn_soporte_error:
      "Found a bug or have a suggestion? Write to us and include the steps to "
      + "reproduce it.",
    pn_apoyar: "Support the project",
    pn_apoyar_detalle:
      "MolDesign is free software. If you find it useful, you can support its "
      + "maintenance with a donation in SOL.",
    pn_solana_opcional:
      "Solana network. Certification and donations are optional features.",

    pn_traspaso_titulo: "Work done as a guest",
    pn_traspaso_tienes: "You have work done as a guest on this machine",
    pn_traspaso_ahora_no: "Not now",
    pn_traspaso_sin_batch: "Batch screens do not come across here yet.",

    pn_panel_selectividad: "Selectivity panel",
    pn_panel_selectividad_d: "Docks against the declared anti-target panel",
    pn_catalogo: "CATALOGUE",
    pn_reevaluacion_mmgbsa: "MM-GBSA re-evaluation",
    pn_admet_optin:
      "Experimental · opt-in. It produces ADMET signals (hERG, CYP, BBB) locally; "
      + "the first load can take several minutes, especially in a virtual machine. "
      + "It is not needed for docking.",

    pn_cargando_pro: "Loading pro evaluation…",
    pn_resultado_limpiado:
      "The visible result was cleared when the session changed. The finished run "
      + "keeps its identifier; sign in again to recover it.",
    pn_conexion_perdida:
      "The connection to the evaluation server was lost.",
    pn_no_se_sabe_como_termino: "It is not known how the task ended",
    pn_puede_seguir_corriendo:
      ": it may still be running. Its identifier has been kept.",

    pn_advertencias: "⚠ Scientific warnings",
    pn_notas_integridad: "Data integrity notes",
    pn_sin_advertencias_simulacion:
      "✓ No warnings or failures were recorded for this simulation.",
    pn_dossier_no_cargo: "The dossier could not be loaded",
    pn_dossier_sin_registro:
      "The integrity of this dossier is not recorded yet",
    pn_dossier_vista_previa: "PDF dossier preview",
    pn_m5zn_titulo: "M5-Zn protocol · zinc metalloenzymes",
    pn_m5zn_no_entra:
      "This number does not enter the total score, the ranking, the "
      + "recommendation or the verdict. It is shown so that it can be audited.",
    pn_reproducibilidad: "Key parameters to reproduce this result.",
    pn_spearman_pendiente: "(Spearman: pending recalculation)",
    pn_editor_no_cargo: "The editor could not be loaded",
    pn_editor_smiles: "Edit or copy the SMILES here",
    pn_verificar_instalacion: "Verify installation",
    pn_descargas_huggingface:
      "Heavy downloads are fetched on demand from Hugging Face. Check the origin "
      + "and the licence of each module before installing it.",
    pn_modelos_sin_descargar:
      "Some AI models have not been downloaded yet. Some features may be "
      + "unavailable.",
    pn_navegacion: "Navigation",
    pn_evaluacion_mayus: "EVALUATION",
    pn_acelerador: "Particle accelerator",
    pn_simulacion_visual: "Visual simulation",
    pn_registro_telemetria: "Telemetry log",
    pn_esperando_pipeline: "Waiting for pipeline data…",
    pn_config_parametros: "Parameter configuration",
    pn_cargando_sesion: "Loading session…",
    pn_tamano: "Size:",
    pn_descarga_de: "Download of {nombre}",
    pn_benzaldehido: "C₇H₆O · Benzaldehyde · Technology pipeline",
  },
};
