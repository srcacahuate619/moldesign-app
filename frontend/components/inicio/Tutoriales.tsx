"use client";

/* La sección de tutoriales del inicio. Primero aparece el de Preparación; con las flechas se pasa al siguiente
 * tutorial (Molcy). Dentro de cada tutorial, las flechas de su figura recorren sus pasos. */

import { useState } from "react";
import { ArrowLeft, ArrowRight, Clapperboard } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { TutorialMolcy } from "./TutorialMolcy";
import { TutorialPreparacion } from "./TutorialPreparacion";

const TUTORIALES = [TutorialPreparacion, TutorialMolcy] as const;

const BOTON_TUTORIAL = "border border-[var(--border-light)] p-2 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)]";

export function Tutoriales() {
  const { t } = useLanguage();
  const [activo, setActivo] = useState(0);
  const total = TUTORIALES.length;
  const Actual = TUTORIALES[activo];

  return (
    <section aria-labelledby="home-tutoriales-eyebrow" className="border-b border-[var(--border)] py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p id="home-tutoriales-eyebrow" className="flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]">
          <Clapperboard size={16} aria-hidden="true" />{t("ini_tut")}
        </p>
        <nav aria-label={t("ini_tut_navegacion")} className="flex items-center gap-3">
          <button type="button" onClick={() => setActivo(activo - 1)} disabled={activo === 0} aria-label={t("ini_tut_anterior_tutorial")} title={t("ini_tut_anterior_tutorial")} className={BOTON_TUTORIAL}>
            <ArrowLeft size={16} aria-hidden="true" />
          </button>
          <span className="font-mono text-[11px] tracking-[0.12em] text-[var(--text-dim)]">{t("ini_tut_n_de_total", { n: activo + 1, total })}</span>
          <button type="button" onClick={() => setActivo(activo + 1)} disabled={activo === total - 1} aria-label={t("ini_tut_siguiente_tutorial")} title={t("ini_tut_siguiente_tutorial")} className={BOTON_TUTORIAL}>
            <ArrowRight size={16} aria-hidden="true" />
          </button>
        </nav>
      </div>
      <div className="mt-7">
        <Actual />
      </div>
    </section>
  );
}
