"use client";

/* Hallmark · pre-emit critique: P5 H4 E4 S5 R5 V5
 * Inicio editorial: novedades públicas; ningún atajo al espacio de trabajo. */

import { useEffect, useState } from "react";
import { ArrowUpRight, BookOpenText, FlaskConical, Megaphone, Radio, Sparkles } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { cargarIndice, type IndiceRegistro } from "@/lib/registro";
import { PRODUCT } from "@/lib/softwareCatalog";

const SITE = "https://moldesign.amezcua-dev.com";

const copy = {
  es: {
    eyebrow: "MOLDESIGN / ACTUALIDAD",
    intro: "Notas de versión, registro científico y noticias de la comunidad. Este espacio informa; las herramientas de trabajo están en la barra superior.",
    issue: "EDICIÓN DE ESCRITORIO", lead: "NOTAS DEL PARCHE", leadStatus: "En preparación · aún no publicado",
    leadTitle: "Lo que viene en la versión 1.0.2",
    leadIntro: "La siguiente versión concentra correcciones de evidencia y procedencia. Estas mejoras están documentadas en desarrollo; todavía no forman parte de la versión instalada.",
    patch: ["El ranking principal vuelve a depender del score observado de Vina.", "La evaluación declara cuándo la tautomería del ligando sigue sin resolverse.", "Las dianas con un sitio que no puede prepararse se identifican como no disponibles."],
    science: "CIENCIA ABIERTA", scienceTitle: "El registro de lo que resistió y lo que cambió.",
    scienceIntro: "Experimentos, mediciones, refutaciones y correcciones con sus condiciones a la vista.",
    artifacts: "artefactos en el registro local", unavailable: "Registro no disponible", more: "¿Quieres saber más?",
    community: "COMUNIDAD", soon: "Próximamente", communityTitle: "Un lugar para compartir el trabajo.",
    communityIntro: "La comunidad tendrá su espacio en la web de MolDesign. Aquí mostraremos un resumen cuando esté publicada.",
    news: "EN DESARROLLO", newsTitle: "Nuevas formas de leer la evidencia.",
    newsIntro: "Molcy explora la comunicación visual de cada corrida y Preparación estructural organiza las decisiones previas a cálculos posteriores. Ambas interfaces se están diseñando; no ejecutan nuevos análisis todavía.",
    current: "Versión instalada", offline: "Contenido incluido con la aplicación · conexión opcional para abrir la web", web: "Sitio de MolDesign",
  },
  en: {
    eyebrow: "MOLDESIGN / UPDATES",
    intro: "Release notes, the scientific register and community news. This space informs; work tools remain in the top bar.",
    issue: "DESKTOP EDITION", lead: "PATCH NOTES", leadStatus: "In progress · not released",
    leadTitle: "Coming in version 1.0.2",
    leadIntro: "The next release focuses on evidence and provenance corrections. These changes are documented in development and are not part of the installed version yet.",
    patch: ["Primary ranking returns to Vina's observed score.", "Evaluations declare when ligand tautomerism remains unresolved.", "Targets whose binding site cannot be prepared are marked unavailable."],
    science: "OPEN SCIENCE", scienceTitle: "The record of what held up and what changed.",
    scienceIntro: "Experiments, measurements, refutations and corrections with their conditions in view.",
    artifacts: "artifacts in the local register", unavailable: "Register unavailable", more: "Want to know more?",
    community: "COMMUNITY", soon: "Coming soon", communityTitle: "A place to share the work.",
    communityIntro: "The community will have its space on the MolDesign website. A summary will appear here when it is published.",
    news: "IN DEVELOPMENT", newsTitle: "New ways to read the evidence.",
    newsIntro: "Molcy explores visual communication for each run, while Structural Preparation organizes decisions before later calculations. Both interfaces are being designed; they do not run new analyses yet.",
    current: "Installed version", offline: "Content bundled with the app · connection optional to open the website", web: "MolDesign website",
  },
};

function MoreLink({ href, text }: { href: string; text: string }) {
  return <ExternalLink href={href} className="group inline-flex items-center gap-2 self-start border-b border-[var(--accent)] pb-1 text-xs font-bold text-[var(--text)] transition-colors hover:text-[var(--accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent-strong)]">{text}<ArrowUpRight size={15} className="transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" aria-hidden="true" /></ExternalLink>;
}

