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
// «Grid box», «docking», «score» y «pose» se quedan como están en los dos
// idiomas: son los términos del campo y traducirlos alejaría al usuario de la
// literatura que va a leer después.

import type { ModuloDeTraduccion } from "./index";

export const opciones: ModuloDeTraduccion = {
  es: {
    op_titulo: "Opciones de evaluación",
    op_opciones_avanzadas: "Opciones avanzadas",
    op_sub_herramienta: "¿Con qué herramienta?",
    op_sub_donde: "¿Dónde acoplar?",
    op_sub_recursos: "¿Con cuántos recursos?",
    op_subtitulo:
      "Configura el motor, el bolsillo de unión y los recursos antes de ejecutar",
    op_cerrar: "Cerrar opciones de evaluación",
    op_aplicar: "Aplicar configuración",

    // ── Motor ─────────────────────────────────────────────────────
    op_motor_docking: "Motor de docking",
    op_moleculas_pequenas: "Moléculas pequeñas",
    op_precision_gnn: "Precisión GNN",
    op_no_aplica: "No aplica para el motor seleccionado",

    // ── Bolsillo ──────────────────────────────────────────────────
    op_parametros_bolsillo: "Parámetros del bolsillo",
    op_centro_grid: "Centro del grid box (Å)",
    op_dimensiones_grid: "Dimensiones del grid box (Å)",
    op_tamano_x: "Tamaño X",
    op_tamano_y: "Tamaño Y",
    op_tamano_z: "Tamaño Z",
    op_parametros_busqueda: "Parámetros de búsqueda",
    op_grid_explicacion:
      "El grid box define la región del espacio donde Vina buscará poses del "
      + "ligando. Un grid más grande = búsqueda más exhaustiva, pero más lenta.",
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
      "Define qué residuos del bolsillo guían la búsqueda. Desmarca los que no "
      + "quieras considerar.",
    op_hotspots_activos: "({activos}/{total} activos)",
    op_marcar_todos: "Marcar todos",
    op_desmarcar_todos: "Desmarcar todos",

    // ── Recursos y pipeline ───────────────────────────────────────
    op_recursos: "Recursos de cómputo",
    op_modulos_pipeline: "Módulos del pipeline",

    // ── Preparación del ligando ───────────────────────────────────
    op_preparacion_ligando: "Preparación del ligando",
    op_ph_protonacion: "pH de protonación",
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
  },
  en: {
    op_titulo: "Evaluation options",
    op_opciones_avanzadas: "Advanced options",
    op_sub_herramienta: "With which tool?",
    op_sub_donde: "Where to dock?",
    op_sub_recursos: "With how many resources?",
    op_subtitulo:
      "Set the engine, the binding pocket and the resources before running",
    op_cerrar: "Close evaluation options",
    op_aplicar: "Apply configuration",

    op_motor_docking: "Docking engine",
    op_moleculas_pequenas: "Small molecules",
    op_precision_gnn: "GNN precision",
    op_no_aplica: "Does not apply to the selected engine",

    op_parametros_bolsillo: "Pocket parameters",
    op_centro_grid: "Grid box centre (Å)",
    op_dimensiones_grid: "Grid box dimensions (Å)",
    op_tamano_x: "Size X",
    op_tamano_y: "Size Y",
    op_tamano_z: "Size Z",
    op_parametros_busqueda: "Search parameters",
    op_grid_explicacion:
      "The grid box defines the region of space where Vina will search for "
      + "ligand poses. A larger grid means a more exhaustive search, but a "
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
      "Choose which pocket residues guide the search. Clear the ones you do not "
      + "want taken into account.",
    op_hotspots_activos: "({activos}/{total} active)",
    op_marcar_todos: "Select all",
    op_desmarcar_todos: "Clear all",

    op_recursos: "Compute resources",
    op_modulos_pipeline: "Pipeline modules",

    op_preparacion_ligando: "Ligand preparation",
    op_ph_protonacion: "Protonation pH",
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
  },
};
