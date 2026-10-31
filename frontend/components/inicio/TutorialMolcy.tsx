"use client";

/* Del caso al vídeo: seis capturas reales de la aplicación con el control de cada paso señalado.
 * Las capturas y la caja de cada control las genera `scripts/capturas-tutorial-molcy.mjs` contra la aplicación de
 * verdad, en los dos idiomas: si la interfaz cambia, se vuelven a generar en vez de retocarlas a mano. */

import marcas from "@/lib/tutorial/molcy-marcas.json";
import { type DefinicionDeTutorial, TutorialPasos, capturaDelPaso as capturaDe } from "./TutorialPasos";

const PASOS = [
  { id: "caso", titulo: "ini_tut_caso_titulo", texto: "ini_tut_caso_texto", alt: "ini_tut_caso_alt" },
  { id: "receptor", titulo: "ini_tut_receptor_titulo", texto: "ini_tut_receptor_texto", alt: "ini_tut_receptor_alt" },
  { id: "evaluar", titulo: "ini_tut_evaluar_titulo", texto: "ini_tut_evaluar_texto", alt: "ini_tut_evaluar_alt" },
  { id: "guardar", titulo: "ini_tut_guardar_titulo", texto: "ini_tut_guardar_texto", alt: "ini_tut_guardar_alt" },
  { id: "corrida", titulo: "ini_tut_corrida_titulo", texto: "ini_tut_corrida_texto", alt: "ini_tut_corrida_alt" },
  { id: "molcy", titulo: "ini_tut_molcy_titulo", texto: "ini_tut_molcy_texto", alt: "ini_tut_molcy_alt" },
] as const;

export const PASOS_DEL_TUTORIAL = PASOS.map((p) => p.id);

export const DEFINICION_MOLCY: DefinicionDeTutorial = {
  id: "molcy",
  carpeta: "/tutorial/molcy",
  titulo: "ini_tut_titulo",
  intro: "ini_tut_intro",
  pasos: PASOS,
  // JSON no tipa el mapa por idioma: que cada paso tenga su caja lo comprueba la prueba del componente.
  marcas: marcas as unknown as DefinicionDeTutorial["marcas"],
};

/** La imagen y la caja del botón de un paso de Molcy, en el idioma de la interfaz. */
export function capturaDelPaso(paso: string, locale: string) {
  return capturaDe(DEFINICION_MOLCY, paso, locale);
}

export function TutorialMolcy() {
  return <TutorialPasos tutorial={DEFINICION_MOLCY} />;
}
