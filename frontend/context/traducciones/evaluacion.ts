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
    ev_recovery_deadline: "{label} excedió {seconds} segundos.",
    ev_frontend_205: "No se pudo descargar el complejo 3D",
    ev_frontend_239: "La comprobación previa no se pudo completar (HTTP {v0}). Revisa el estado del motor y vuelve a intentarlo.",
    ev_frontend_067: "No se pudo confirmar la cancelación: {v0}. ",
    ev_frontend_069: "No se pudo descargar el certificado: {v0}",
    ev_frontend_070: "No se pudo descargar el complejo: {v0}",
    ev_frontend_071: "Se perdió la conexión con el servidor. No se sabe cómo terminó la tarea.",
    ev_frontend_072: "No se pudieron cargar los receptores: {v0}",
    ev_frontend_073: "El backend no devolvió el resultado persistido de la corrida.",
    ev_frontend_074: "El resultado está guardado, pero tu sesión caducó. Inicia sesión de nuevo para recuperarlo.",
    ev_frontend_075: "El resultado está guardado, pero pertenece a otra sesión. Inicia sesión con la cuenta que ejecutó esta corrida.",
    ev_frontend_076: "El resultado sigue guardado, pero el motor local no está disponible. Comprueba el estado del motor y vuelve a intentarlo.",
    ev_frontend_077: "El resultado sigue referenciado por este caso, pero no se pudo recuperar: {v0}",
    // ── Estado y resultados ───────────────────────────────────────
    ev_comprobando_visor: "Comprobando compatibilidad del visor 3D…",
    // SOL-10: el editor de un caso nuevo muestra una molécula de muestra
    // que NO es la hipótesis del usuario. Sin esta seña, estructura y
    // SMILES parecían válidos mientras el botón pedía un ligando.
    ev_editor_ejemplo:
      "Ejemplo: lo que ves es una molécula de muestra, no la hipótesis de "
      + "este caso. Si pulsas «Ejecutar evaluación» se evalúa tal cual; escribe "
      + "o dibuja tu ligando para evaluar otro.",
    ev_estructura_smiles: "Estructura SMILES",
    ev_evaluando: "Evaluando…",
    ev_reiniciar: "Reiniciar",
    ev_recuperando_resultados: "Recuperando resultados guardados",
    ev_post_hoc_badge: "a posteriori",
    ev_fuera_de_uso: "desactivado",
    ev_ver_en_solana_explorer: "Ver en Solana Explorer",
    ev_descargar_informe: "Descargar informe de evaluación",
    ev_descargar_complejo_pdb: "Complejo .PDB",
    ev_guardar_en_moldex: "Guardar en MolDex",
    ev_registrar_integridad_solana: "Registrar integridad en Solana",
    ev_ejecutar: "Ejecutar evaluación",
    ev_peticion_preparacion: "Desde Preparación: se cargó el ligando {smiles} con «Tautómero del ligando: {modo}». Revisa y pulsa «Ejecutar evaluación» para volver a evaluar.",
    ev_fallo: "La evaluación falló",
    ev_cancelada: "Evaluación cancelada",
    ev_sin_resultados_titulo: "La evaluación terminó sin resultados",
    ev_sin_resultados_detalle:
      "El pipeline reportó éxito pero el resultado no llegó a la interfaz. Esto "
      + "suele ser un problema de serialización del resultado en el backend (no "
      + "un problema del acoplamiento). Reintenta la evaluación o revisa los logs "
      + "del backend.",
    ev_sin_resultados_aun: "Sin resultados todavía",
    ev_elige_para_empezar:
      "Elige un receptor y una molécula, y ejecuta la evaluación para ver el "
      + "reporte completo del acoplamiento molecular.",
    ev_pipeline_degradado: "Pipeline degradado en esta corrida",
    ev_peso_no_reportado: "peso no reportado",
    ev_pesos_no_calibrados:
      "Pesos serializados por el pipeline · no representan confianza calibrada",
    ev_vista_previa_informe: "Ver informe de evaluación",
    ev_mmgbsa_ejecutar: "Ejecutar cálculo MM-GBSA",
    ev_mmgbsa_nombre_completo:
      "Mecánica molecular / área de superficie de Born generalizada",
    ev_mmgbsa_pose_a_refinar: "Pose a refinar",
    ev_mmgbsa_pose_numero: "Pose n.º {rank}",
    ev_mmgbsa_calculando_pasos:
      "Calculando con OpenMM… ({steps} pasos)",
    ev_mmgbsa_error_desconocido:
      "Error desconocido al ejecutar MM-GBSA.",
    ev_mmgbsa_motor_predeterminado: "OpenMM",
    ev_mmgbsa_van_der_waals: "Van der Waals",
    ev_mmgbsa_explicacion:
      "MM-GBSA post-hoc minimiza la pose con OpenMM y combina términos de "
      + "mecánica molecular, Generalized Born y superficie accesible al solvente "
      + "para estimar un ΔG dependiente del protocolo. El signo y la magnitud "
      + "sólo deben compararse dentro de la misma configuración; no sustituyen "
      + "una afinidad experimental.",
    ev_mmgbsa_post_hoc:
      "Señal post-hoc dependiente del protocolo; no clasifica por sí sola al "
      + "ligando como candidato.",
    ev_mmgbsa_sin_descomposicion:
      "La descomposición por contribución (vdW, electrostática, GB, SASA) no está "
      + "disponible en este endpoint. El valor reportado es la diferencia "
      + "calculada entre complejo, receptor y ligando sobre la pose de docking "
      + "minimizada; depende de la parametrización y no es una medición "
      + "experimental.",

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
    ev_elige_receptor_ejecutar: "Elige un receptor antes de ejecutar.",
    ev_elige_ligando_ejecutar: "Introduce o dibuja un ligando antes de ejecutar.",
    ev_bloqueante_tecnico: "La comprobación previa encontró {count} bloqueante técnico: {items}. La corrida fallaría igual, más tarde.",
    ev_bloqueantes_tecnicos: "La comprobación previa encontró {count} bloqueantes técnicos: {items}. La corrida fallaría igual, más tarde.",
    ev_receptor_elegido: "Receptor elegido: {pdbId}",
    ev_cargando_receptor: "Cargando {pdbId}…",
    ev_cambiar: "Cambiar",
    ev_seleccionar: "Seleccionar",
    ev_sistema_fijado_corto: "Sistema fijado",

    // ── Botonera ──────────────────────────────────────────────────
    ev_opciones: "Opciones",
    ev_parametros_corrida: "Parámetros de la evaluación",
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
    ev_sello_otra_corrida:
      "El sello describe una corrida anterior de esta molécula, no la que se "
      + "muestra: no atestigua estas cifras. Moldex enseña las dos.",

    // ── Informe ───────────────────────────────────────────────────
    ev_reporte_vista_previa: "Informe de evaluación — vista previa",
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
    ev_aviso_sin_severidad_pie:
      "El motor emitió este aviso como texto, sin código ni severidad. El texto es el que "
      + "emitió; su importancia no se dedujo de él.",
    ev_chat_no_pulsado: "No se pulsó Evaluar: {motivo}.",
    ev_chat_motivo_en_marcha: "No se pulsó Evaluar: hay una evaluación en marcha en este caso.",
    ev_chat_motivo_deshabilitado: "No se pulsó Evaluar: el botón está deshabilitado en este momento.",
    ev_chat_motivo_ocupada: "No se pulsó Evaluar: la pantalla está ocupada con otra operación.",
    ev_chat_motivo_boton_perdido: "No se pulsó Evaluar: el botón dejó de estar disponible justo antes de pulsarlo.",
    ev_chat_ocupado_trabajo: "el espacio de casos tiene trabajo en curso (una evaluación u otra operación)",
    ev_chat_ocupado_otra: "ya hay otra evaluación pedida desde el chat esperando respuesta",
    ev_chat_ocupado_receptor: "se está asignando un receptor desde el chat",
    ev_chat_ocupado_smiles: "se está cargando un SMILES desde el chat",
    ev_chat_ocupado_corrida: "hay una corrida aceptada sin registrar en el caso",
    ev_chat_caso_sin_abrir: "No se pudo abrir el caso: hay trabajo sin guardar o en curso.",
    ev_chat_plazo: "Se agotó el plazo sin respuesta. Última etapa: {etapa}.",
    ev_chat_sin_etapa: "la petición no llegó a ninguna etapa",
    ev_chat_etapa_recibida_casos: "el espacio de casos recibió la petición",
    ev_chat_etapa_caso_abierto: "caso abierto; se pidió la vista Evaluación y la pantalla aún no confirmó",
    ev_chat_etapa_recibida_pantalla: "la pantalla de Evaluación recibió la petición",
    ev_chat_etapa_esperando:
      "esperando a que la pantalla esté lista ({estado}: puede ejecutar={puede}, botón={boton}, "
      + "ocupada={ocupada}, deshabilitado={deshabilitado}, bloqueo={bloqueo})",
    ev_chat_etapa_resaltado: "botón resaltado, a punto de pulsarlo",
    ev_chat_etapa_pulsado: "botón Evaluar pulsado; esperando la comprobación previa y el envío",
    ev_chat_etapa_envio: "se inició el envío; comprobando y enviando la evaluación",
  },
  en: {
    ev_recovery_deadline: "{label} exceeded {seconds} seconds.",
    ev_frontend_205: "The 3D complex could not be downloaded",
    ev_frontend_239: "The preflight check could not be completed (HTTP {v0}). Check the engine status and try again.",
    ev_frontend_067: "Cancellation could not be confirmed: {v0}. ",
    ev_frontend_069: "The certificate could not be downloaded: {v0}",
    ev_frontend_070: "The complex could not be downloaded: {v0}",
    ev_frontend_071: "The connection to the server was lost. It is not known how the task ended.",
    ev_frontend_072: "The receptors could not be loaded: {v0}",
    ev_frontend_073: "The backend did not return the persisted run result.",
    ev_frontend_074: "The result is saved, but your session expired. Sign in again to recover it.",
    ev_frontend_075: "The result is saved, but it belongs to another session. Sign in with the account that ran this run.",
    ev_frontend_076: "The result is still saved, but the local engine is not available. Check the engine status and try again.",
    ev_frontend_077: "This case still references the result, but it could not be recovered: {v0}",
    ev_comprobando_visor: "Checking 3D viewer compatibility…",
    ev_editor_ejemplo:
      "Example: what you see is a sample molecule, not this case's "
      + "hypothesis. If you press “Run evaluation” it is evaluated as is; type "
      + "or draw your ligand to evaluate a different one.",
    ev_estructura_smiles: "SMILES structure",
    ev_evaluando: "Evaluating…",
    ev_reiniciar: "Restart",
    ev_recuperando_resultados: "Recovering saved results",
    ev_post_hoc_badge: "post hoc",
    ev_fuera_de_uso: "off",
    ev_ver_en_solana_explorer: "View in Solana Explorer",
    ev_descargar_informe: "Download evaluation report",
    ev_descargar_complejo_pdb: "PDB complex",
    ev_guardar_en_moldex: "Save to MolDex",
    ev_registrar_integridad_solana: "Record integrity on Solana",
    ev_ejecutar: "Run evaluation",
    ev_peticion_preparacion: "From Preparation: the ligand {smiles} was loaded with “Ligand tautomer: {modo}”. Review it and press “Run evaluation” to evaluate again.",
    ev_fallo: "The evaluation failed",
    ev_cancelada: "Evaluation canceled",
    ev_sin_resultados_titulo: "The evaluation finished with no results",
    ev_sin_resultados_detalle:
      "The pipeline reported success but the result never reached the interface. "
      + "This is usually a result-serialization problem in the backend (not a "
      + "docking problem). Retry the evaluation or check the backend logs.",
    ev_sin_resultados_aun: "No results yet",
    ev_elige_para_empezar:
      "Choose a receptor and a molecule, then run the evaluation to see the full "
      + "molecular docking report.",
    ev_pipeline_degradado: "Pipeline degraded on this run",
    ev_peso_no_reportado: "weight not reported",
    ev_pesos_no_calibrados:
      "Weights serialized by the pipeline · they do not represent calibrated "
      + "confidence",
    ev_vista_previa_informe: "View evaluation report",
    ev_mmgbsa_ejecutar: "Run MM-GBSA calculation",
    ev_mmgbsa_nombre_completo:
      "Molecular Mechanics / Generalized Born Surface Area",
    ev_mmgbsa_pose_a_refinar: "Pose to refine",
    ev_mmgbsa_pose_numero: "Pose #{rank}",
    ev_mmgbsa_calculando_pasos:
      "Calculating with OpenMM… ({steps} steps)",
    ev_mmgbsa_error_desconocido:
      "Unknown error while running MM-GBSA.",
    ev_mmgbsa_motor_predeterminado: "OpenMM",
    ev_mmgbsa_van_der_waals: "Van der Waals",
    ev_mmgbsa_explicacion:
      "Post-hoc MM-GBSA minimizes the pose with OpenMM and combines molecular "
      + "mechanics, Generalized Born and solvent-accessible surface terms to "
      + "estimate a protocol-dependent ΔG. Its sign and magnitude may only be "
      + "compared within the same configuration; they do not replace an "
      + "experimental affinity.",
    ev_mmgbsa_post_hoc:
      "Post-hoc, protocol-dependent signal; on its own it does not qualify the "
      + "ligand as a candidate.",
    ev_mmgbsa_sin_descomposicion:
      "The per-contribution decomposition (vdW, electrostatics, GB, SASA) is not "
      + "available from this endpoint. The reported value is the difference "
      + "calculated between complex, receptor and ligand over the minimized "
      + "docking pose; it depends on the parameterisation and is not an "
      + "experimental measurement.",
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
    ev_elige_receptor_ejecutar: "Choose a receptor before running.",
    ev_elige_ligando_ejecutar: "Enter or draw a ligand before running.",
    ev_bloqueante_tecnico: "Preflight found {count} technical blocker: {items}. The run would fail later anyway.",
    ev_bloqueantes_tecnicos: "Preflight found {count} technical blockers: {items}. The run would fail later anyway.",
    ev_receptor_elegido: "Receptor: {pdbId}",
    ev_cargando_receptor: "Loading {pdbId}…",
    ev_cambiar: "Change",
    ev_seleccionar: "Select",
    ev_sistema_fijado_corto: "System locked",

    ev_opciones: "Options",
    ev_parametros_corrida: "Evaluation parameters",
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
    ev_sello_otra_corrida:
      "The seal describes an earlier run of this molecule, not the one shown: "
      + "it does not attest these figures. Moldex shows both.",

    ev_reporte_vista_previa: "Evaluation report — preview",
    ev_cerrar_vista_previa: "Close report preview",

    ev_mmgbsa_titulo: "MM-GBSA — binding ΔG estimate",
    ev_mmgbsa_cerrar: "Close MM-GBSA calculation",
    ev_mmgbsa_que_calcula: "What does it calculate?",
    ev_mmgbsa_pasos: "Minimization steps",
    ev_mmgbsa_pasos_rapido: "500 steps (fast)",
    ev_mmgbsa_pasos_estandar: "1000 steps (standard)",
    ev_mmgbsa_pasos_maximo: "5000 steps (maximum)",
    ev_mmgbsa_configura: "Set the parameters and run the calculation",
    ev_mmgbsa_depende_gpu:
      "The time depends on the number of steps and on GPU availability.",
    ev_mmgbsa_en_curso: "Minimization running…",
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
    ev_aviso_sin_severidad_pie:
      "The engine emitted this warning as plain text, with no code or severity. The text is "
      + "what it emitted; its importance was not inferred from it.",
    ev_chat_no_pulsado: "Evaluate was not pressed: {motivo}.",
    ev_chat_motivo_en_marcha: "Evaluate was not pressed: an evaluation is running in this case.",
    ev_chat_motivo_deshabilitado: "Evaluate was not pressed: the button is disabled right now.",
    ev_chat_motivo_ocupada: "Evaluate was not pressed: the screen is busy with another operation.",
    ev_chat_motivo_boton_perdido: "Evaluate was not pressed: the button stopped being available just before pressing it.",
    ev_chat_ocupado_trabajo: "the case workspace has work in progress (an evaluation or another operation)",
    ev_chat_ocupado_otra: "another evaluation requested from the chat is waiting for an answer",
    ev_chat_ocupado_receptor: "a receptor is being assigned from the chat",
    ev_chat_ocupado_smiles: "a SMILES is being loaded from the chat",
    ev_chat_ocupado_corrida: "the case has an accepted run that is not registered yet",
    ev_chat_caso_sin_abrir: "The case could not be opened: there is unsaved work or work in progress.",
    ev_chat_plazo: "The time limit ran out with no answer. Last stage: {etapa}.",
    ev_chat_sin_etapa: "the request did not reach any stage",
    ev_chat_etapa_recibida_casos: "the case workspace received the request",
    ev_chat_etapa_caso_abierto: "case opened; the Evaluation view was requested and the screen has not confirmed yet",
    ev_chat_etapa_recibida_pantalla: "the Evaluation screen received the request",
    ev_chat_etapa_esperando:
      "waiting for the screen to be ready ({estado}: can run={puede}, button={boton}, "
      + "busy={ocupada}, disabled={deshabilitado}, blocked={bloqueo})",
    ev_chat_etapa_resaltado: "button highlighted, about to press it",
    ev_chat_etapa_pulsado: "Evaluate button pressed; waiting for the preflight check and the submission",
    ev_chat_etapa_envio: "submission started; checking and sending the evaluation",
  },
};
