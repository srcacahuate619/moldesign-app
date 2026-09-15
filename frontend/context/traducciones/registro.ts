// =====================================================================
// Registro científico — los experimentos que se sellaron antes de correr
// =====================================================================
//
// ESTE MÓDULO ES EL ARGUMENTO DEL PRODUCTO, y su traducción es la más delicada
// de todas: cada frase existe para no halagarse. Tres cosas no se pueden perder
// al cruzar de idioma:
//
//   1. Que los experimentos se registraron ANTES de ejecutarse, con la hipótesis
//      y el criterio escritos por adelantado. Sin ese «antes» la frase deja de
//      significar nada.
//   2. Que la mitad dijo que no, y que esos también están publicados.
//   3. Que el cociente crudo del manifest sería más halagador y se rechaza a
//      propósito, porque mezcla prerregistros —positivos por declararse, no por
//      superar nada— con experimentos que tenían un umbral real.
//
// Un inglés que suavice el punto 3 convierte una declaración de honestidad en
// una nota metodológica. Es exactamente lo contrario de lo que dice.

import type { ModuloDeTraduccion } from "./index";

export const registro: ModuloDeTraduccion = {
  es: {
    rg_cargando_paper: "Cargando el paper…",
    rg_cargando: "Cargando el registro…",
    rg_no_cargado: "No se pudo cargar el registro científico.",
    rg_sin_paper:
      "El paper de este registro todavía no está redactado. Abajo está la ficha "
      + "completa, generada del manifest sellado — que es la fuente de verdad de "
      + "todos los números de esta página.",
    rg_hipotesis: "Hipótesis.",
    rg_razon_decision: "Razón de la decisión",
    rg_lo_que_se_sostuvo: "Lo que se sostuvo, y lo que se cayó",
    rg_preregistro:
      "Cada experimento de MolDesign se registró antes de ejecutarse, con su "
      + "hipótesis y su criterio de decisión escritos por adelantado, y se selló "
      + "con el commit, la semilla, el entorno y los hashes de todo lo que tocó. "
      + "Esta página los abre todos: los que funcionaron y los que no.",
    rg_defecto_detectado: "Un defecto detectado",
    rg_despues: "después",
    rg_hipotesis_derribadas: "hipótesis derribadas",
    rg_otras_poblaciones: "Las otras poblaciones del registro",
    rg_ni_exitos_ni_fracasos:
      "Estas no son ni éxitos ni fracasos, y por eso no entran en el marcador. "
      + "Están aquí porque son la mitad del trabajo.",
    rg_activa_capa: "Activa una capa para ver esos registros.",
    rg_generado_desde: "Generado desde los manifests sellados por",

    // ── El contraste de la portada ────────────────────────────────
    rg_no_empaquetamos: "No estamos empaquetando el trabajo de otros",
    rg_detras_de_cada:
      "Detrás de cada componente hay experimentos que se registraron antes de "
      + "ejecutarse, con la hipótesis y el criterio de decisión escritos por "
      + "adelantado. La mitad dijo que no. Están todos publicados, incluidos los "
      + "que derribaron nuestras propias ideas.",
    rg_cociente_crudo:
      "El cociente crudo de decisiones del manifest sería más halagador. No lo "
      + "usamos: mezcla prerregistros —que se sellan como positivos al "
      + "declararse, no por superar nada— con experimentos que sí tenían un "
      + "umbral real. Separar las poblaciones es la única forma de que el número "
      + "signifique algo.",
    rg_abrir_registro: "Abrir el registro completo →",
  },
  en: {
    rg_cargando_paper: "Loading the paper…",
    rg_cargando: "Loading the record…",
    rg_no_cargado: "The scientific record could not be loaded.",
    rg_sin_paper:
      "The paper for this record has not been written yet. Below is the full "
      + "sheet, generated from the sealed manifest — which is the source of truth "
      + "for every number on this page.",
    rg_hipotesis: "Hypothesis.",
    rg_razon_decision: "Reason for the decision",
    rg_lo_que_se_sostuvo: "What held up, and what fell",
    rg_preregistro:
      "Every MolDesign experiment was registered before it ran, with its "
      + "hypothesis and its decision criterion written in advance, and sealed with "
      + "the commit, the seed, the environment and the hashes of everything it "
      + "touched. This page opens all of them: the ones that worked and the ones "
      + "that did not.",
    rg_defecto_detectado: "A defect found",
    rg_despues: "afterwards",
    rg_hipotesis_derribadas: "hypotheses knocked down",
    rg_otras_poblaciones: "The other populations in the record",
    rg_ni_exitos_ni_fracasos:
      "These are neither successes nor failures, which is why they do not enter "
      + "the scoreboard. They are here because they are half of the work.",
    rg_activa_capa: "Turn on a layer to see those records.",
    rg_generado_desde: "Generated from the manifests sealed by",

    rg_no_empaquetamos: "We are not repackaging other people's work",
    rg_detras_de_cada:
      "Behind every component there are experiments that were registered before "
      + "they ran, with the hypothesis and the decision criterion written in "
      + "advance. Half of them said no. They are all published, including the ones "
      + "that knocked down our own ideas.",
    rg_cociente_crudo:
      "The raw decision ratio in the manifest would be more flattering. We do not "
      + "use it: it mixes pre-registrations —which are sealed as positive by being "
      + "declared, not by passing anything— with experiments that did have a real "
      + "threshold. Separating the populations is the only way for the number to "
      + "mean anything.",
    rg_abrir_registro: "Open the full record →",
  },
};
