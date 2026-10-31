"use client";

/* Un tutorial de pasos: una captura real de la aplicación por paso, con el control de ese paso señalado.
 * Las capturas y la caja de cada control las generan los scripts de `frontend/scripts/` contra la aplicación de
 * verdad, en los dos idiomas: si la interfaz cambia, se vuelven a generar en vez de retocarlas a mano. La flecha y
 * el recuadro van encima de la imagen, no pintados en ella. */

import { useState } from "react";
import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";

export type Marca = { ancho: number; alto: number; caja: [number, number, number, number] };

export type PasoDeTutorial = {
  /** Nombre de la captura (`<id>.webp`) y clave de su marca. */
  id: string;
  /** Claves de traducción del título del paso, de su texto y del texto alternativo de la captura. */
  titulo: string;
  texto: string;
  alt: string;
};

export type DefinicionDeTutorial = {
  id: string;
  /** Carpeta pública de las capturas: `<carpeta>/<idioma>/<paso>.webp`. */
  carpeta: string;
  /** Claves de traducción del título y de la introducción del tutorial. */
  titulo: string;
  intro: string;
  pasos: readonly PasoDeTutorial[];
  marcas: Record<"es" | "en", Record<string, Marca>>;
};

/** La imagen y la caja del control de un paso, en el idioma de la interfaz (inglés o castellano). */
export function capturaDelPaso(tutorial: DefinicionDeTutorial, paso: string, locale: string): { src: string; marca: Marca } {
  const idioma = locale === "en" ? "en" : "es";
  return { src: `${tutorial.carpeta}/${idioma}/${paso}.webp`, marca: tutorial.marcas[idioma][paso] };
}

function porcentaje(valor: number, total: number) {
  return `${((valor / total) * 100).toFixed(2)}%`;
}

const BOTON_PASO = "border border-[var(--border-light)] p-2 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]";

export function TutorialPasos({ tutorial }: { tutorial: DefinicionDeTutorial }) {
  const { t, locale } = useLanguage();
  const [activo, setActivo] = useState(0);
  const total = tutorial.pasos.length;
  const paso = tutorial.pasos[activo];
  const { src, marca } = capturaDelPaso(tutorial, paso.id, locale);
  const [x, y, w, h] = marca.caja;
  // La flecha apunta al botón desde arriba; si el botón está pegado al borde superior, desde abajo.
  const desdeAbajo = y / marca.alto < 0.14;
  const Flecha = desdeAbajo ? ArrowUp : ArrowDown;

  return (
    <div data-testid={`tutorial-${tutorial.id}`} className="grid gap-7 lg:grid-cols-[minmax(200px,0.55fr)_minmax(0,1.45fr)]">
      <div className="min-w-0">
        <h2 className="font-display text-2xl font-bold tracking-tight [overflow-wrap:anywhere] sm:text-3xl">{t(tutorial.titulo)}</h2>
        <p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">{t(tutorial.intro)}</p>
        <ol className="mt-6 divide-y divide-[var(--border-light)] border-y border-[var(--border-light)]">
          {tutorial.pasos.map((p, index) => {
            const actual = index === activo;
            return (
              <li key={p.id}>
                <button type="button" onClick={() => setActivo(index)} aria-current={actual ? "step" : undefined}
                  className={`flex w-full gap-4 py-3 text-left focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] ${actual ? "" : "opacity-70 hover:opacity-100"}`}>
                  <span className={`shrink-0 font-mono text-[11px] ${actual ? "font-bold text-[var(--accent-strong)]" : "text-[var(--text-dim)]"}`}>{String(index + 1).padStart(2, "0")}</span>
                  <span className="min-w-0">
                    <span className={`block text-sm ${actual ? "font-bold text-[var(--text)]" : "text-[var(--text-secondary)]"}`}>{t(p.titulo)}</span>
                    {actual && <span className="mt-1 block text-sm leading-6 text-[var(--text-secondary)]">{t(p.texto)}</span>}
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
          <img src={src} alt={t(paso.alt)} width={marca.ancho} height={marca.alto} className="block h-auto w-full" />
          <span data-testid="tutorial-recuadro" aria-hidden="true"
            className="pointer-events-none absolute rounded-md border-[3px] border-[var(--accent-strong)] shadow-[0_0_0_4px_rgba(0,0,0,0.35)]"
            style={{ left: porcentaje(x - 4, marca.ancho), top: porcentaje(y - 4, marca.alto),
              width: porcentaje(w + 8, marca.ancho), height: porcentaje(h + 8, marca.alto) }} />
          {/* Rebota cuatro veces al llegar a cada paso (la `key` reinicia la animación) y se queda quieta. */}
          <span key={paso.id} data-testid="tutorial-flecha" aria-hidden="true"
            className={`pointer-events-none absolute -translate-x-1/2 text-[var(--accent-strong)] drop-shadow-[0_1px_2px_rgba(0,0,0,0.6)] motion-safe:animate-senala ${desdeAbajo ? "" : "-translate-y-full"}`}
            style={{ left: porcentaje(x + w / 2, marca.ancho), top: porcentaje(desdeAbajo ? y + h + 10 : y - 10, marca.alto) }}>
            <Flecha size={40} strokeWidth={3} />
          </span>
        </div>
        <figcaption className="mt-4 flex flex-wrap items-center justify-between gap-4">
          <span className="font-mono text-[11px] tracking-[0.12em] text-[var(--text-dim)]">{t("ini_tut_paso", { n: activo + 1, total })}</span>
          <span className="flex gap-2">
            <button type="button" onClick={() => setActivo(activo - 1)} disabled={activo === 0} aria-label={t("ini_tut_anterior")} title={t("ini_tut_anterior")} className={BOTON_PASO}><ArrowLeft size={16} aria-hidden="true" /></button>
            <button type="button" onClick={() => setActivo(activo + 1)} disabled={activo === total - 1} aria-label={t("ini_tut_siguiente")} title={t("ini_tut_siguiente")} className={BOTON_PASO}><ArrowRight size={16} aria-hidden="true" /></button>
          </span>
        </figcaption>
      </figure>
    </div>
  );
}