export default function HomePage() {
  const { t, locale } = useLanguage();
  const c = copy[locale];
  const [register, setRegister] = useState<IndiceRegistro | null>(null);
  useEffect(() => { cargarIndice().then(setRegister).catch(() => setRegister(null)); }, []);

  return (
    <div className="min-h-[calc(100dvh-56px)] bg-[var(--bg)] text-[var(--text)]">
      <main className="mx-auto max-w-[1500px] px-4 pb-16 pt-8 sm:px-7 lg:px-10">
        <header className="flex flex-wrap items-end justify-between gap-5 border-b border-[var(--border)] pb-7">
          <div className="max-w-3xl min-w-0"><p className="mb-3 font-mono text-[11px] font-bold tracking-[0.22em] text-[var(--accent-strong)]">{c.eyebrow}</p><h1 className="font-display text-4xl font-bold leading-none tracking-tight [overflow-wrap:anywhere] sm:text-5xl lg:text-6xl">{t("pg_inicio_titulo")}</h1><p className="mt-5 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">{c.intro}</p></div>
          <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-[var(--text-dim)]">{c.issue} · v{PRODUCT.version}</span>
        </header>

        <div className="grid lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
          <article className="relative flex min-h-[520px] flex-col justify-between overflow-hidden border-b border-[var(--border)] bg-[var(--bg-secondary)] p-6 sm:p-9 lg:border-r">
            <div className="pointer-events-none absolute -right-16 -top-20 size-72 rounded-full border border-[var(--border-light)] opacity-60 sm:size-96" aria-hidden="true" />
            <div className="pointer-events-none absolute -right-2 -top-2 size-56 rounded-full border border-dashed border-[var(--border-light)] opacity-50 sm:size-72" aria-hidden="true" />
            <div className="relative z-10"><div className="flex flex-wrap items-center gap-3"><span className="inline-flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]"><Megaphone size={15} />{c.lead}</span><span className="border border-[var(--border-light)] px-2 py-1 font-mono text-[10px] text-[var(--text-dim)]">{c.leadStatus}</span></div><h2 className="mt-8 max-w-[640px] font-display text-3xl font-bold leading-[1.08] tracking-tight [overflow-wrap:anywhere] sm:text-4xl lg:text-5xl">{c.leadTitle}</h2><p className="mt-5 max-w-xl text-sm leading-7 text-[var(--text-secondary)]">{c.leadIntro}</p></div>
            <div className="relative z-10 mt-11"><ul className="max-w-[670px] divide-y divide-[var(--border-light)] border-y border-[var(--border-light)]">{c.patch.map((item, index) => <li key={item} className="flex gap-5 py-3 text-xs leading-6 sm:text-sm"><span className="shrink-0 font-mono text-[11px] text-[var(--accent-strong)]">0{index + 1}</span><span>{item}</span></li>)}</ul><div className="mt-7"><MoreLink href={`${SITE}/novedades`} text={c.more} /></div></div>
          </article>

          <div className="grid min-w-0">
            <article className="flex min-h-[260px] flex-col justify-between border-b border-[var(--border)] p-6 sm:p-8">
              <div><p className="flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]"><FlaskConical size={15} />{c.science}</p><h2 className="mt-5 max-w-md font-display text-2xl font-bold leading-tight [overflow-wrap:anywhere] sm:text-3xl">{c.scienceTitle}</h2><p className="mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">{c.scienceIntro}</p></div>
              <div className="mt-7 flex flex-wrap items-end justify-between gap-4"><div><span className="block font-mono text-3xl font-bold">{register?.total ?? "—"}</span><span className="text-xs text-[var(--text-dim)]">{register ? c.artifacts : c.unavailable}</span></div><MoreLink href={`${SITE}/ciencia`} text={c.more} /></div>
            </article>
            <article className="flex min-h-[260px] flex-col justify-between border-b border-[var(--border)] bg-[var(--bg-card)] p-6 sm:p-8">
              <div><div className="flex flex-wrap items-center gap-3"><p className="flex items-center gap-2 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]"><Radio size={15} />{c.community}</p><span className="border border-[var(--border-light)] px-2 py-1 font-mono text-[10px] uppercase tracking-[0.09em] text-[var(--text-dim)]">{c.soon}</span></div><h2 className="mt-5 max-w-md font-display text-2xl font-bold leading-tight [overflow-wrap:anywhere] sm:text-3xl">{c.communityTitle}</h2><p className="mt-3 max-w-md text-sm leading-6 text-[var(--text-secondary)]">{c.communityIntro}</p></div>
              <p className="mt-7 border-t border-[var(--border)] pt-4 font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-dim)]">{c.soon}</p>
            </article>
          </div>
        </div>
        <section aria-labelledby="home-news-title" className="grid gap-7 border-b border-[var(--border)] py-10 lg:grid-cols-[minmax(200px,0.55fr)_minmax(0,1.45fr)]"><div className="flex items-start gap-3 font-mono text-[11px] font-bold tracking-[0.18em] text-[var(--accent-strong)]"><Sparkles size={16} />{c.news}</div><div><h2 id="home-news-title" className="font-display text-2xl font-bold tracking-tight [overflow-wrap:anywhere] sm:text-3xl">{c.newsTitle}</h2><p className="mt-3 max-w-3xl text-sm leading-7 text-[var(--text-secondary)]">{c.newsIntro}</p></div></section>
      </main>
      <footer className="border-t border-[var(--border)] px-4 py-6 sm:px-7 lg:px-10"><div className="mx-auto flex max-w-[1500px] flex-wrap items-center justify-between gap-4 text-xs text-[var(--text-dim)]"><span className="flex items-center gap-2"><BookOpenText size={14} />{c.current}: v{PRODUCT.version}</span><span>{c.offline}</span><ExternalLink href={SITE} className="inline-flex items-center gap-1 font-semibold text-[var(--text)] underline decoration-[var(--accent)] underline-offset-4 hover:text-[var(--accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-[var(--accent-strong)]">{c.web}<ArrowUpRight size={14} /></ExternalLink></div></footer>
    </div>
  );
}
