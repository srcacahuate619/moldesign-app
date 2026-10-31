"use client";

/* Cómo preparar una evaluación para compartirla: seis capturas reales de la pestaña Preparación con el control de cada
 * paso señalado. Las capturas y la caja de cada control las genera `scripts/capturas-tutorial-preparacion.mjs` contra la
 * aplicación de verdad, en los dos idiomas: si la interfaz cambia, se vuelven a generar en vez de retocarlas a mano. */

import marcas from "@/lib/tutorial/preparacion-marcas.json";
import { type DefinicionDeTutorial, TutorialPasos, capturaDelPaso as capturaDe } from "./TutorialPasos";

const PASOS = [
  { id: "pestana", titulo: "ini_prep_p1_titulo", texto: "ini_prep_p1_texto", alt: "ini_prep_p1_alt" },
  { id: "caso", titulo: "ini_prep_p2_titulo", texto: "ini_prep_p2_texto", alt: "ini_prep_p2_alt" },
  { id: "auditoria", titulo: "ini_prep_p3_titulo", texto: "ini_prep_p3_texto", alt: "ini_prep_p3_alt" },
  { id: "decision", titulo: "ini_prep_p4_titulo", texto: "ini_prep_p4_texto", alt: "ini_prep_p4_alt" },
  { id: "paquete", titulo: "ini_prep_p5_titulo", texto: "ini_prep_p5_texto", alt: "ini_prep_p5_alt" },
  { id: "aviso", titulo: "ini_prep_p6_titulo", texto: "ini_prep_p6_texto", alt: "ini_prep_p6_alt" },
] as const;

export const PASOS_DEL_TUTORIAL_PREPARACION = PASOS.map((p) => p.id);

export const DEFINICION_PREPARACION: DefinicionDeTutorial = {
  id: "preparacion",
  carpeta: "/tutorial/preparacion",
  titulo: "ini_prep_tut_titulo",
  intro: "ini_prep_tut_intro",
  pasos: PASOS,
  // JSON no tipa el mapa por idioma: que cada paso tenga su caja lo comprueba la prueba del componente.
  marcas: marcas as unknown as DefinicionDeTutorial["marcas"],
};

/** La imagen y la caja del control de un paso de Preparación, en el idioma de la interfaz. */
export function capturaDelPasoPreparacion(paso: string, locale: string) {
  return capturaDe(DEFINICION_PREPARACION, paso, locale);
}

export function TutorialPreparacion() {
  return <TutorialPasos tutorial={DEFINICION_PREPARACION} />;
}
