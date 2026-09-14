// =====================================================================
// Evaluación — la pantalla donde se lanza y se lee una corrida
// =====================================================================
//
// Es la superficie que un revisor de la Store abre justo después de la portada,
// y la que hasta ahora estaba entera en castellano fijo aunque el paquete
// declarara `en-US`.
//
// DOS REGLAS DE TRADUCCIÓN QUE AQUÍ IMPORTAN MÁS QUE EN OTRAS PANTALLAS:
//
//   1. Una advertencia no se suaviza al cruzar de idioma. «El ligando acoplará
//      contra parte de la cavidad» dice que el número es incompleto; la versión
//      inglesa tiene que decir lo mismo con la misma fuerza, no «may dock
//      against part of the cavity».
//
//   2. Lo que el producto NO afirma sigue sin afirmarlo. «No certifica validez
//      científica» es una frontera legal, no una fórmula de cortesía.

import type { ModuloDeTraduccion } from "./index";

export const evaluacion: ModuloDeTraduccion = {
  es: {
    // ── Sistema estructural del caso ──────────────────────────────
    ev_sistema_fijado: "Sistema estructural fijado",
    ev_sistema_provisional: "Sistema estructural provisional",
    ev_sistema_desde_corrida: "desde la corrida {taskId}…",
    ev_sistema_provisional_detalle:
      "Todavía no ha terminado ninguna corrida en este sistema, así que aún puedes "
      + "corregir receptor o caja. Quedará fijado cuando una corrida termine.",
    ev_sistema_fijado_detalle:
      "Puedes evaluar nuevos SMILES y cambiar el protocolo en este sistema. "
      + "Para cambiar receptor, caja o residuos, crea otro caso.",
    ev_opciones_fijadas:
      "Caja y residuos fijados por la primera corrida que terminó. "
      + "El protocolo se puede cambiar.",

    // ── Selector de receptor ──────────────────────────────────────
    ev_elige_receptor: "Elige receptor",
    ev_receptor_elegido: "Receptor elegido: {pdbId}",
    ev_cargando_receptor: "Cargando {pdbId}…",
    ev_cambiar: "Cambiar",
    ev_seleccionar: "Seleccionar",
    ev_sistema_fijado_corto: "Sistema fijado",

    // ── Botonera ──────────────────────────────────────────────────
    ev_opciones: "Opciones",
    ev_ver_resultados: "Ver resultados",
    ev_ocultar_resultados: "Ocultar resultados",
    ev_evaluaciones_anteriores: "Evaluaciones anteriores",
    ev_sin_evaluaciones_aun: "Este caso todavía no ha lanzado ninguna evaluación.",
    ev_ver_evaluaciones_anteriores: "Ver las evaluaciones anteriores de este caso",
    ev_falta_smiles_o_receptor: "Añade un SMILES válido y selecciona un receptor",
    ev_cancelar_corrida:
      "Cancela la evaluación y mata todos los procesos (docking, MM-GBSA, etc.)",

    // ── Progreso y recuperación ───────────────────────────────────
    ev_procesando: "Procesando resultados del pipeline",
    ev_error_pipeline: "Error desconocido durante el pipeline.",
    ev_no_se_abrio_resultado: "No se pudo abrir el resultado guardado",
    ev_consultando_evidencia:
      "Estamos consultando la evidencia persistida de la última corrida.",
    ev_reintentar_recuperacion: "Reintentar recuperación",

    // ── Estimación de duración ────────────────────────────────────
    ev_duracion_estimada: "Duración estimada",
    ev_duracion_estimada_cohorte: "Duración estimada de la cohorte",
    ev_calibrado_con_tu_equipo: "Calibrado con tu equipo",
    ev_sin_historial_todavia: "Sin historial todavía",
    ev_solo_primera_vez: "Sólo esta primera vez: ",
    ev_anade_entre: "Añade entre {min} y {max}.",
    ev_de_que_se_compone: "De qué se compone",

    // ── Certificación ─────────────────────────────────────────────
    ev_certificar_aviso:
      "Registra en Solana el compuesto, target, señal de score y fecha; "
      + "no certifica validez científica ni sustituye el dossier.",

    // ── Informe ───────────────────────────────────────────────────
    ev_reporte_vista_previa: "Reporte científico — vista previa",
    ev_cerrar_vista_previa: "Cerrar vista previa del reporte",

    // ── MM-GBSA ───────────────────────────────────────────────────
    ev_mmgbsa_titulo: "MM-GBSA — estimación de ΔG de unión",
    ev_mmgbsa_cerrar: "Cerrar cálculo MM-GBSA",
    ev_mmgbsa_que_calcula: "¿Qué calcula?",
    ev_mmgbsa_pasos: "Pasos de minimización",
    ev_mmgbsa_pasos_rapido: "500 pasos (rápido)",
    ev_mmgbsa_pasos_estandar: "1000 pasos (estándar)",
    ev_mmgbsa_pasos_maximo: "5000 pasos (máximo)",
    ev_mmgbsa_configura: "Configura los parámetros y ejecuta el cálculo",
    ev_mmgbsa_depende_gpu:
      "El tiempo depende del número de pasos y la disponibilidad de GPU.",
    ev_mmgbsa_en_curso: "Minimización en curso…",
    ev_mmgbsa_puede_tardar:
      "Este proceso puede tomar entre 30 segundos y varios minutos según el hardware.",
    ev_mmgbsa_fallo: "El cálculo falló",
    ev_mmgbsa_puedes_reintentar: "Puedes reintentar con el botón de abajo.",
    ev_mmgbsa_electrostatica: "Electrostática",
    ev_mmgbsa_solvatacion_gb: "Solvatación GB (polar)",
    ev_mmgbsa_solvatacion_sasa: "Solvatación SASA (no polar)",
    ev_mmgbsa_estimacion: "Estimación MM-GBSA (ΔG)",
    ev_mmgbsa_como_usarlo: "Cómo se puede usar este número.",
    ev_mmgbsa_descomposicion: "Descomposición de energía por contribución",
    ev_mmgbsa_contribucion_negativa: "Contribución negativa en este modelo",
    ev_mmgbsa_contribucion_positiva: "Contribución positiva en este modelo",

    // ── ADMET ─────────────────────────────────────────────────────
    ev_admet_requiere_corrida:
      "Requiere una corrida terminada con una molécula identificable.",
    ev_admet_no_guardado:
      "El perfil se calculó pero NO se pudo guardar: el dossier de esta corrida "
      + "no lo incluirá.",

    // ── Miscelánea de resultados ──────────────────────────────────
    ev_ums_historico: "UMS histórico",
    ev_click_para_calcular: "Clic para calcular",
    ev_no_produjo_salida: "no produjo salida",
    ev_no_produjeron_salida: "no produjeron salida",
  },
  en: {
    ev_sistema_fijado: "Structural system locked",
    ev_sistema_provisional: "Structural system provisional",
    ev_sistema_desde_corrida: "from run {taskId}…",
    ev_sistema_provisional_detalle:
      "No run has finished on this system yet, so you can still correct the receptor "
      + "or the box. It will be locked once a run finishes.",
    ev_sistema_fijado_detalle:
      "You can evaluate new SMILES and change the protocol on this system. "
      + "To change receptor, box or residues, create another case.",
    ev_opciones_fijadas:
      "Box and residues locked by the first run that finished. "
      + "The protocol can still be changed.",

    ev_elige_receptor: "Choose a receptor",
    ev_receptor_elegido: "Receptor: {pdbId}",
    ev_cargando_receptor: "Loading {pdbId}…",
    ev_cambiar: "Change",
    ev_seleccionar: "Select",
    ev_sistema_fijado_corto: "System locked",

    ev_opciones: "Options",
    ev_ver_resultados: "Show results",
    ev_ocultar_resultados: "Hide results",
    ev_evaluaciones_anteriores: "Previous evaluations",
    ev_sin_evaluaciones_aun: "This case has not launched any evaluation yet.",
    ev_ver_evaluaciones_anteriores: "See the previous evaluations of this case",
    ev_falta_smiles_o_receptor: "Enter a valid SMILES and select a receptor",
    ev_cancelar_corrida:
      "Cancels the evaluation and kills every process (docking, MM-GBSA, and so on)",

    ev_procesando: "Processing pipeline results",
    ev_error_pipeline: "Unknown error during the pipeline.",
    ev_no_se_abrio_resultado: "Could not open the saved result",
    ev_consultando_evidencia:
      "We are querying the stored evidence of the last run.",
    ev_reintentar_recuperacion: "Retry recovery",

    ev_duracion_estimada: "Estimated duration",
    ev_duracion_estimada_cohorte: "Estimated duration of the cohort",
    ev_calibrado_con_tu_equipo: "Calibrated with your machine",
    ev_sin_historial_todavia: "No history yet",
    ev_solo_primera_vez: "This first time only: ",
    ev_anade_entre: "Adds between {min} and {max}.",
    ev_de_que_se_compone: "What it is made of",

    ev_certificar_aviso:
      "Records the compound, target, score signal and date on Solana; "
      + "it does not certify scientific validity and does not replace the dossier.",

    ev_reporte_vista_previa: "Scientific report — preview",
    ev_cerrar_vista_previa: "Close report preview",

    ev_mmgbsa_titulo: "MM-GBSA — binding ΔG estimate",
    ev_mmgbsa_cerrar: "Close MM-GBSA calculation",
    ev_mmgbsa_que_calcula: "What does it calculate?",
    ev_mmgbsa_pasos: "Minimisation steps",
    ev_mmgbsa_pasos_rapido: "500 steps (fast)",
    ev_mmgbsa_pasos_estandar: "1000 steps (standard)",
    ev_mmgbsa_pasos_maximo: "5000 steps (maximum)",
    ev_mmgbsa_configura: "Set the parameters and run the calculation",
    ev_mmgbsa_depende_gpu:
      "The time depends on the number of steps and on GPU availability.",
    ev_mmgbsa_en_curso: "Minimisation running…",
    ev_mmgbsa_puede_tardar:
      "This can take between 30 seconds and several minutes depending on the hardware.",
    ev_mmgbsa_fallo: "The calculation failed",
    ev_mmgbsa_puedes_reintentar: "You can retry with the button below.",
    ev_mmgbsa_electrostatica: "Electrostatics",
    ev_mmgbsa_solvatacion_gb: "GB solvation (polar)",
    ev_mmgbsa_solvatacion_sasa: "SASA solvation (non-polar)",
    ev_mmgbsa_estimacion: "MM-GBSA estimate (ΔG)",
    ev_mmgbsa_como_usarlo: "How this number can be used.",
    ev_mmgbsa_descomposicion: "Energy decomposition by contribution",
    ev_mmgbsa_contribucion_negativa: "Negative contribution in this model",
    ev_mmgbsa_contribucion_positiva: "Positive contribution in this model",

    ev_admet_requiere_corrida:
      "Requires a finished run with an identifiable molecule.",
    ev_admet_no_guardado:
      "The profile was calculated but could NOT be saved: the dossier of this run "
      + "will not include it.",

    ev_ums_historico: "Historical UMS",
    ev_click_para_calcular: "Click to calculate",
    ev_no_produjo_salida: "produced no output",
    ev_no_produjeron_salida: "produced no output",
  },
};
