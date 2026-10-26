"use client";

import React, { useEffect, useId, useRef } from "react";
import { X } from "lucide-react";

import { useLanguage } from "../../../context/LanguageContext";

/**
 * Ayuda de un parámetro: el texto que antes ocupaba sitio permanente en el diálogo de
 * «Parámetros de la evaluación» y que ahora se abre con un «?» (decisión del propietario,
 * 2026-10-07). Lo que cambia es dónde se lee, no lo que dice: los párrafos son las mismas
 * claves de traducción de siempre.
 */
export interface TemaDeAyuda {
  /** Nombre del parámetro: titula el diálogo y nombra el botón para los lectores de pantalla. */
  titulo: string;
  /** Párrafos en orden. Llegan ya traducidos. */
  parrafos: readonly string[];
}

// El signo no se traduce. No se usa `auto_5bab61eb5317`, que vale «?» en español pero en inglés
// quedó con una letra de canción (traducción automática); sólo lo pinta `DockingEnginePanel`,
// que no usa nadie.
const SIGNO_DE_AYUDA = "?";

export function BotonAyuda({
  tema,
  onAbrir,
}: {
  tema: TemaDeAyuda;
  onAbrir: (tema: TemaDeAyuda, origen: HTMLElement) => void;
}) {
  const { t } = useLanguage();
  return (
    <button
      type="button"
      aria-haspopup="dialog"
      aria-label={t("op_ayuda_sobre", { tema: tema.titulo })}
      onClick={(event) => onAbrir(tema, event.currentTarget)}
      className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-zinc-700 bg-zinc-900 font-mono text-xs font-bold text-zinc-400 transition-colors hover:border-purple-500/40 hover:text-white cursor-pointer focus-visible:outline-2 focus-visible:outline-purple-400"
    >
      <span aria-hidden="true">{SIGNO_DE_AYUDA}</span>
    </button>
  );
}

/**
 * Se pinta por encima del diálogo de parámetros (`z-50`). Escape y el fondo lo cierran a
 * ÉL y no al diálogo de debajo; al cerrar, el foco vuelve al «?» que lo abrió.
 */
export function DialogoDeAyuda({
  tema,
  origen,
  onCerrar,
}: {
  tema: TemaDeAyuda;
  origen: HTMLElement | null;
  onCerrar: () => void;
}) {
  const { t } = useLanguage();
  const idTitulo = useId();
  const botonCerrar = useRef<HTMLButtonElement>(null);
  // El efecto depende sólo del origen: con `onCerrar` en las dependencias, un padre que
  // pasa una función nueva en cada render movería el foco en cada pulsación.
  const cerrar = useRef(onCerrar);
  cerrar.current = onCerrar;

  useEffect(() => {
    botonCerrar.current?.focus();
    const alTeclear = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        cerrar.current();
      }
    };
    document.addEventListener("keydown", alTeclear);
    return () => {
      document.removeEventListener("keydown", alTeclear);
      origen?.focus();
    };
  }, [origen]);

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" role="presentation">
      <div className="absolute inset-0 bg-black/70" onClick={onCerrar} />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        className="relative w-full max-w-lg max-h-[80vh] overflow-y-auto rounded-2xl border border-purple-500/30 bg-zinc-950 p-5 shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id={idTitulo} className="text-base font-bold font-mono uppercase tracking-wider text-white">
            {tema.titulo}
          </h2>
          <button
            ref={botonCerrar}
            type="button"
            onClick={onCerrar}
            aria-label={t("op_ayuda_cerrar")}
            className="rounded-lg border border-zinc-800 bg-zinc-900 p-1.5 text-zinc-400 transition-colors hover:border-purple-500/30 hover:text-white cursor-pointer"
          >
            <X size={14} />
          </button>
        </div>
        <div className="mt-3 space-y-3">
          {tema.parrafos.map((parrafo, i) => (
            <p key={i} className="text-sm font-mono leading-relaxed text-zinc-300">
              {parrafo}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}
