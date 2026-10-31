// =====================================================================
// Texto compartido: lo que dicen varias pantallas a la vez
// =====================================================================
//
// QUE ENTRA AQUI Y QUE NO. Entra lo que aparece en MAS DE UNA superficie con
// el mismo sentido: estados de una corrida, verbos de boton, unidades. NO entra
// un texto que hoy se repite por casualidad en dos pantallas pero que manana
// una de ellas querra matizar; eso pertenece a su modulo, aunque se escriba dos
// veces. Compartir una clave es prometer que las dos pantallas van a querer
// decir siempre lo mismo.
//
// SOBRE EL VOCABULARIO EN INGLES. «Docking», «score» y «pose» se dejan como
// estan: son los terminos del campo y traducirlos —«acoplamiento» pasa, pero
// «puntuacion» y «postura» no— confundiria a quien lee literatura. En
// castellano se usa «acoplamiento» porque ahi si es el termino habitual.

import type { ModuloDeTraduccion } from "./index";

export const comun: ModuloDeTraduccion = {
  es: {
    c_engine_idle: "Motor en espera",
    c_engine_starting: "Iniciando motor…",
    c_engine_ready: "Motor listo",
    c_engine_not_installed: "Motor no instalado",
    c_engine_spawn_failed: "El motor no pudo arrancar",
    c_engine_health_failed: "El motor arrancó pero no superó la comprobación de salud",
    c_engine_disconnected: "El motor se desconectó",
    c_engine_explain_not_installed: "Falta una parte del runtime de cálculo en disco (Python, el backend o Vina). Repara o reinstala MolDesign; los modelos opcionales no sustituyen este runtime.",
    c_engine_explain_spawn_failed: "El proceso del motor no llegó a ejecutarse. Suele ser un permiso o un ejecutable que falta.",
    c_engine_explain_health_failed: "El proceso arrancó pero no se identificó como el backend de MolDesign. Suele significar que se está ejecutando una copia desactualizada del backend.",
    c_engine_explain_disconnected: "El motor estaba disponible y dejó de responder. La evaluación no podrá continuar hasta que vuelva.",
    c_engine_unknown: "El motor devolvió un estado que esta versión no reconoce.",
    c_engine_lost_port: "El motor dejó de responder en el puerto {port}.",
    c_help_meaning: "Qué significa: {title}",
    c_external_failed: "No se pudo abrir el enlace",
    c_local_doc_failed: "No se pudo cargar {path}. El documento viaja con la aplicacion, asi que esto indica un empaquetado incompleto. ({cause})",
    co_frontend_216: "El puente de escritorio no esta disponible, asi que no se puede saber en que puerto quedo el backend. No se adivina: otro programa podria estar escuchando ahi.",
    co_frontend_217: "El motor no devolvió un puerto utilizable.",
    co_frontend_246: "El puente de escritorio no está disponible (comando `{v0}`). Esta función requiere la aplicación de escritorio.",
    // ── Verbos de accion ──────────────────────────────────────────
    c_reintentar: "Reintentar",
    c_cerrar: "Cerrar",
    c_cancelar: "Cancelar",
    c_guardar: "Guardar",
    c_descargar: "Descargar",
    c_copiar: "Copiar",
    c_copiado: "Copiado",
    c_ver_mas: "Ver más",
    c_ver_menos: "Ver menos",
    c_iniciar_sesion: "Iniciar sesión",
    c_lanzar_pipeline: "Lanzar pipeline",
    c_que_significa: "Qué significa",

    // ── Estados y magnitudes compartidas ─────────────────────────
    c_estado: "Estado",
    c_log_status_inactive: "INACTIVO",
    c_log_status_error: "ERROR",
    c_log_status_processing: "PROCESANDO",
    c_score: "Score",
    c_afinidad: "Afinidad",
    c_pendiente: "Pendiente",
    c_motor: "Motor",
    c_cadena: "Cadena",
    c_exhaustividad: "Exhaustividad",
    c_abrir_menu: "Abrir menú",
    c_beta: "Beta",
    c_cerrar_menu: "Cerrar menú",
    c_exportar_zip: "Exportar paquete ZIP",
    c_nombre: "Nombre",
    c_reintentar_seguimiento: "Reintentar seguimiento",

    // ── Estados ───────────────────────────────────────────────────
    c_cargando: "Cargando…",
    c_loading_molecular_editor: "Cargando editor molecular…",
    c_download_models: "Descargar modelos",
    c_calculando: "Calculando…",
    c_sin_datos: "Sin datos",
    c_no_definido: "No definido",
    c_no_calculado: "No calculado",
    c_no_registrado: "No registrado",
    c_no_disponible: "No disponible",

    // ── Unidades y magnitudes ─────────────────────────────────────
    c_segundos: "s",
    c_minutos: "min",
    c_horas: "h",
    c_kcal_mol: "kcal/mol",
    c_angstrom: "Å",

    // ── Duraciones compuestas ─────────────────────────────────────
    c_dur_segundos: "{n} s",
    c_dur_minutos: "{n} min",
    c_dur_minutos_segundos: "{m} min {s} s",
    c_dur_horas: "{n} h",
    c_dur_horas_minutos: "{h} h {m} min",

    // ── Fallo de conexion ─────────────────────────────────────────
    c_sin_motor:
      "No se pudo establecer contacto con el motor local de MolDesign. "
      + "Revisa su estado en la aplicación y vuelve a intentarlo.",

    // ── Login ─────────────────────────────────────────────────────
    c_login_email: "Correo electrónico",
  },
  en: {
    c_engine_idle: "Engine idle",
    c_engine_starting: "Starting engine…",
    c_engine_ready: "Engine ready",
    c_engine_not_installed: "Engine not installed",
    c_engine_spawn_failed: "The engine could not start",
    c_engine_health_failed: "The engine started but failed the health check",
    c_engine_disconnected: "The engine disconnected",
    c_engine_explain_not_installed: "Part of the compute runtime is missing from disk (Python, the backend, or Vina). Repair or reinstall MolDesign; optional models do not replace this runtime.",
    c_engine_explain_spawn_failed: "The engine process did not run. This is usually due to a permission issue or a missing executable.",
    c_engine_explain_health_failed: "The process started but did not identify itself as the MolDesign backend. This usually means an outdated copy of the backend is running.",
    c_engine_explain_disconnected: "The engine was available and stopped responding. Evaluation cannot continue until it returns.",
    c_engine_unknown: "The engine returned a state that this version does not recognize.",
    c_engine_lost_port: "The engine stopped responding on port {port}.",
    c_help_meaning: "What it means: {title}",
    c_external_failed: "The link could not be opened",
    c_local_doc_failed: "Could not load {path}. The document ships with the application, so this indicates incomplete packaging. ({cause})",
    co_frontend_216: "The desktop bridge is not available, so the backend port cannot be determined. It is not guessed: another program could be listening there.",
    co_frontend_217: "The engine did not return a usable port.",
    co_frontend_246: "The desktop bridge is not available (command `{v0}`). This feature requires the desktop application.",
    c_reintentar: "Retry",
    c_cerrar: "Close",
    c_cancelar: "Cancel",
    c_guardar: "Save",
    c_descargar: "Download",
    c_copiar: "Copy",
    c_copiado: "Copied",
    c_ver_mas: "Show more",
    c_ver_menos: "Show less",
    c_iniciar_sesion: "Sign in",
    c_lanzar_pipeline: "Launch pipeline",
    c_que_significa: "What this means",

    // ── Shared statuses and metrics ───────────────────────────────
    c_estado: "Status",
    c_log_status_inactive: "INACTIVE",
    c_log_status_error: "ERROR",
    c_log_status_processing: "PROCESSING",
    c_score: "Score",
    c_afinidad: "Affinity",
    c_pendiente: "Pending",
    c_motor: "Engine",
    c_cadena: "Chain",
    c_exhaustividad: "Exhaustiveness",
    c_abrir_menu: "Open menu",
    c_beta: "Beta",
    c_cerrar_menu: "Close menu",
    c_exportar_zip: "Export ZIP package",
    c_nombre: "Name",
    c_reintentar_seguimiento: "Retry tracking",

    c_cargando: "Loading…",
    c_loading_molecular_editor: "Loading the molecular editor…",
    c_download_models: "Download models",
    c_calculando: "Calculating…",
    c_sin_datos: "No data",
    c_no_definido: "Not defined",
    c_no_calculado: "Not calculated",
    c_no_registrado: "Not recorded",
    c_no_disponible: "Not available",

    c_segundos: "s",
    c_minutos: "min",
    c_horas: "h",
    c_kcal_mol: "kcal/mol",
    c_angstrom: "Å",

    c_dur_segundos: "{n} s",
    c_dur_minutos: "{n} min",
    c_dur_minutos_segundos: "{m} min {s} s",
    c_dur_horas: "{n} h",
    c_dur_horas_minutos: "{h} h {m} min",

    c_sin_motor:
      "Could not reach the local MolDesign engine. "
      + "Check its status in the application and try again.",

    // ── Login ─────────────────────────────────────────────────────
    c_login_email: "Email",
  },
};
