"use client";

/* Hallmark · pre-emit critique: P5 H4 E4 S5 R5 V5
 * Inicio editorial: explica la app, trae las notas de la versión y lleva a la web.
 * Ningún atajo al espacio de trabajo: las herramientas están en la barra superior. */

import { useEffect, useState } from "react";
import { ArrowUpRight, BookOpenText, FlaskConical, Megaphone, Radio, ShieldCheck, Sparkles } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { Tutoriales } from "@/components/inicio/Tutoriales";
import { cargarIndice, type IndiceRegistro } from "@/lib/registro";
import { PRODUCT } from "@/lib/softwareCatalog";
import { SITE, VERSION_DE_LAS_NOTAS, versionAlcanza } from "@/lib/inicio";

const CLAVES_DE_LAS_NOTAS = [
  "ini_nota_1", "ini_nota_2", "ini_nota_3", "ini_nota_4", "ini_nota_5", "ini_nota_6", "ini_nota_7", "ini_nota_8", "ini_nota_9",
] as const;

const CLAVES_DE_LO_QUE_ES = ["ini_es_1", "ini_es_2", "ini_es_3"] as const;
const CLAVES_DE_LO_QUE_NO_ES = ["ini_no_es_1", "ini_no_es_2", "ini_no_es_3"] as const;

/** Las seis herramientas, en el orden de la barra superior. */
const HERRAMIENTAS = [
  { nombre: "ini_herr_evaluacion", texto: "ini_herr_evaluacion_texto" },
  { nombre: "ini_herr_batch", texto: "ini_herr_batch_texto" },
  { nombre: "ini_herr_preparacion", texto: "ini_herr_preparacion_texto" },
  { nombre: "ini_herr_moldex", texto: "ini_herr_moldex_texto" },
  { nombre: "ini_herr_historial", texto: "ini_herr_historial_texto" },
  { nombre: "ini_herr_molcy", texto: "ini_herr_molcy_texto" },
] as const;

const ENLACE_CLASE =
  "group inline-flex items-center gap-2 self-start border-b border-[var(--accent)] pb-1 text-xs font-bold text-[var(--text)] transition-colors hover:text-[var(--accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent-strong)]";

function MoreLink({ href, text }: { href: string; text: string }) {
  return <ExternalLink href={href} className={ENLACE_CLASE}>{text}<ArrowUpRight size={15} className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden="true" /></ExternalLink>;
}

