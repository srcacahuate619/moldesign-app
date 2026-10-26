// =====================================================================
// Búsqueda del catálogo de receptores: por palabras, no por subcadenas
// =====================================================================
//
// QA1-004. Buscar «ACE» (la diana de un caso «Inhibición de ACE») devolvía 14
// receptores y NINGUNO era la ACE humana: casaban ALCALIGENACEAE, DEACETYLASE,
// ACETYLCHOLINESTERASE… porque el filtro era `name.includes(term)`.
//
// Decisión del propietario (2026-10-04): palabras completas y nombres primero, sin
// tocar los datos del catálogo. Aquí:
//
//   · cada palabra de la consulta tiene que casar con el COMIENZO de una palabra del
//     receptor (así «angio» sigue encontrando «angiotensin» mientras se escribe, pero
//     «ace» ya no entra por la mitad de «alcaligenaceae»);
//   · todas las palabras de la consulta tienen que casar (Y);
//   · se ignoran tildes y mayúsculas;
//   · el orden es: palabra EXACTA del nombre o PDB ID > comienzo de palabra del nombre >
//     organismo o familia.

import type { Target } from "./api";

const sinMarcas = (texto: string): string => texto.normalize("NFD").replace(/\p{M}+/gu, "").toLowerCase();

/** Palabras en minúsculas y sin tildes; los signos y guiones bajos separan. */
export function palabrasDe(texto: string | null | undefined): string[] {
  return sinMarcas(texto ?? "").split(/[^\p{L}\p{N}]+/u).filter(Boolean);
}

function mejorCoincidencia(palabras: readonly string[], token: string, exacta: number, prefijo: number): number {
  let mejor = 0;
  for (const palabra of palabras) {
    if (palabra === token) return exacta;
    if (palabra.startsWith(token)) mejor = Math.max(mejor, prefijo);
  }
  return mejor;
}

/**
 * 0 si el receptor no casa con la consulta; mayor es mejor. Una consulta vacía (o sólo
 * signos) casa con todo y devuelve 1, para que quien llama no tenga que distinguirla.
 */
export function puntuarReceptor(target: Target, consulta: string, familia?: string | null): number {
  const tokens = palabrasDe(consulta);
  if (tokens.length === 0) return 1;
  const nombre = palabrasDe(target.name);
  const id = palabrasDe(target.pdb_id);
  const secundarias = [...palabrasDe(target.organism), ...palabrasDe(familia)];

  let total = 0;
  for (const token of tokens) {
    const mejor = Math.max(
      mejorCoincidencia(nombre, token, 3, 2),
      mejorCoincidencia(id, token, 3, 2),
      mejorCoincidencia(secundarias, token, 1, 1),
    );
    if (mejor === 0) return 0;
    total += mejor;
  }
  return total;
}
