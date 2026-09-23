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
    c_score: "Score",
    c_afinidad: "Afinidad",
    c_pendiente: "Pendiente",
    c_motor: "Motor",
    c_cadena: "Cadena",
    c_exhaustividad: "Exhaustividad",
    c_exportar_zip: "Exportar paquete ZIP",
    c_nombre: "Nombre",
    c_reintentar_seguimiento: "Reintentar seguimiento",

    // ── Estados ───────────────────────────────────────────────────
    c_cargando: "Cargando…",
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
    c_score: "Score",
    c_afinidad: "Affinity",
    c_pendiente: "Pending",
    c_motor: "Engine",
    c_cadena: "Chain",
    c_exhaustividad: "Exhaustiveness",
    c_exportar_zip: "Export ZIP package",
    c_nombre: "Name",
    c_reintentar_seguimiento: "Retry tracking",

    c_cargando: "Loading…",
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