export default function HomePage() {
  const { t } = useLanguage();
  const [register, setRegister] = useState<IndiceRegistro | null>(null);
  useEffect(() => { cargarIndice().then(setRegister).catch(() => setRegister(null)); }, []);

  // Las notas describen una versión concreta; su estado sale de comparar con la instalada, no de un texto que alguien
  // tenga que acordarse de cambiar el día de la publicación.
  const publicada = versionAlcanza(PRODUCT.version, VERSION_DE_LAS_NOTAS);

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-[var(--bg)] text-[var(--text)]">
      <main className="mx-auto max-w-[1500px] px-4 pb-16 pt-8 sm:px-7 lg:px-10">
        <header className="flex flex-wrap items-end justify-between gap-5 border-b border-[var(--border)] pb-7">
          <div className="max-w-3xl min-w-0"><p className="mb-3 font-mono text-[11px] font-bold tracking-[0.22em] text-[var(--accent-strong)]">{t("ini_eyebrow")}</p><h1 className="font-display text-4xl font-bold leading-none tracking-tight [overflow-wrap:anywhere] sm:text-5xl lg:text-6xl">{t("pg_inicio_titulo")}</h1><p data-testid="que-es-la-app" className="mt-5 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">{t("ini_intro")}</p></div>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--text-dim)]">{t("ini_edicion")} · v{PRODUCT.version}</span>
        </header>

        <div className="grid lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
          <article data-testid="notas-de-la-version" className="relative flex min-h-[520px] flex-col justify-between overflow-hidden border-b border-[var(--border)] bg-[var(--bg-secondary)] p-6 sm:p-9 lg:border-r">
            <div className="pointer-events-none absolute -right-16 -top-20 size-72 rounded-full border border-[var(--border-light)] opacity-60 sm:size-96" aria-hidden="true" />
            <div className="pointer-events-none absolute -right-2 -top-2 size-56 rounded-full border border-dashed border-[var(--border-light)] opacity-50 sm:size-72" aria-hidden="true" />
            <div className="relative z-10"><div className="flex flex-wrap items-center gap-3"><span className="inline-flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]"><Megaphone size={15} />{t("ini_notas")}</span><span data-testid="estado-de-las-notas" className="border border-[var(--border-light)] px-2 py-1 font-mono text-[10px] text-[var(--text-dim)]">{publicada ? t("ini_estado_publicada") : t("ini_estado_pendiente")}</span></div><h2 className="mt-8 max-w-[640px] font-display text-3xl font-bold leading-[1.08] tracking-tight [overflow-wrap:anywhere] sm:text-4xl lg:text-5xl">{publicada ? t("ini_titulo_publicada") : t("ini_titulo_pendiente")}</h2><p className="mt-5 max-w-xl text-sm leading-7 text-[var(--text-secondary)]">{publicada ? t("ini_intro_publicada") : t("ini_intro_pendiente")}</p></div>
            <div className="relative z-10 mt-11"><ul className="max-w-[670px] divide-y divide-[var(--border-light)] border-y border-[var(--border-light)]">{CLAVES_DE_LAS_NOTAS.map((clave, index) => <li key={clave} className="flex gap-5 py-3 text-xs leading-6 sm:text-sm"><span className="shrink-0 font-mono text-[11px] text-[var(--accent-strong)]">{String(index + 1).padStart(2, "0")}</span><span>{t(clave)}</span></li>)}</ul><div className="mt-7"><MoreLink href={SITE} text={t("ini_cta_boton")} /></div></div>
          </article>

          <div className="grid min-w-0">
            <article data-testid="que-es-y-que-no-es" className="flex flex-col gap-6 border-b border-[var(--border)] p-6 sm:p-8">
              <div><p className="flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]"><ShieldCheck size={15} />{t("ini_que_es")}</p><ul className="mt-3 space-y-2">{CLAVES_DE_LO_QUE_ES.map((clave) => <li key={clave} className="text-sm leading-6 text-[var(--text-secondary)]">{t(clave)}</li>)}</ul></div>
              <div><p className="font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--text-dim)]">{t("ini_que_no_es")}</p><ul className="mt-3 space-y-2">{CLAVES_DE_LO_QUE_NO_ES.map((clave) => <li key={clave} className="text-sm leading-6 text-[var(--text-secondary)]">{t(clave)}</li>)}</ul></div>
            </article>
            <article className="flex min-h-[220px] flex-col justify-between border-b border-[var(--border)] p-6 sm:p-8">
              <div><p className="flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]"><FlaskConical size={15} />{t("ini_ciencia")}</p><h2 className="mt-5 max-w-md font-display text-2xl font-bold leading-tight [overflow-wrap:anywhere] sm:text-3xl">{t("ini_ciencia_titulo")}</h2><p className="mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">{t("ini_ciencia_intro")}</p></div>
              <div className="mt-7"><span className="block font-mono text-3xl font-bold">{register?.total ?? "—"}</span><span className="text-xs text-[var(--text-dim)]">{register ? t("ini_artefactos") : t("ini_registro_no_disponible")}</span></div>
            </article>
            <article className="flex min-h-[220px] flex-col justify-between border-b border-[var(--border)] bg-[var(--bg-card)] p-6 sm:p-8">
              <div><div className="flex flex-wrap items-center gap-3"><p className="flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]"><Radio size={15} />{t("ini_comunidad")}</p><span className="border border-[var(--border-light)] px-2 py-1 font-mono text-[10px] uppercase tracking-[0.09em] text-[var(--text-dim)]">{t("ini_proximamente")}</span></div><h2 className="mt-5 max-w-md font-display text-2xl font-bold leading-tight [overflow-wrap:anywhere] sm:text-3xl">{t("ini_comunidad_titulo")}</h2><p className="mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">{t("ini_comunidad_intro")}</p></div>
              <p className="mt-7 border-t border-[var(--border)] pt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-dim)]">{t("ini_proximamente")}</p>
            </article>
          </div>
        </div>

        <section data-testid="que-incluye" aria-labelledby="home-includes-title" className="grid gap-7 border-b border-[var(--border)] py-10 lg:grid-cols-[minmax(200px,0.55fr)_minmax(0,1.45fr)]">
          <div className="flex items-start gap-3 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]"><Sparkles size={16} />{t("ini_incluye")}</div>
          <div>
            <h2 id="home-includes-title" className="font-display text-2xl font-bold tracking-tight [overflow-wrap:anywhere] sm:text-3xl">{t("ini_incluye_titulo")}</h2>
            <ul className="mt-6 grid gap-x-8 gap-y-5 sm:grid-cols-2 xl:grid-cols-3">{HERRAMIENTAS.map((herramienta) => <li key={herramienta.nombre}><p className="font-mono text-xs font-bold uppercase tracking-[0.12em] text-[var(--text)]">{t(herramienta.nombre)}</p><p className="mt-1.5 text-sm leading-6 text-[var(--text-secondary)]">{t(herramienta.texto)}</p></li>)}</ul>
          </div>
        </section>

        <Tutoriales />

        <section data-testid="llamada-a-la-accion" aria-labelledby="home-cta-title" className="flex flex-wrap items-center justify-between gap-6 py-10">
          <div className="max-w-2xl"><h2 id="home-cta-title" className="font-display text-2xl font-bold tracking-tight [overflow-wrap:anywhere] sm:text-3xl">{t("ini_cta_titulo")}</h2><p className="mt-3 text-sm leading-7 text-[var(--text-secondary)]">{t("ini_cta_texto")}</p></div>
          <MoreLink href={SITE} text={t("ini_cta_boton")} />
        </section>
      </main>
      <footer className="border-t border-[var(--border)] px-4 py-6 sm:px-7 lg:px-10"><div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-4 text-xs text-[var(--text-dim)]"><span className="flex items-center gap-2"><BookOpenText size={14} />{t("ini_version_instalada")}: v{PRODUCT.version}</span><span>{t("ini_sin_conexion")}</span><ExternalLink href={SITE} className="inline-flex items-center gap-1 font-semibold text-[var(--text)] underline decoration-[var(--accent)] underline-offset-4 hover:text-[var(--accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent-strong)]">{t("ini_sitio")}<ArrowUpRight size={14} /></ExternalLink></div></footer>
    </div>
  );
}
