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
    pn_molcy_source_credit: "MolDesign · código fuente: github.com/srcacahuate619/moldesign-molcy",
    pe_bloqueado_desc: "Falta evidencia imprescindible o hay un defecto estructural bloqueante.",
    pe_accion: "Acción recomendada",
    pe_ultima_completada: "Se audita la evaluación seleccionada; su identificador aparece arriba. Cambiarla no modifica el caso.",
    pe_hueco_estado: 'Hueco del esqueleto junto al sitio: el sistema está bloqueado hasta reparar o cambiar la estructura.',
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
    pn_receptor_subir: "Subir receptor",
    pn_receptor_oficiales: "Receptores oficiales",
    pn_mis_receptores: "Mis receptores",
    pn_targets_count: "{n} objetivos",
    pn_receptor_activo: "Activo",
    pn_organismo_humano: "Humano",
    pn_variante_reproducible: "Variante reproducible",
    pn_variante_crear: "Crear variante",
    pn_variante_no_disponible:
      "Este receptor no se puede preparar: no puede ser la base de una variante, que sólo cambia los metales y cofactores que se conservan.",
    pn_receptor_privado: "Privado",
    pn_compartiendo: "Compartiendo",
    pn_compartir: "Compartir",
    pn_catalogo_sub:
      "Selecciona una estructura biológica para la simulación de acoplamiento "
      + "molecular",
    pn_familia_quimica: "Familia química",
    pn_familia_terapeutica: "Familia terapéutica",
    pn_comunidad_cientifica: "Comunidad científica",
    pn_sin_receptores: "No se encontraron receptores en esta sección",
    pn_calibracion: "Calibración",
    // SOL-03: el badge del selector mide readiness ESTRUCTURAL (preparado +
    // grid + hotspots), no respaldo predictivo. Se rotula como lo que mide;
    // la calibración predictiva la muestra el componente SC-9 compartido.
    pn_preparacion: "Preparación",
    pn_prep_listo: "Listo",
    pn_prep_revisar: "Revisar",
    pn_prep_sin_datos: "Sin datos",
    pn_no_disponible: "No disponible",
    pn_no_disponible_meeko: "La preparación automática (Meeko) no puede construir este receptor.",
    pn_detalle_tecnico: "Detalle técnico",
    pn_truncadas_en_sitio: "Cadenas laterales truncadas en el sitio: {n}",
    pn_todas: "Todas",
    pn_panel_por_defecto: "Panel por defecto",
    pn_ninguna: "Ninguna",
    pn_anti_selector: "Anti-dianas por familia",
    pn_anti_todas: "Todas las disponibles",
    pn_anti_recuento: "{n}/{total} disponibles seleccionadas",
    pn_anti_coste: "Cada anti-diana añade un acoplamiento por confórmero; con más de 8 puede aumentar mucho el tiempo.",
    pn_anti_pose: "El redocking no reprodujo la pose cristalográfica; el margen ΔΔG es orientativo.",
    pn_anti_excluidas: "Estas anti-dianas no están disponibles y se excluyen del envío al aplicar: {ids}. Revisa Parámetros de la evaluación.",
    pn_anti_guardadas: "Selección guardada",
    pn_anti_ausente: "Esta id guardada ya no existe en el panel.",
    pn_anti_sin_familia: "Sin familia declarada",
    pn_anti_cargando: "Consultando anti-dianas disponibles…",
    pn_anti_error: "No se pudo consultar el panel de anti-dianas. No se puede confirmar qué receptores están disponibles.",
    pn_anti_reintentar: "Reintentar",
    pn_anti_pedidas: "Anti-dianas solicitadas: {ids}",
    pn_anti_acopladas: "Anti-dianas acopladas: {ids}",
    pn_anti_cero: "Ninguna",
    pn_anti_truncadas: "{n} cadenas laterales incompletas se truncaron junto al sitio; la cavidad preparada pierde esos grupos.",
    pn_anti_panel_elegir: "Elegir anti-dianas",
    pn_anti_panel_cerrar: "Cerrar la lista",
    pn_anti_panel_ayuda: "Aquí aparecen las anti-dianas que seleccionas y los resultados anteriores. Seleccionar una anti-diana no inicia el cálculo.",
    pn_anti_panel_vacio: "No hay ninguna anti-diana elegida. Marca en el catálogo las que quieras evaluar.",
    pn_anti_catalogo: "Catálogo de anti-dianas",
    pn_anti_estructura_detalle: "Detalles de estructura",
    pn_anti_estructura_reservas: "Reservas de estructura",
    pn_anti_catalogo_total: "{n} en catálogo",
    pn_anti_catalogo_disponibles: "{n} disponibles",
    pn_anti_catalogo_no_disponibles: "{n} no disponibles",
    pn_anti_catalogo_ayuda: "Marca las anti-dianas que quieras añadir a tu panel. Cada una añade un acoplamiento.",
    pn_anti_buscar: "Buscar anti-diana",
    pn_anti_buscar_placeholder: "Nombre, gen o PDB",
    pn_anti_filtrar_familia: "Familia",
    pn_anti_todas_familias: "Todas las familias",
    pn_anti_resultados_busqueda: "Resultados en el catálogo: {n}",
    pn_anti_sin_coincidencias: "No hay coincidencias. Cambia la búsqueda o la familia.",
    pn_anti_seleccion_bloqueada: "La selección se mantiene fija mientras termina la evaluación en curso.",
    pn_anti_panel_seleccionadas: "Seleccionadas: {n}",
    pn_anti_panel_evaluadas: "Evaluadas de la selección: {n}",
    pn_anti_panel_anteriores: "Resultados anteriores: {n}",
    pn_anti_cobertura_registrada: "Evidencia del panel:",
    pn_anti_resultado_anterior: "Resultado anterior · fuera de la selección",
    pn_anti_evaluar_seleccionadas: "Evaluar seleccionadas ({n})",
    pn_anti_sin_ficha: "Esta anti-diana no tiene una ficha explicativa propia: aquí sólo se muestra el riesgo que declara el panel y su resultado.",
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
    pn_transparency: "Transparencia",
    pn_card_count: "{count} elementos",
    pn_licenses_notices: "Licencias y avisos",
    pn_capacidades_desktop:
      "Capacidades reales de la edición Desktop y su procedencia.",
    pn_codigo_fuente: "Código fuente",
    pn_cerrar_acerca: "Cerrar Acerca de MolDesign",
    pn_areas_stack: "Áreas del stack",
    pn_about_section_chemistry: "Química y docking",
    pn_about_section_scoring: "Scoring y modelos",
    pn_about_section_ai: "IA y lenguaje",
    pn_about_section_platform: "Plataforma y visualización",
    pn_about_section_sources: "Créditos y fuentes",
    pn_about_availability_included: "Incluido",
    pn_about_availability_optional: "Opcional",
    pn_about_availability_external: "Servicio externo",
    pn_about_availability_adapted: "Método adaptado",
    pn_about_card_moltalk_description:
      "La miniatura de Moldex que gira la pose top-1 y la vista 3D del editor nacen de su visor. "
      + "La idea es suya: adaptamos su método para alinear la geometría 3D con el dibujo 2D y "
      + "lo reimplementamos en código propio. No incluimos su código ni sus dependencias.",
    pn_about_card_moltalk_credit: "Dominic Fico · github.com/DomFico/moltalk",
    pn_about_kind_third_party: "Tercero",
    pn_about_kind_moldesign: "MolDesign",
    pn_about_kind_scientific_source: "Fuente científica",
    pn_about_card_vina_description: "Motor de docking que genera y puntúa poses ligando–receptor. Incluye vina_trace, una copia de Vina 1.2.7 que registra la búsqueda para la escena «Búsqueda» de Molcy.",
    pn_about_card_meeko_description: "Prepara ligandos y receptores para los formatos utilizados por AutoDock.",
    pn_about_card_rdkit_description: "Validación química, descriptores, fingerprints y conformaciones moleculares.",
    pn_about_card_open_babel_description: "Programa independiente que MolDesign ejecuta como herramienta de línea de órdenes para convertir PDBQT a SDF cuando la exportación del ligando falla. No se enlaza como biblioteca. El ejecutable empaquetado se identifica internamente como 3.1.0 porque la 3.1.1 fue una corrección de empaquetado que no actualizó la cadena; el valor medido vive en el manifiesto del paquete.",
    pn_about_card_open_babel_credit: "Open Babel contributors; empaquetado del wheel por Jinzhe Zeng",
    pn_about_card_openmm_description: "Viajan en el runtime. En 1.0.2 MM-GBSA está desactivado y la interfaz no ofrece ninguna ruta que los use.",
    pn_about_card_prolif_description: "Análisis de contactos e interacciones proteína–ligando sobre estructuras 3D.",
    pn_about_card_xtb_description: "Cálculos semiempíricos ejecutados como proceso independiente para descriptores cuánticos.",
    pn_about_card_xgboost_description: "Modelos tabulares de rescoring y explicación de contribuciones de sus variables.",
    pn_about_card_admet_description: "Predicciones computacionales de propiedades ADMET; no sustituyen validación experimental.",
    pn_about_card_tabpfn_description: "Viaja en el runtime con su licencia y su atribución; en 1.0.2 ninguna ruta de MolDesign lo usa.",
    pn_about_card_rtmscore_version: "snapshot integrado",
    pn_about_card_rtmscore_description: "Implementación de investigación para rescoring proteína–ligando. Su distribución permanece bloqueada hasta aclarar la licencia upstream.",
    pn_about_card_moldesign_models_name: "Modelos MolDesign",
    pn_about_card_moldesign_models_version: "manifiesto versionado",
    pn_about_card_moldesign_models_description: "Modelos y calibraciones propios con manifiestos, hashes y licencia separados del código.",
    pn_about_card_llama_description: "Servidor local que ejecuta modelos GGUF fuera del proceso principal de MolDesign.",
    pn_about_card_qwen_description: "Modelo local compatible con MolChat. Sus pesos tienen licencia propia y conservan su licencia de terceros.",
    pn_about_card_anthropic_description: "Integración opcional configurada por el usuario; las solicitudes se rigen por el proveedor elegido.",
    pn_about_card_tauri_description: "Contenedor nativo, ciclo de vida del backend y empaquetado de la edición Desktop.",
    pn_about_card_next_react_description: "Interfaz local y arquitectura de componentes del producto.",
    pn_about_card_fastapi_description: "API local que conecta la interfaz con los pipelines científicos.",
    pn_about_card_3dmol_description: "Visualización molecular 3D de estructuras, receptores, ligandos y complejos.",
    pn_about_card_ketcher_description: "Editor químico 2D para dibujar, importar y exportar estructuras moleculares.",
    pn_about_card_solana_description: "Integración opcional para registrar certificados; no constituye por sí misma protección de propiedad intelectual.",
    pn_about_card_rcsb_version: "CC0 1.0 · 380 estructuras",
    pn_about_card_rcsb_description: "Aporta las estructuras y los metadatos estructurales base del catálogo: los 380 archivos .pdb.gz distribuidos proceden directamente de RCSB PDB.",
    pn_about_card_rcsb_credit: "Dominio público (CC0 1.0) · cita científica recomendada: la entrada PDB concreta y sus autores originales",
    pn_about_card_uniprot_description: "Fuente de las descripciones funcionales de los receptores, tomadas del comentario FUNCTION y traducidas al español.",
    pn_about_card_uniprot_credit: "Atribución requerida · Fuente: UniProtKB; traducción/adaptación al español: MolDesign",
    pn_about_card_methods_name: "Publicaciones de métodos",
    pn_about_card_methods_version: "referencias por motor",
    pn_about_card_methods_description: "Vina, Meeko, Dimorphite-DL, PoseBusters, ESMFold, xTB, RTMScore, ADMET-AI y TabPFN conservan sus autores y referencias metodológicas.",
    pn_about_card_methods_credit: "Las citas científicas no sustituyen los avisos de licencia",
    pn_about_card_catalog_name: "Catálogo MolDesign",
    pn_about_card_catalog_version: "380 receptores curados",
    pn_about_card_catalog_description: "Curación de MolDesign sobre las estructuras de RCSB: caja de búsqueda, hotspots, selección de cadena, familia estructural y estado. Esa capa es cálculo propio, no una afirmación de RCSB ni de UniProt.",
    pn_about_card_catalog_credit: "Curación y cálculo: MolDesign · estructuras CC0 de RCSB PDB · descripciones CC BY 4.0 de UniProtKB · RCSB y UniProt no certifican los resultados de MolDesign",
    pn_about_card_dimorphite_description: "Protona el ligando al pH elegido (7,4 por defecto) antes de prepararlo.",
    pn_about_card_gemmi_description: "Lee las estructuras mmCIF/PDBx de los receptores que subes.",
    pn_about_card_posebusters_description: "Comprueba la validez física de las poses: geometría del ligando y contactos con la proteína.",
    pn_about_card_esmfold_version: "v1 · pesos a petición",
    pn_about_card_esmfold_description: "Pliega péptidos para que Vina los acople. Sus pesos (8,4 GB) se descargan a petición; el código viaja con Transformers.",
    pn_about_card_reportlab_description: "Genera los PDF del dossier y de los certificados.",
    pn_about_card_molcy_name: "Motor Molcy",
    pn_about_card_molcy_description: "Dibuja los vídeos y las fotos de Molcy dentro de Blender. Es obra propia de MolDesign, publicada bajo GPL-3.0-or-later, y se ejecuta como programa aparte.",
    pn_about_card_blender_description: "Ejecuta el motor de Molcy. No viaja en el instalador: MolDesign lo descarga a petición de la Blender Foundation y verifica su SHA-256.",
    pn_about_card_molecular_nodes_version: "la que instala Blender Extensions",
    pn_about_card_molecular_nodes_description: "Extensión de Blender que construye las moléculas de las escenas de Molcy. No viaja en el instalador: se instala a petición desde Blender Extensions.",
    pn_about_card_vcruntime_description: "Bibliotecas de ejecución que necesitan los programas nativos incluidos. Se rigen por los términos de redistribución de Microsoft, no por la licencia de MolDesign.",
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
    pn_prop_peso_molecular: "Peso molecular",
    pn_prop_peso_molecular_titulo: "Peso Molecular",
    pn_prop_hbd: "HBD",
    pn_prop_hba: "HBA",
    pn_prop_llega_cerebro: "Llega al cerebro",
    pn_prop_logs: "LogS (solubilidad)",
    pn_prop_rotatable_bonds: "Enlaces rotables",
    pn_prop_qed_titulo: "Estimación cuantitativa de drug-likeness (QED)",
    pn_prop_solubilidad_acuosa_titulo: "Solubilidad acuosa (LogS)",
    pn_pains_alerta: "Alerta PAINS",
    pn_lipinski_ro5: "Regla de cinco de Lipinski",
    pn_qed_cuantitativo: "QED (estimación cuantitativa de similitud con fármacos)",
    pn_sa_score_accesibilidad: "SA Score (accesibilidad sintética)",
    pn_patrones_detectados: "patrones detectados",
    pn_spider_peso_molecular: "Peso mol.",
    pn_spider_donadores_h: "Donadores H",
    pn_spider_aceptores_h: "Aceptores H",
    pn_spider_rotables: "Rotables",
    pn_spider_tu_compuesto: "Tu compuesto",
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
      "Señales estimadas de metabolismo CYP; no equivalen a toxicidad "
      + "clínica. Las alertas TabPFN de corridas antiguas no están validadas.",
    pn_toxicidad_sin_evaluar:
      "— Sin evaluar: TabPFN retirado por falta de procedencia de sus etiquetas.",
    pn_sin_alertas_reactividad:
      "✓ Sin señales CYP identificadas por ADMET-AI; no es una prueba de seguridad.",
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
    pn_score_adme: "ADME",
    pn_score_adme_profile: "Perfil ADME",
    pn_score_drug_likeness: "Perfil tipo fármaco",
    pn_score_specificity: "Especificidad",
    pn_score_control_mode: "Modo de control",
    pn_score_raw_affinity: "Afinidad bruta",
    pn_score_lipophilic_efficiency: "Eficiencia lipofílica",
    pn_score_rtmscore: "RTMScore (red neuronal de grafos)",
    pn_score_quantum: "Puntuación QUANTUM (xTB)",
    pn_score_synthetic_accessibility: "Accesibilidad sintética",
    pn_score_synthesis_warning: "Síntesis difícil",
    pn_score_toxicity_alert: "Alerta de toxicidad",
    pn_score_identifier: "Identificador",
    pn_score_identifier_placeholder: "p. ej., compuesto-001",
    pn_score_save_protocol: "Guardar protocolo",
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
    pn_caja_acoplamiento: "Caja de búsqueda",
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
      "Residuos clave del bolsillo de unión. Cada residuo indica si el ligando lo contactó (hotspot hit).",
    pn_residuo_contactado: "contactado",
    pn_residuo_sin_contacto: "sin contacto",
    pn_residuo_contacto_no_registrado: "contacto no registrado",
    pn_sin_hotspots: "Sin hotspots definidos para este target.",
    pn_residuos_usados_catalogo: "En esta corrida se usaron {n} residuos de referencia: los del catálogo.",
    pn_residuos_usados_elegidos:
      "En esta corrida se usaron {n} residuos de referencia, elegidos de los {total} del catálogo.",
    pn_residuos_usados_ninguno: "En esta corrida no se usó ningún residuo de referencia: se decidió desactivarlos.",
    pn_residuos_usados_desconocido:
      "Esta corrida no registró qué residuos de referencia usó. Se muestran los del catálogo, que podrían no ser los usados.",
    pn_residuo_no_usado: "no usado",
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
      "A pH {ph} la especie no cambia respecto a lo que escribiste: se acopló tal "
      + "cual.",
    // Declaración del tautómero (backend/chem/declaracion_tautomeros.py). Las
    // frases calcan las del expediente: el canónico de RDKit es reproducible,
    // no una predicción de población.
    pn_taut_enumerados: "entre {n} enumerados",
    pn_prot_estados_devueltos: "{n} estados devueltos",
    pn_prot_seleccion_cargas: "Se eligió por las cargas esperadas a pH {ph}.",
    pn_prot_seleccion_cargas_sin_ph: "Se eligió por las cargas esperadas; no consta el pH del criterio.",
    pn_prot_seleccion_alfabetica: "No se reconocieron centros ionizables; se eligió por orden alfabético del SMILES.",
    pn_prot_seleccion_sin_pka: "Se reconoció un grupo sin pKa en la tabla; la elección requiere revisión.",
    pn_prot_seleccion_sin_estados: "El enumerador no devolvió microestados alternativos.",
    pn_prot_seleccion_sin_validos: "Ninguna alternativa fue válida; se conservó la entrada.",
    pn_prot_seleccion_desconocida: "No consta cómo se eligió el estado.",
    pn_prot_quimica_no_resuelta: "La elección no está resuelta químicamente.",
    pn_prot_no_aplicada_sin_cambio: "La protonación no se aplicó. La especie no cambia respecto a la entrada: se acopló tal cual.",
    pn_prot_desconocida_sin_cambio: "No consta completa la protonación. La especie no cambia respecto a la entrada.",
    pn_prot_ph_no_consta: "Se aplicó la protonación, pero no consta su pH.",
    pn_ph_solicitado_ejecutado: "pH solicitado: {solicitado}; pH ejecutado: {ejecutado}.",
    pn_taut_titulo: "Tautómero:",
    pn_taut_unico: "uno solo enumerable; no hay alternativas que declarar.",
    pn_taut_multiestado:
      "{n} candidatos y ninguno descartado con evidencia. Se acopló el canónico "
      + "de RDKit, que es una representación reproducible, no una predicción de "
      + "población: revísalo antes de un cálculo de energía libre.",
    pn_taut_no_resuelto:
      "no resuelto: la enumeración falló o quedó incompleta, así que no se declara.",

    // ── SAR ───────────────────────────────────────────────────────
    pn_sar_titulo: "Análisis SAR — estructura-actividad",
    pn_sar_comparables: "Moléculas estructuralmente comparables",
    pn_sar_cohorte: "Qué moléculas entran en la tabla",
    pn_sar_cohorte_reciente: "La evaluación más reciente de cada molécula (cambia si se reevalúa con otro protocolo)",
    pn_sar_cohorte_protocolo: "Las {n} corridas de este caso con el mismo protocolo que la que ves (K={k}), tal como quedaron",
    pn_sar_cohorte_explicita: "Tabla construida sobre {n} corridas concretas del caso: se puede reconstruir aunque las moléculas se reevalúen después.",
    pn_sar_cohorte_rechazada: "No se pudo construir la tabla con esa cohorte: {motivo}",
    pn_sar_consultando: "Consultando análogos estructurales…",
    pn_sar_sin_analogos:
      "Sin análogos disponibles aún — evalúa más moléculas contra el mismo "
      + "receptor para poblar el SAR.",
    pn_sar_analogos_contra: "SAR: {count} análogos contra {target}",
    pn_sar_molecula: "Molécula",
    pn_sar_drug: "Fármaco",
    pn_sar_base: "molécula base",
    pn_sar_baseline: "Referencia",
    pn_sar_best_in_class: "Mejor de la clase",
    pn_sar_mejora_baseline: "Mejora frente a la referencia",
    pn_sar_empeora_baseline: "Empeora frente a la referencia",
    pn_flow_smiles_ingestion: "Ingesta de SMILES",
    pn_flow_etkdg_engine: "Motor ETKDG",
    pn_flow_cl_gnn: "CL-GNN",
    pn_flow_rtmscore: "RTMScore",
    pn_flow_ums_metal: "UMS de metales",
    pn_flow_molchamb: "MolChamb",
    pn_flow_selectivity: "Selectividad",
    pn_flow_admet_final: "ADMET final",
    pn_flow_molchat: "MolChat IA",
    pn_flow_solana_record: "Registro en Solana",
    pn_flow_pdf_certificate: "Certificado PDF",
    pn_flow_deep_focus: "Enfoque profundo",
    pn_flow_pipeline_completed: "Pipeline completado",
    pn_pdf_dossier_name: "INFORME_{id}.PDF",
    pn_pdf_fullscreen: "Pantalla completa",
    pn_pdf_download: "DESCARGAR",
    pn_pdf_register_integrity: "Registrar integridad",
    pn_reproducibility_title: "Reproducibilidad",
    pn_ml_rescore_label: "Rescoring por ML",
    pn_evaluated_label: "Evaluado",

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
    pn_traspaso_requiere_escritorio: "El traspaso del invitado requiere el escritorio.",
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
      "Las descargas pesadas se obtienen bajo demanda: los modelos, desde Hugging Face; "
      + "Blender, desde download.blender.org, y Molecular Nodes, desde extensions.blender.org. "
      + "Revisa el origen y la licencia de cada módulo antes de instalarlo.",
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
    pn_molcy_source_credit: "MolDesign · source code: github.com/srcacahuate619/moldesign-molcy",
    pe_bloqueado_desc: "Essential evidence is missing or a structural defect blocks progress.",
    pe_accion: "Recommended action",
    pe_ultima_completada: "The selected evaluation is audited; its identifier appears above. Changing it does not modify the case.",
    pe_hueco_estado: "Backbone gap near the site: the system is blocked until the structure is repaired or replaced.",
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
      "A computational result prioritizes what to review next. It does not replace "
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

    pn_catalogo_titulo: "Receptor catalog",
    pn_receptor_subir: "Upload receptor",
    pn_receptor_oficiales: "Official receptors",
    pn_mis_receptores: "My receptors",
    pn_targets_count: "{n} targets",
    pn_receptor_activo: "Active",
    pn_organismo_humano: "Human",
    pn_variante_reproducible: "Reproducible variant",
    pn_variante_crear: "Create variant",
    pn_variante_no_disponible:
      "This receptor cannot be prepared: it cannot be the base of a variant, which only changes the metals and cofactors that are kept.",
    pn_receptor_privado: "Private",
    pn_compartiendo: "Sharing",
    pn_compartir: "Share",
    pn_catalogo_sub:
      "Select a biological structure for the molecular docking simulation",
    pn_familia_quimica: "Chemical family",
    pn_familia_terapeutica: "Therapeutic family",
    pn_comunidad_cientifica: "Scientific community",
    pn_sin_receptores: "No receptors were found in this section",
    pn_calibracion: "Calibration",
    pn_preparacion: "Preparation",
    pn_prep_listo: "Ready",
    pn_prep_revisar: "Review",
    pn_prep_sin_datos: "No data",
    pn_no_disponible: "Unavailable",
    pn_no_disponible_meeko: "Automatic preparation (Meeko) cannot build this receptor.",
    pn_detalle_tecnico: "Technical detail",
    pn_truncadas_en_sitio: "Side chains truncated in the site: {n}",
    pn_todas: "All",
    pn_panel_por_defecto: "Default panel",
    pn_ninguna: "None",
    pn_anti_selector: "Anti-targets by family",
    pn_anti_todas: "All available",
    pn_anti_recuento: "{n}/{total} available targets selected",
    pn_anti_coste: "Each anti-target adds one docking run per conformer; selecting more than 8 can substantially increase runtime.",
    pn_anti_pose: "Redocking did not reproduce the crystal pose; the ΔΔG margin is indicative.",
    pn_anti_excluidas: "These anti-targets are unavailable and will be excluded when you apply: {ids}. Review Evaluation parameters.",
    pn_anti_guardadas: "Saved selection",
    pn_anti_ausente: "This saved ID no longer exists in the panel.",
    pn_anti_sin_familia: "Family not declared",
    pn_anti_cargando: "Checking available anti-targets…",
    pn_anti_error: "The anti-target panel could not be loaded. Available receptors cannot be confirmed.",
    pn_anti_reintentar: "Retry",
    pn_anti_pedidas: "Requested anti-targets: {ids}",
    pn_anti_acopladas: "Docked anti-targets: {ids}",
    pn_anti_cero: "None",
    pn_anti_truncadas: "{n} incomplete side chains were truncated near the site; the prepared pocket lacks those groups.",
    pn_anti_panel_elegir: "Choose anti-targets",
    pn_anti_panel_cerrar: "Close the list",
    pn_anti_panel_ayuda: "Your selected anti-targets and previous results appear here. Selecting an anti-target does not start a calculation.",
    pn_anti_panel_vacio: "No anti-target is selected. Choose the ones you want to evaluate in the catalog.",
    pn_anti_catalogo: "Anti-target catalog",
    pn_anti_estructura_detalle: "Structure details",
    pn_anti_estructura_reservas: "Structural caveats",
    pn_anti_catalogo_total: "{n} in catalog",
    pn_anti_catalogo_disponibles: "{n} available",
    pn_anti_catalogo_no_disponibles: "{n} unavailable",
    pn_anti_catalogo_ayuda: "Tick the anti-targets you want to add to your panel. Each one adds a docking run.",
    pn_anti_buscar: "Search anti-targets",
    pn_anti_buscar_placeholder: "Name, gene or PDB",
    pn_anti_filtrar_familia: "Family",
    pn_anti_todas_familias: "All families",
    pn_anti_resultados_busqueda: "Catalog results: {n}",
    pn_anti_sin_coincidencias: "No matches. Change the search or family.",
    pn_anti_seleccion_bloqueada: "The selection stays fixed until the current evaluation finishes.",
    pn_anti_panel_seleccionadas: "Selected: {n}",
    pn_anti_panel_evaluadas: "Evaluated in the selection: {n}",
    pn_anti_panel_anteriores: "Previous results: {n}",
    pn_anti_cobertura_registrada: "Panel evidence:",
    pn_anti_resultado_anterior: "Previous result · outside the selection",
    pn_anti_evaluar_seleccionadas: "Evaluate selected ({n})",
    pn_anti_sin_ficha: "This anti-target has no explanatory sheet of its own: only the risk the panel declares and its result are shown here.",
    pn_resolucion: "Resolution",
    pn_cerrar_catalogo: "Close the receptor catalog",
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
      + "Licenses.",
    pn_transparency: "Transparency",
    pn_card_count: "{count} entries",
    pn_licenses_notices: "Licenses and notices",
    pn_capacidades_desktop:
      "Real capabilities of the Desktop edition and where they come from.",
    pn_codigo_fuente: "Source code",
    pn_cerrar_acerca: "Close About MolDesign",
    pn_areas_stack: "Stack areas",
    pn_about_section_chemistry: "Chemistry and docking",
    pn_about_section_scoring: "Scoring and models",
    pn_about_section_ai: "AI and language",
    pn_about_section_platform: "Platform and visualization",
    pn_about_section_sources: "Credits and sources",
    pn_about_availability_included: "Included",
    pn_about_availability_optional: "Optional",
    pn_about_availability_external: "External service",
    pn_about_availability_adapted: "Adapted method",
    pn_about_card_moltalk_description:
      "The Moldex thumbnail that rotates the top-1 pose and the editor's 3D view come from its viewer. "
      + "The idea is theirs: we adapted its method for aligning the 3D geometry with the 2D drawing and "
      + "reimplemented it in our own code. We include neither its code nor its dependencies.",
    pn_about_card_moltalk_credit: "Dominic Fico · github.com/DomFico/moltalk",
    pn_about_kind_third_party: "Third party",
    pn_about_kind_moldesign: "MolDesign",
    pn_about_kind_scientific_source: "Scientific source",
    pn_about_card_vina_description: "Docking engine that generates and scores ligand–receptor poses. Includes vina_trace, a copy of Vina 1.2.7 that records the search for Molcy's Search scene.",
    pn_about_card_meeko_description: "Prepares ligands and receptors in the formats used by AutoDock.",
    pn_about_card_rdkit_description: "Chemical validation, descriptors, fingerprints, and molecular conformers.",
    pn_about_card_open_babel_description: "Standalone program that MolDesign runs as a command-line tool to convert PDBQT to SDF when ligand export fails. It is not linked as a library. The packaged executable identifies itself internally as 3.1.0 because the 3.1.1 release was a packaging correction that did not update the version string; the measured value is in the package manifest.",
    pn_about_card_open_babel_credit: "Open Babel contributors; wheel packaged by Jinzhe Zeng",
    pn_about_card_openmm_description: "They ship in the runtime. In 1.0.2, MM-GBSA is disabled and the interface offers no workflow that uses them.",
    pn_about_card_prolif_description: "Analysis of contacts and protein–ligand interactions in 3D structures.",
    pn_about_card_xtb_description: "Semi-empirical calculations run as a separate process to produce quantum descriptors.",
    pn_about_card_xgboost_description: "Tabular rescoring models and explanations of their feature contributions.",
    pn_about_card_admet_description: "Computational predictions of ADMET properties; they do not replace experimental validation.",
    pn_about_card_tabpfn_description: "Ships in the runtime with its license and attribution; in 1.0.2 no MolDesign workflow uses it.",
    pn_about_card_rtmscore_version: "integrated snapshot",
    pn_about_card_rtmscore_description: "Research implementation for protein–ligand rescoring. Distribution remains blocked until the upstream license is clarified.",
    pn_about_card_moldesign_models_name: "MolDesign models",
    pn_about_card_moldesign_models_version: "versioned manifest",
    pn_about_card_moldesign_models_description: "MolDesign's own models and calibrations, with manifests, hashes, and a license separate from the code.",
    pn_about_card_llama_description: "Local server that runs GGUF models outside MolDesign's main process.",
    pn_about_card_qwen_description: "Local model compatible with MolChat. Its weights have their own license and retain their third-party licensing terms.",
    pn_about_card_anthropic_description: "Optional integration configured by the user; requests are governed by the selected provider.",
    pn_about_card_tauri_description: "Native container, backend lifecycle, and packaging for the Desktop edition.",
    pn_about_card_next_react_description: "Local interface and the product's component architecture.",
    pn_about_card_fastapi_description: "Local API that connects the interface to the scientific pipelines.",
    pn_about_card_3dmol_description: "3D molecular visualization of structures, receptors, ligands, and complexes.",
    pn_about_card_ketcher_description: "2D chemical editor for drawing, importing, and exporting molecular structures.",
    pn_about_card_solana_description: "Optional integration for recording certificates; it does not by itself protect intellectual property.",
    pn_about_card_rcsb_version: "CC0 1.0 · 380 structures",
    pn_about_card_rcsb_description: "Provides the catalog's base structures and structural metadata: the 380 distributed .pdb.gz files come directly from RCSB PDB.",
    pn_about_card_rcsb_credit: "Public domain (CC0 1.0) · recommended scientific citation: the specific PDB entry and its original authors",
    pn_about_card_uniprot_description: "Source of receptor functional descriptions, taken from the FUNCTION comment and translated into Spanish.",
    pn_about_card_uniprot_credit: "Attribution required · Source: UniProtKB; translation/adaptation into Spanish: MolDesign",
    pn_about_card_methods_name: "Methods publications",
    pn_about_card_methods_version: "references by engine",
    pn_about_card_methods_description: "Vina, Meeko, Dimorphite-DL, PoseBusters, ESMFold, xTB, RTMScore, ADMET-AI, and TabPFN retain their authors and methodological references.",
    pn_about_card_methods_credit: "Scientific citations do not replace license notices",
    pn_about_card_catalog_name: "MolDesign catalog",
    pn_about_card_catalog_version: "380 curated receptors",
    pn_about_card_catalog_description: "MolDesign curation of RCSB structures: search box, hotspots, chain selection, structural family, and status. This layer is computed by MolDesign; it is not a claim by RCSB or UniProt.",
    pn_about_card_catalog_credit: "Curation and computation: MolDesign · CC0 structures from RCSB PDB · CC BY 4.0 descriptions from UniProtKB · RCSB and UniProt do not certify MolDesign results",
    pn_about_card_dimorphite_description: "Protonates the ligand at the chosen pH (7.4 by default) before it is prepared.",
    pn_about_card_gemmi_description: "Reads the mmCIF/PDBx structures of the receptors you upload.",
    pn_about_card_posebusters_description: "Checks the physical validity of poses: ligand geometry and contacts with the protein.",
    pn_about_card_esmfold_version: "v1 · weights on request",
    pn_about_card_esmfold_description: "Folds peptides so that Vina can dock them. Its weights (8.4 GB) are downloaded on request; the code ships with Transformers.",
    pn_about_card_reportlab_description: "Generates the PDFs of the dossier and the certificates.",
    pn_about_card_molcy_name: "Molcy engine",
    pn_about_card_molcy_description: "Draws Molcy's videos and photos inside Blender. It is MolDesign's own work, released under GPL-3.0-or-later, and runs as a separate program.",
    pn_about_card_blender_description: "Runs the Molcy engine. It does not ship with the installer: MolDesign downloads it on request from the Blender Foundation and verifies its SHA-256.",
    pn_about_card_molecular_nodes_version: "the version Blender Extensions installs",
    pn_about_card_molecular_nodes_description: "Blender extension that builds the molecules in Molcy's scenes. It does not ship with the installer: it is installed on request from Blender Extensions.",
    pn_about_card_vcruntime_description: "Runtime libraries needed by the bundled native programs. They are governed by Microsoft's redistribution terms, not by MolDesign's license.",
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
    pn_prop_peso_molecular: "Molecular weight",
    pn_prop_peso_molecular_titulo: "Molecular weight",
    pn_prop_hbd: "HBD",
    pn_prop_hba: "HBA",
    pn_prop_llega_cerebro: "Reaches the brain",
    pn_prop_logs: "LogS (solubility)",
    pn_prop_rotatable_bonds: "Rotatable bonds",
    pn_prop_qed_titulo: "Quantitative estimate of drug-likeness (QED)",
    pn_prop_solubilidad_acuosa_titulo: "Aqueous solubility (LogS)",
    pn_pains_alerta: "PAINS alert",
    pn_lipinski_ro5: "Lipinski Rule of Five",
    pn_qed_cuantitativo: "QED (quantitative estimate of drug-likeness)",
    pn_sa_score_accesibilidad: "SA Score (synthetic accessibility)",
    pn_patrones_detectados: "patterns detected",
    pn_spider_peso_molecular: "Mol. weight",
    pn_spider_donadores_h: "H-bond donors",
    pn_spider_aceptores_h: "H-bond acceptors",
    pn_spider_rotables: "Rotatable",
    pn_spider_tu_compuesto: "Your compound",
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
      "Estimated CYP metabolism signals do not establish clinical toxicity. "
      + "Legacy TabPFN alerts are unvalidated.",
    pn_toxicidad_sin_evaluar:
      "— Not evaluated: TabPFN withdrawn because its labels lack provenance.",
    pn_sin_alertas_reactividad:
      "✓ No CYP signals identified by ADMET-AI; this does not establish safety.",
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
    pn_score_adme: "ADME",
    pn_score_adme_profile: "ADME profile",
    pn_score_drug_likeness: "Drug-likeness",
    pn_score_specificity: "Specificity",
    pn_score_control_mode: "Control mode",
    pn_score_raw_affinity: "Raw affinity",
    pn_score_lipophilic_efficiency: "Lipophilic efficiency",
    pn_score_rtmscore: "RTMScore (GNN)",
    pn_score_quantum: "QUANTUM (xTB) score",
    pn_score_synthetic_accessibility: "Synthetic accessibility",
    pn_score_synthesis_warning: "Difficult to synthesize",
    pn_score_toxicity_alert: "Toxicity alert",
    pn_score_identifier: "Identifier",
    pn_score_identifier_placeholder: "e.g. compound-001",
    pn_score_save_protocol: "Save protocol",
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
    pn_caja_acoplamiento: "Search box",
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
      "Key residues of the binding pocket. Each residue states whether the ligand contacted it (hotspot hit).",
    pn_residuo_contactado: "contacted",
    pn_residuo_sin_contacto: "no contact",
    pn_residuo_contacto_no_registrado: "contact not recorded",
    pn_sin_hotspots: "No hotspots defined for this target.",
    pn_residuos_usados_catalogo: "This run used {n} reference residues: the catalog ones.",
    pn_residuos_usados_elegidos:
      "This run used {n} reference residues, selected from the {total} in the catalog.",
    pn_residuos_usados_ninguno: "This run used no reference residues: they were deliberately turned off.",
    pn_residuos_usados_desconocido:
      "This run did not record which reference residues it used. The catalog ones are shown, which may not be the ones used.",
    pn_residuo_no_usado: "not used",
    pn_ver_controles_pose: "See the physical controls of pose #{rango}",

    pn_lo_que_escribiste: "What you typed",
    pn_no_es_la_que_escribiste:
      "The docked molecule is not the one you typed.",
    pn_alternativas_descartadas:
      "The discarded alternatives were not evaluated. The descriptors below (MW, "
      + "LogP, TPSA) are calculated on the neutral form you typed, not on the "
      + "docked species.",
    pn_ph_no_cambia:
      "At pH {ph} the species does not change from what you typed: it was docked as "
      + "it is.",
    pn_taut_enumerados: "among {n} enumerated forms",
    pn_prot_estados_devueltos: "{n} states returned",
    pn_prot_seleccion_cargas: "Selected by the expected charges at pH {ph}.",
    pn_prot_seleccion_cargas_sin_ph: "Selected by the expected charges; the criterion pH is not recorded.",
    pn_prot_seleccion_alfabetica: "No ionizable centers were recognized; selection used SMILES alphabetical order.",
    pn_prot_seleccion_sin_pka: "A group without a pKa in the table was recognized; the selection requires review.",
    pn_prot_seleccion_sin_estados: "The enumerator returned no alternative microstates.",
    pn_prot_seleccion_sin_validos: "No alternative was valid; the input was retained.",
    pn_prot_seleccion_desconocida: "How the state was selected is not recorded.",
    pn_prot_quimica_no_resuelta: "The selection is not chemically resolved.",
    pn_prot_no_aplicada_sin_cambio: "Protonation was not applied. The species is unchanged from the input: it was docked as it is.",
    pn_prot_desconocida_sin_cambio: "The protonation record is incomplete. The species is unchanged from the input.",
    pn_prot_ph_no_consta: "Protonation was applied, but its pH is not recorded.",
    pn_ph_solicitado_ejecutado: "Requested pH: {solicitado}; executed pH: {ejecutado}.",
    pn_taut_titulo: "Tautomer:",
    pn_taut_unico: "a single enumerable form; there are no alternatives to declare.",
    pn_taut_multiestado:
      "{n} candidates and none ruled out with evidence. The RDKit canonical form "
      + "was docked; it is a reproducible representation, not a population "
      + "prediction: review it before a free-energy calculation.",
    pn_taut_no_resuelto:
      "not resolved: the enumeration failed or was incomplete, so it is not declared.",

    pn_sar_titulo: "SAR analysis — structure-activity",
    pn_sar_comparables: "Structurally comparable molecules",
    pn_sar_cohorte: "Which molecules enter the table",
    pn_sar_cohorte_reciente: "The most recent evaluation of each molecule (changes if re-evaluated with another protocol)",
    pn_sar_cohorte_protocolo: "The {n} runs in this case with the same protocol as the one you see (K={k}), as they were recorded",
    pn_sar_cohorte_explicita: "Table built on {n} specific runs of the case: it can be rebuilt even if the molecules are re-evaluated later.",
    pn_sar_cohorte_rechazada: "The table could not be built with that cohort: {motivo}",
    pn_sar_consultando: "Looking up structural analogues…",
    pn_sar_sin_analogos:
      "No analogues available yet — evaluate more molecules against the same "
      + "receptor to populate the SAR.",
    pn_sar_analogos_contra: "SAR: {count} analogues against {target}",
    pn_sar_molecula: "Molecule",
    pn_sar_drug: "Drug",
    pn_sar_base: "base molecule",
    pn_sar_baseline: "Baseline",
    pn_sar_best_in_class: "Best in class",
    pn_sar_mejora_baseline: "Improves vs baseline",
    pn_sar_empeora_baseline: "Worse vs baseline",
    pn_flow_smiles_ingestion: "SMILES ingestion",
    pn_flow_etkdg_engine: "ETKDG engine",
    pn_flow_cl_gnn: "CL-GNN",
    pn_flow_rtmscore: "RTMScore",
    pn_flow_ums_metal: "Metal UMS",
    pn_flow_molchamb: "MolChamb",
    pn_flow_selectivity: "Selectivity",
    pn_flow_admet_final: "Final ADMET",
    pn_flow_molchat: "MolChat AI",
    pn_flow_solana_record: "Solana record",
    pn_flow_pdf_certificate: "PDF certificate",
    pn_flow_deep_focus: "Deep focus",
    pn_flow_pipeline_completed: "Pipeline completed",
    pn_pdf_dossier_name: "REPORT_{id}.PDF",
    pn_pdf_fullscreen: "Full screen",
    pn_pdf_download: "DOWNLOAD",
    pn_pdf_register_integrity: "Record integrity",
    pn_reproducibility_title: "Reproducibility",
    pn_ml_rescore_label: "ML rescoring",
    pn_evaluated_label: "Evaluated",

    pn_variante_titulo: "New preparation variant",
    pn_variante_nombre: "Variant name",
    pn_variante_metales: "Metals and cofactors that must be kept",
    pn_variante_separados:
      "Comma-separated. Waters are removed in this MVP; the real preparation and "
      + "its hashes will be recorded when the variant is created.",

    pn_comparador_titulo: "Ligand comparator",
    pn_comparador_no_cargo:
      "The pose and the receptor of this molecule could not be loaded. The file "
      + "may be unavailable or not authorized for your account.",
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
    pn_traspaso_requiere_escritorio: "Guest transfer requires the desktop app.",
    pn_traspaso_tienes: "You have work done as a guest on this machine",
    pn_traspaso_ahora_no: "Not now",
    pn_traspaso_sin_batch: "Batch screens do not come across here yet.",

    pn_panel_selectividad: "Selectivity panel",
    pn_panel_selectividad_d: "Docks against the declared anti-target panel",
    pn_catalogo: "CATALOG",
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
      "Heavy downloads are fetched on demand: the models from Hugging Face, Blender "
      + "from download.blender.org and Molecular Nodes from extensions.blender.org. "
      + "Check the origin and the license of each module before installing it.",
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
