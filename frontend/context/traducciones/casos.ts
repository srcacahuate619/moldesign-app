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
    // ── Espacio vacío y creación ──────────────────────────────────
    ca_crear_titulo: "Crea un caso de estudio",
    ca_crear_descripcion:
      "Reúne una proteína, una hipótesis de sitio, ligandos, corridas, controles "
      + "e informes en un espacio reproducible.",
    ca_crear_boton: "Crear un caso",
    ca_solo_lo_minimo:
      "Las preguntas científicas se responden después, en «Detalles del caso». "
      + "Aquí sólo lo mínimo.",
    ca_ubicacion: "Ubicación",
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

    // ── Informe ───────────────────────────────────────────────────
    ca_informe_titulo: "Informe del caso",
    ca_volver_evaluacion: "Volver a Evaluación",
    ca_informe_anterior: "Este informe es de una corrida anterior.",
    ca_informe_anterior_detalle:
      "Los inputs del caso han cambiado desde que se ejecutó, así que no es "
      + "evidencia de la hipótesis actual. Para obtener evidencia de los inputs "
      + "de ahora hay que comprobar la preparación y volver a ejecutar.",
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
    ca_justificacion: "Justificación (obligatoria)",
    ca_justificacion_ejemplo:
      "Qué evidencia respalda esta decisión y qué límites tiene…",
  },
  en: {
    ca_crear_titulo: "Create a study case",
    ca_crear_descripcion:
      "Bring a protein, a site hypothesis, ligands, runs, controls and reports "
      + "together in one reproducible space.",
    ca_crear_boton: "Create a case",
    ca_solo_lo_minimo:
      "The scientific questions are answered later, in «Case details». Only the "
      + "essentials here.",
    ca_ubicacion: "Location",
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
    ca_inicializar_como_caso: "Initialise as a case",
    ca_ya_registrado: "The case is already registered in another folder",
    ca_carpeta_sin_caso: "Folder with no case",

    ca_historial_titulo: "Previous evaluations of this case",
    ca_historial_cerrar: "Close the case evaluation history",
    ca_sin_evaluaciones: "This case has not launched any evaluation yet.",
    ca_otra_hipotesis: "Another hypothesis",
    ca_otro_protocolo: "Another protocol",
    ca_recuperando_resultado: "Recovering the saved result of this run…",

    ca_informe_titulo: "Case report",
    ca_volver_evaluacion: "Back to Evaluation",
    ca_informe_anterior: "This report is from an earlier run.",
    ca_informe_anterior_detalle:
      "The case inputs have changed since it ran, so it is not evidence for the "
      + "current hypothesis. To get evidence for the inputs as they are now, you "
      + "have to check the preparation and run again.",
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
    ca_justificacion: "Rationale (required)",
    ca_justificacion_ejemplo:
      "What evidence supports this decision and what its limits are…",
  },
};
