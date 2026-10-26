// =====================================================================
// Opciones de evaluación — motor, bolsillo y recursos
// =====================================================================
//
// DOS TEXTOS DE AQUÍ NO SON ETIQUETAS, SON ADVERTENCIAS CIENTÍFICAS, y se
// traducen con el mismo cuidado que el modal legal:
//
//   · El pH de protonación cambia LA ESPECIE QUÍMICA que se acopla, no un
//     ajuste del motor. Un ácido carboxílico entra neutro a pH 1 y como anión a
//     7.4: es otra molécula, con otra huella y otro resultado. El inglés tiene
//     que decir eso, no «affects protonation».
//
//   · Los pasos de minimización «no garantizan precisión». Ese «no garantizan»
//     es el punto entero de la frase.
//
// «Docking», «score» y «pose» se quedan como están en los dos
// idiomas: son los términos del campo y traducirlos alejaría al usuario de la
// literatura que va a leer después.

import type { ModuloDeTraduccion } from "./index";

export const opciones: ModuloDeTraduccion = {
  es: {
    op_comprobando_motores: "Comprobando motores disponibles…",
    op_menu_theme_dark: "Tema oscuro",
    op_menu_theme_light: "Tema claro",
    op_titulo: "Parámetros de la evaluación",
    op_opciones_avanzadas: "Parámetros avanzados",
    op_sub_herramienta: "¿Con qué herramienta?",
    op_sub_donde: "¿Dónde acoplar?",
    op_sub_recursos: "¿Con cuántos recursos?",
    op_subtitulo:
      "Configura el motor, el bolsillo de unión y los recursos antes de ejecutar",
    op_cerrar: "Cerrar opciones de evaluación",
    op_aplicar: "Aplicar configuración",

    // ── Motor ─────────────────────────────────────────────────────
    op_motor_docking: "Motor y muestreo",
    op_moleculas_pequenas: "Moléculas pequeñas",
    op_api_grupo: "Motor externo (API)",
    op_api_titulo: "Vía API",
    op_api_badge: "Sin conectar",
    op_api_desc: "Un motor propio o de terceros, conectado por API. Esta versión no envía datos a ningún servicio.",
    op_esm_desc: "Pliega el péptido con ESMFold y lo acopla con Vina. Si la geometría del ligando transferido no pasa las comprobaciones, la transferencia se abstiene y no da afinidad. Si el caso declara una caja, la corrida sigue con Vina estándar sobre ella y lo marca con un aviso crítico de motor sustituido; sin caja, la corrida falla.",
    op_esm_encendido: "Encendido y listo.",
    op_esm_se_enciende: "Instalado. Se enciende solo cuando la corrida lo necesita.",
    op_esm_reintentar: "Reintentar",
    op_esm_sin_estado: "Comprobando el estado…",
    op_esm_chip_listo: "Listo",
    op_esm_chip_instalado: "Instalado",
    op_esm_chip_sin_descargar: "Sin descargar",
    op_esm_chip_no_arranco: "No arrancó",
    op_esm_chip_no_disponible: "No disponible",
    op_ayuda_sobre: "Más información sobre {tema}",
    op_ayuda_cerrar: "Cerrar ayuda",
    op_esm_alcance: "ESMFold está pensado para péptidos lineales; para una molécula pequeña, Vina es la opción recomendada. La decisión es tuya: si ESMFold no puede plegar la entrada, la corrida cae a Vina con exhaustividad 4 y lo indica en los avisos.",
    op_precision_gnn: "Precisión GNN",
    op_conformeros_descripcion: "Conformaciones iniciales del ligando",
    op_conformeros_varios: "Varios confórmeros",
    op_conformeros_numero: "Número de confórmeros",
    op_conformeros_aviso: "Explora más conformaciones y aumenta el tiempo de cálculo. No garantiza una mejor pose.",
    op_no_aplica: "No aplica para el motor seleccionado",

    // ── Bolsillo ──────────────────────────────────────────────────
    op_parametros_bolsillo: "Parámetros del bolsillo",
    op_centro_grid: "Centro de la caja de búsqueda (Å)",
    op_dimensiones_grid: "Dimensiones de la caja de búsqueda (Å)",
    op_tamano_x: "Tamaño X",
    op_tamano_y: "Tamaño Y",
    op_tamano_z: "Tamaño Z",
    op_parametros_busqueda: "Parámetros de búsqueda",
    op_grid_explicacion:
      "La caja de búsqueda define la región del espacio donde Vina buscará poses del "
      + "ligando. Una caja más grande = búsqueda más exhaustiva, pero más lenta.",
    op_hotspots: "Residuos del sitio activo (hotspots)",
    op_sistema_sellado_titulo: "Caja y residuos fijados",
    op_sistema_sellado:
      "Una corrida de este caso ya terminó en este sistema. La caja y los "
      + "residuos definen qué se está comparando y no se pueden mover sin que "
      + "las corridas dejen de ser el mismo experimento; para cambiarlos, crea "
      + "otro caso. El protocolo —motor, exhaustiveness, poses— sí se puede "
      + "cambiar: cada corrida guarda el suyo y el historial del caso enseña "
      + "cuál usó cada una.",
    op_hotspots_fijados:
      "Fijados por la primera corrida que terminó en este caso.",
    op_hotspots_explicacion:
      // SOL-09: no es una etiqueta, es una advertencia científica. Los
      // hotspots NO guían la búsqueda de Vina (la región la define la
      // caja); son referencias para describir el sitio y analizar los
      // contactos. Prometer lo contrario hacia creer que desmarcar un
      // residuo cambia el espacio explorado.
      "No guían la búsqueda de Vina: la región la define la caja. Son "
      + "referencias para describir el sitio y analizar los contactos de las poses. "
      + "Desmarca los que no quieras usar como referencia.",
    op_hotspots_activos: "({activos}/{total} activos)",
    op_marcar_todos: "Marcar todos",
    op_desmarcar_todos: "Desmarcar todos",

    // ── Recursos y pipeline ───────────────────────────────────────
    op_recursos: "Recursos de cómputo",
    op_modulos_pipeline: "Módulos del pipeline",

    // ── Preparación del ligando ───────────────────────────────────
    op_preparacion_ligando: "Preparación del ligando",
    op_ph_protonacion: "pH de protonación",
    op_tautomero: "Tautómero del ligando",
    op_tautomero_defecto: "Canónico de RDKit (MolDesign normaliza el tautómero)",
    op_tautomero_entrada: "Por defecto (conservar el tautómero que escribí)",
    op_tautomero_ayuda: "Por defecto se acopla el tautómero escrito en el SMILES, con su estereoquímica. El canónico de RDKit lo sustituye por una forma normalizada y reproducible, que no predice el tautómero dominante y a veces elige una forma minoritaria (hidroxamatos, lactamas). La protonación sigue el pH seleccionado en los dos casos.",
    op_numero_disminuir: "Disminuir {campo}",
    op_numero_aumentar: "Aumentar {campo}",
    op_numero_fuera_de_rango: "{valor} está fuera del rango permitido ({min} a {max}). Se conserva {vigente}.",
    op_numero_no_valido: "«{valor}» no es un número válido. Se conserva {vigente}.",
    op_numero_no_entero: "«{valor}» debe ser un número entero. Se conserva {vigente}.",
    op_ph_cambia_a: "Cambia la",
    op_ph_especie: "especie química",
    op_ph_cambia_b:
      "que se acopla, no un ajuste del motor. Un ácido carboxílico entra neutro "
      + "a pH 1 y como anión a 7.4; la lisina da tres especies distintas entre 1 "
      + "y 12. Dos pH que producen especies distintas son corridas distintas y no "
      + "comparten caché.",
    op_ph_fuera_fisiologico:
      "Fuera del pH fisiológico (7.4). El receptor se prepara aparte y no sigue "
      + "a este valor: la comparación con una corrida a 7.4 deja de ser directa.",
    op_pasos_no_garantizan:
      "Más pasos aumentan el coste y pueden mejorar la convergencia; no "
      + "garantizan precisión. 1000 es un valor orientativo para screening.",

    // ── Descargas y menú ──────────────────────────────────────────
    op_descargas_actividad_reciente: "Actividad reciente",
    op_descargas_modelos_motores: "Modelos y motores",
    op_menu_modelos_motores: "Modelos y motores",
    op_download_consult_notices: "Consultar avisos",
    op_download_esmfold_name: "ESMFold v1 — pesos del modelo",
    op_download_esmfold_description: "Plegamiento de péptidos con ESMFold (Meta AI); el acoplamiento lo hace después AutoDock Vina. Con GPU tarda minutos; en CPU, bastante más. El tokenizer ya viene en el instalador: esto es sólo el checkpoint.",
    op_download_qwen_description: "LLM local para MolChat",
    op_download_and_verify: "Descargar y verificar",
    op_download_extracting: "Extrayendo",
    op_download_installed: "Instalado",
    op_download_already_installed: "Ya lo tienes instalado",
    op_download_already_installed_detail: "El archivo está en disco y su SHA-256 coincide con el publicado.",
    op_download_again_question: "¿Descargar de nuevo?",
    op_download_again: "Descargar de nuevo",
    op_download_again_detail: "Vuelve a bajar {size} y sustituye el archivo sólo si el nuevo pasa la verificación SHA-256. Úsalo si sospechas que está dañado.",
    op_download_not_installed: "No instalado",
    op_download_retry: "Reintentar descarga",
    op_download_required: "Requerido",
    op_download_view_license: "Ver licencia",
    op_download_view_source: "Ver origen",
    op_download_now: "Descargar ahora",
    op_required_model: "Modelo requerido",
    op_language: "Idioma",
    op_path_default: "Predeterminado",
    op_reset_default_path: "Restablecer la ruta predeterminada",
    op_download_downloading: "Descargando",
    op_data_clearing: "Limpiando…",
    op_provider_configured: "Configurado",
    op_menu_back_options: "Volver a opciones",
    op_menu_close_options: "Cerrar opciones",
    op_menu_downloads: "Gestionar descargas",
    op_menu_data_backup: "Datos y respaldo",
    op_menu_clear_legacy: "Limpiar datos locales heredados",
    op_menu_sounds: "Sonidos",
    op_menu_support: "Soporte y ayuda",
    op_faq: "Preguntas frecuentes",
    op_activity: "Actividad",
    op_activity_count_one: "Actividad: {count} pendiente",
    op_activity_count_many: "Actividad: {count} pendientes",
    op_activity_notifications: "Actividad y notificaciones",
    op_activity_close: "Cerrar actividad",
    op_downloads: "Descargas",
  },
  en: {
    op_comprobando_motores: "Checking available engines…",
    op_menu_theme_dark: "Dark theme",
    op_menu_theme_light: "Light theme",
    op_titulo: "Evaluation parameters",
    op_opciones_avanzadas: "Advanced parameters",
    op_sub_herramienta: "With which tool?",
    op_sub_donde: "Where to dock?",
    op_sub_recursos: "With how many resources?",
    op_subtitulo:
      "Set the engine, the binding pocket and the resources before running",
    op_cerrar: "Close evaluation options",
    op_aplicar: "Apply configuration",

    op_motor_docking: "Engine and sampling",
    op_moleculas_pequenas: "Small molecules",
    op_api_grupo: "External engine (API)",
    op_api_titulo: "Via API",
    op_api_badge: "Not connected",
    op_api_desc: "Your own or a third-party engine, connected over API. This version does not send data to any service.",
    op_esm_desc: "Folds the peptide with ESMFold and docks it with Vina. If the transferred ligand geometry fails validation, the transfer abstains and gives no affinity. If the case declares a box, the run continues with standard Vina on it and flags it with a critical substituted-engine warning; without a box, the run fails.",
    op_esm_encendido: "Running and ready.",
    op_esm_se_enciende: "Installed. Starts only when the run needs it.",
    op_esm_reintentar: "Retry",
    op_esm_sin_estado: "Checking status…",
    op_esm_chip_listo: "Ready",
    op_esm_chip_instalado: "Installed",
    op_esm_chip_sin_descargar: "Not downloaded",
    op_esm_chip_no_arranco: "Failed to start",
    op_esm_chip_no_disponible: "Unavailable",
    op_ayuda_sobre: "More information about {tema}",
    op_ayuda_cerrar: "Close help",
    op_esm_alcance: "ESMFold is meant for linear peptides; for a small molecule, Vina is the recommended choice. The decision is yours: if ESMFold cannot fold the input, the run falls back to Vina with exhaustiveness 4 and notes it in the warnings.",
    op_precision_gnn: "GNN precision",
    op_conformeros_descripcion: "Initial ligand conformations",
    op_conformeros_varios: "Multiple conformers",
    op_conformeros_numero: "Number of conformers",
    op_conformeros_aviso: "Explores more conformations and increases computation time. It does not guarantee a better pose.",
    op_no_aplica: "Does not apply to the selected engine",

    op_parametros_bolsillo: "Pocket parameters",
    op_centro_grid: "Search box center (Å)",
    op_dimensiones_grid: "Search box dimensions (Å)",
    op_tamano_x: "Size X",
    op_tamano_y: "Size Y",
    op_tamano_z: "Size Z",
    op_parametros_busqueda: "Search parameters",
    op_grid_explicacion:
      "The search box defines the region of space where Vina will search for "
      + "ligand poses. A larger box means a more exhaustive search, but a "
      + "slower one.",
    op_hotspots: "Active-site residues (hotspots)",
    op_sistema_sellado_titulo: "Box and residues locked",
    op_sistema_sellado:
      "A run of this case has already finished on this system. The box and the "
      + "residues define what is being compared, and they cannot be moved "
      + "without the runs ceasing to be the same experiment; to change them, "
      + "create another case. The protocol —engine, exhaustiveness, poses— can "
      + "be changed: each run stores its own and the case history shows which "
      + "one each used.",
    op_hotspots_fijados:
      "Locked by the first run that finished in this case.",
    op_hotspots_explicacion:
      // SOL-09: same honesty in English — they do not guide Vina's search;
      // the box defines the region. A soft translation would reintroduce
      // the promise the audit refuted.
      "They do not guide Vina's search: the box defines the region. They are "
      + "references to describe the site and analyze the contacts of the poses. "
      + "Clear the ones you do not want as references.",
    op_hotspots_activos: "({activos}/{total} active)",
    op_marcar_todos: "Select all",
    op_desmarcar_todos: "Clear all",

    op_recursos: "Compute resources",
    op_modulos_pipeline: "Pipeline modules",

    op_preparacion_ligando: "Ligand preparation",
    op_ph_protonacion: "Protonation pH",
    op_tautomero: "Ligand tautomer",
    op_tautomero_defecto: "RDKit canonical (MolDesign normalizes the tautomer)",
    op_tautomero_entrada: "Default (keep the tautomer I entered)",
    op_tautomero_ayuda: "By default, the tautomer entered in the SMILES is docked, with its stereochemistry. The RDKit canonical option replaces it with a normalized, reproducible form that does not predict the dominant tautomer and sometimes picks a minor form (hydroxamates, lactams). Protonation follows the selected pH in both cases.",
    op_numero_disminuir: "Decrease {campo}",
    op_numero_aumentar: "Increase {campo}",
    op_numero_fuera_de_rango: "{valor} is outside the allowed range ({min} to {max}). {vigente} is kept.",
    op_numero_no_valido: "“{valor}” is not a valid number. {vigente} is kept.",
    op_numero_no_entero: "“{valor}” must be a whole number. {vigente} is kept.",
    op_ph_cambia_a: "It changes the",
    op_ph_especie: "chemical species",
    op_ph_cambia_b:
      "that is docked; it is not an engine setting. A carboxylic acid enters "
      + "neutral at pH 1 and as an anion at 7.4; lysine gives three different "
      + "species between 1 and 12. Two pH values that produce different species "
      + "are different runs and do not share a cache.",
    op_ph_fuera_fisiologico:
      "Outside physiological pH (7.4). The receptor is prepared separately and "
      + "does not follow this value: comparison with a run at 7.4 stops being "
      + "direct.",
    op_pasos_no_garantizan:
      "More steps raise the cost and may improve convergence; they do not "
      + "guarantee accuracy. 1000 is a rule-of-thumb value for screening.",

    // ── Descargas y menú ──────────────────────────────────────────
    op_descargas_actividad_reciente: "Recent activity",
    op_descargas_modelos_motores: "Models and engines",
    op_menu_modelos_motores: "Models and engines",
    op_download_consult_notices: "See notices",
    op_download_esmfold_name: "ESMFold v1 — model weights",
    op_download_esmfold_description: "Peptide folding with ESMFold (Meta AI); docking is then performed by AutoDock Vina. It takes minutes on a GPU and considerably longer on a CPU. The tokenizer is already included in the installer: this download contains only the checkpoint.",
    op_download_qwen_description: "Local LLM for MolChat",
    op_download_and_verify: "Download and verify",
    op_download_extracting: "Extracting",
    op_download_installed: "Installed",
    op_download_already_installed: "Already installed",
    op_download_already_installed_detail: "The file is on disk and its SHA-256 matches the published one.",
    op_download_again_question: "Download again?",
    op_download_again: "Download again",
    op_download_again_detail: "Downloads {size} again and replaces the file only if the new one passes the SHA-256 check. Use it if you suspect the file is damaged.",
    op_download_not_installed: "Not installed",
    op_download_retry: "Retry download",
    op_download_required: "Required",
    op_download_view_license: "View license",
    op_download_view_source: "View source",
    op_download_now: "Download now",
    op_required_model: "Required model",
    op_language: "Language",
    op_path_default: "Default",
    op_reset_default_path: "Reset the default path",
    op_download_downloading: "Downloading",
    op_data_clearing: "Clearing…",
    op_provider_configured: "Configured",
    op_menu_back_options: "Back to options",
    op_menu_close_options: "Close options",
    op_menu_downloads: "Manage downloads",
    op_menu_data_backup: "Data and backup",
    op_menu_clear_legacy: "Clear legacy local data",
    op_menu_sounds: "Sounds",
    op_menu_support: "Support and help",
    op_faq: "Frequently asked questions",
    op_activity: "Activity",
    op_activity_count_one: "Activity: {count} pending",
    op_activity_count_many: "Activity: {count} pending",
    op_activity_notifications: "Activity and notifications",
    op_activity_close: "Close activity",
    op_downloads: "Downloads",
  },
};
