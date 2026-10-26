"use client";

/* Del caso al vídeo: seis capturas reales de la aplicación con el control de cada paso señalado.
 * Las capturas y la caja de cada control las genera `scripts/capturas-tutorial-molcy.mjs` contra la aplicación de
 * verdad, en los dos idiomas: si la interfaz cambia, se vuelven a generar en vez de retocarlas a mano. La flecha y
 * el recuadro van encima de la imagen, no pintados en ella. */

import { useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Clapperboard } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import marcas from "@/lib/tutorial/molcy-marcas.json";

export const PASOS_DEL_TUTORIAL = ["caso", "receptor", "evaluar", "guardar", "corrida", "molcy"] as const;
export type PasoDelTutorial = (typeof PASOS_DEL_TUTORIAL)[number];
type Marca = { ancho: number; alto: number; caja: [number, number, number, number] };

const CLAVES: Record<PasoDelTutorial, { titulo: string; texto: string; alt: string }> = {
  caso: { titulo: "ini_tut_caso_titulo", texto: "ini_tut_caso_texto", alt: "ini_tut_caso_alt" },
  receptor: { titulo: "ini_tut_receptor_titulo", texto: "ini_tut_receptor_texto", alt: "ini_tut_receptor_alt" },
  evaluar: { titulo: "ini_tut_evaluar_titulo", texto: "ini_tut_evaluar_texto", alt: "ini_tut_evaluar_alt" },
  guardar: { titulo: "ini_tut_guardar_titulo", texto: "ini_tut_guardar_texto", alt: "ini_tut_guardar_alt" },
  corrida: { titulo: "ini_tut_corrida_titulo", texto: "ini_tut_corrida_texto", alt: "ini_tut_corrida_alt" },
  molcy: { titulo: "ini_tut_molcy_titulo", texto: "ini_tut_molcy_texto", alt: "ini_tut_molcy_alt" },
};

// JSON no tipa tuplas: que cada paso tenga su caja de cuatro números lo comprueba la prueba del componente.
const MARCAS = marcas as unknown as Record<"es" | "en", Record<PasoDelTutorial, Marca>>;

/** La imagen y la caja del botón de un paso, en el idioma de la interfaz (inglés o castellano). */
export function capturaDelPaso(paso: PasoDelTutorial, locale: string): { src: string; marca: Marca } {
  const idioma = locale === "en" ? "en" : "es";
  return { src: `/tutorial/molcy/${idioma}/${paso}.webp`, marca: MARCAS[idioma][paso] };
}

function porcentaje(valor: number, total: number) {
  return `${((valor / total) * 100).toFixed(2)}%`;
}

export function TutorialMolcy() {
  const { t, locale } = useLanguage();
  const [activo, setActivo] = useState(0);
  const paso = PASOS_DEL_TUTORIAL[activo];
  const { src, marca } = capturaDelPaso(paso, locale);
  const [x, y, w, h] = marca.caja;
  // La flecha apunta al botón desde arriba; si el botón está pegado al borde superior, desde abajo.
  const desdeAbajo = y / marca.alto < 0.14;
  const Flecha = desdeAbajo ? ArrowUp : ArrowDown;
  const total = PASOS_DEL_TUTORIAL.length;

  return (
    <section data-testid="tutorial-molcy" aria-labelledby="home-molcy-title" className="grid gap-7 border-b border-[var(--border)] py-10 lg:grid-cols-[minmax(200px,0.55fr)_minmax(0,1.45fr)]">
      <div className="min-w-0">
        <p className="flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]"><Clapperboard size={16} aria-hidden="true" />{t("ini_tut")}</p>
        <h2 id="home-molcy-title" className="mt-5 font-display text-2xl font-bold tracking-tight [overflow-wrap:anywhere] sm:text-3xl">{t("ini_tut_titulo")}</h2>
        <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">{t("ini_tut_intro")}</p>
        <ol className="mt-6 divide-y divide-[var(--border-light)] border-y border-[var(--border-light)]">
          {PASOS_DEL_TUTORIAL.map((id, index) => {
            const claves = CLAVES[id];
            const actual = index === activo;
            return (
              <li key={id}>
                <button type="button" onClick={() => setActivo(index)} aria-current={actual ? "step" : undefined}
                  className={`flex w-full gap-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] ${actual ? "" : "opacity-70 hover:opacity-100"}`}>
                  <span className={`shrink-0 font-mono text-[11px] ${actual ? "font-bold text-[var(--accent-strong)]" : "text-[var(--text-dim)]"}`}>{String(index + 1).padStart(2, "0")}</span>
                  <span className="min-w-0">
                    <span className={`block text-sm ${actual ? "font-bold text-[var(--text)]" : "text-[var(--text-secondary)]"}`}>{t(claves.titulo)}</span>
                    {actual && <span className="mt-1 block text-sm leading-6 text-[var(--text-secondary)]">{t(claves.texto)}</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>

      <figure className="min-w-0">
        <div className="relative overflow-hidden border border-[var(--border)] bg-[var(--bg-secondary)]">
          {/* eslint-disable-next-line @next/next/no-img-element -- export estático: Next Image no optimiza sin servidor */}
          <img src={src} alt={t(CLAVES[paso].alt)} width={marca.ancho} height={marca.alto} className="block h-auto w-full" />
          <span data-testid="tutorial-recuadro" aria-hidden="true"
            className="pointer-events-none absolute rounded-md border-[3px] border-[var(--accent-strong)] shadow-[0_0_0_4px_rgba(0,0,0,0.35)]"
            style={{ left: porcentaje(x - 4, marca.ancho), top: porcentaje(y - 4, marca.alto),
              width: porcentaje(w + 8, marca.ancho), height: porcentaje(h + 8, marca.alto) }} />
          {/* Rebota cuatro veces al llegar a cada paso (la `key` reinicia la animación) y se queda quieta. */}
          <span key={paso} data-testid="tutorial-flecha" aria-hidden="true"
            className={`pointer-events-none absolute -translate-x-1/2 text-[var(--accent-strong)] drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)] motion-safe:animate-senala ${desdeAbajo ? "" : "-translate-y-full"}`}
            style={{ left: porcentaje(x + w / 2, marca.ancho), top: porcentaje(desdeAbajo ? y + h + 10 : y - 10, marca.alto) }}>
            <Flecha size={40} strokeWidth={3} />
          </span>
        </div>
        <figcaption className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <span className="font-mono text-[11px] tracking-[0.12em] text-[var(--text-dim)]">{t("ini_tut_paso", { n: activo + 1, total })}</span>
          <span className="flex gap-2">
            <button type="button" onClick={() => setActivo(activo - 1)} disabled={activo === 0} aria-label={t("ini_tut_anterior")} title={t("ini_tut_anterior")}
              className="border border-[var(--border-light)] p-2 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]"><ArrowLeft size={16} aria-hidden="true" /></button>
            <button type="button" onClick={() => setActivo(activo + 1)} disabled={activo === total - 1} aria-label={t("ini_tut_siguiente")} title={t("ini_tut_siguiente")}
              className="border border-[var(--border-light)] p-2 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]"><ArrowRight size={16} aria-hidden="true" /></button>
          </span>
        </figcaption>
      </figure>
    </section>
  );
}
