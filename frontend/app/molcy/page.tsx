"use client";

/* Hallmark · pre-emit critique: P5 H4 E4 S5 R5 V4
 * Molcy: workspace de edición; la vista esquemática nunca se presenta como evidencia. */

import { useState } from "react";
import { useLanguage } from "@/context/LanguageContext";
import {
  Aperture, ArrowRight, Check, CircleHelp, Layers3, MonitorPlay,
  Monitor, Pause, Play, ScanEye, Smartphone, Sparkles, WandSparkles,
} from "lucide-react";

type SceneId = "resultado" | "busqueda" | "ensamble";
type FormatId = "vertical" | "horizontal";

const scenes = {
  resultado: {
    number: "01",
    icon: ScanEye,
    es: { name: "Resultado", summary: "Sitio activo, pose evaluada e interacciones calculadas.", phase: ["Sitio activo", "Pose evaluada", "Contexto estructural"] },
    en: { name: "Result", summary: "Active site, evaluated pose and computed interactions.", phase: ["Active site", "Evaluated pose", "Structural context"] },
  },
  busqueda: {
    number: "02",
    icon: Sparkles,
    es: { name: "Búsqueda", summary: "Poses y pasos registrados durante la exploración.", phase: ["Sitio activo", "Exploración registrada", "Pose seleccionada"] },
    en: { name: "Search", summary: "Recorded poses and steps from the exploration.", phase: ["Active site", "Recorded search", "Selected pose"] },
  },
  ensamble: {
    number: "03",
    icon: Layers3,
    es: { name: "Ensamble", summary: "Conformeros y controles disponibles de cada pose.", phase: ["Conformeros", "Comparación de poses", "Controles disponibles"] },
    en: { name: "Ensemble", summary: "Conformers and available checks for each pose.", phase: ["Conformers", "Pose comparison", "Available checks"] },
  },
} as const;

const copy = {
  es: {
    eyebrow: "ESTUDIO VISUAL · MOLCY",
    intro: "Compón un video a partir de una corrida concreta. Cada escena mostrará únicamente las estructuras, pasos y controles que esa corrida conserve.",
    draft: "Diseño de interfaz",
    source: "01 / ORIGEN",
    sourceTitle: "Corrida de evaluación",
    sourceMissing: "Ninguna corrida vinculada",
    sourceDetail: "La selección de evaluaciones llegará con la conexión al historial. El video quedará asociado a una ejecución exacta, no al resultado más reciente de una molécula.",
    scenes: "02 / NARRATIVA",
    scenesTitle: "Elige qué contar",
    searchNote: "Búsqueda requiere una traza real; el número de pasos nunca se infiere de las poses finales.",
    ensembleNote: "Ensamble solo enseñará conformeros y controles presentes en la corrida.",
    preview: "VISTA PREVIA",
    previewHint: "Esquema de composición · sin datos moleculares cargados",
    previewEmpty: "Aquí aparecerá el sitio activo de la corrida seleccionada.",
    playback: "Fotograma conceptual",
    storyboard: "GUION VISUAL",
    output: "03 / SALIDA",
    outputTitle: "Formato de entrega",
    vertical: "Vertical",
    horizontal: "Horizontal",
    formatHint: "La composición se adaptará al formato. Las estructuras y cifras seguirán siendo las mismas.",
    evidence: "Regla de evidencia",
    evidenceText: "Si falta la traza, una pose o un control, Molcy lo indicará y no dibujará datos de sustitución.",
    generate: "Generar video",
    disabled: "Disponible cuando se conecte una corrida de evaluación.",
    noBackend: "Interfaz de diseño · generación aún no conectada",
  },
  en: {
    eyebrow: "VISUAL STUDIO · MOLCY",
    intro: "Compose a video from one exact run. Each scene will show only the structures, steps and checks preserved by that run.",
    draft: "Interface design",
    source: "01 / SOURCE",
    sourceTitle: "Evaluation run",
    sourceMissing: "No run linked",
    sourceDetail: "Run selection will arrive with history integration. The video will be linked to an exact run, not a molecule’s latest result.",
    scenes: "02 / NARRATIVE",
    scenesTitle: "Choose what to show",
    searchNote: "Search requires a real trace; the number of steps is never inferred from final poses.",
    ensembleNote: "Ensemble will only show conformers and checks present in the run.",
    preview: "PREVIEW",
    previewHint: "Composition sketch · no molecular data loaded",
    previewEmpty: "The selected run’s active site will appear here.",
    playback: "Concept frame",
    storyboard: "VISUAL STORYBOARD",
    output: "03 / OUTPUT",
    outputTitle: "Delivery format",
    vertical: "Vertical",
    horizontal: "Horizontal",
    formatHint: "The composition will adapt to the format. Structures and figures will remain the same.",
    evidence: "Evidence rule",
    evidenceText: "If a trace, pose or check is missing, Molcy will say so and will not draw substitute data.",
    generate: "Generate video",
    disabled: "Available when an evaluation run is connected.",
    noBackend: "Interface design · rendering is not connected yet",
  },
};

export default function MolcyPage() {
  const { t, locale } = useLanguage();
  const c = copy[locale];
  const [scene, setScene] = useState<SceneId>("resultado");
  const [format, setFormat] = useState<FormatId>("vertical");
  const selected = scenes[scene][locale];

  return (
    <main className="min-h-[calc(100dvh-56px)] bg-[var(--bg)] px-4 pb-16 pt-8 text-[var(--text)] sm:px-7 lg:px-10">
      <div className="mx-auto max-w-[1500px]">
        <header className="mb-8 flex flex-wrap items-start justify-between gap-5 border-b border-[var(--border)] pb-7">
          <div className="max-w-3xl min-w-0">
            <p className="mb-3 font-mono text-[11px] font-bold tracking-[0.22em] text-[var(--accent-strong)]">{c.eyebrow}</p>
            <h1 className="font-display text-3xl font-bold leading-[1.08] tracking-tight [overflow-wrap:anywhere] sm:text-4xl lg:text-5xl">{t("pg_molcy_titulo")}</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-[var(--text-secondary)]">{c.intro}</p>
          </div>
          <span className="border border-[var(--border-light)] px-3 py-2 font-mono text-[10px] uppercase tracking-[0.16em] text-[var(--text-dim)]">{c.draft}</span>
        </header>

        <div className="grid items-start gap-6 xl:grid-cols-[minmax(245px,0.84fr)_minmax(360px,1.55fr)_minmax(250px,0.82fr)]">
          <aside className="space-y-7">
            <section aria-labelledby="molcy-source-title">
              <p className="mb-2 font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">{c.source}</p>
              <h2 id="molcy-source-title" className="font-display text-xl font-bold">{c.sourceTitle}</h2>
              <div className="mt-4 border border-dashed border-[var(--border-light)] bg-[var(--bg-card)] p-5">
                <div className="flex items-center gap-3">
                  <div className="flex size-10 shrink-0 items-center justify-center border border-[var(--border-light)] text-[var(--accent-strong)]"><Aperture size={19} /></div>
                  <p className="text-sm font-semibold">{c.sourceMissing}</p>
                </div>
                <p className="mt-4 text-xs leading-6 text-[var(--text-muted)]">{c.sourceDetail}</p>
              </div>
            </section>

            <section aria-labelledby="molcy-scenes-title">
              <p className="mb-2 font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">{c.scenes}</p>
              <h2 id="molcy-scenes-title" className="font-display text-xl font-bold">{c.scenesTitle}</h2>
              <div className="mt-4 space-y-2" role="group" aria-label={c.scenesTitle}>
                {(Object.keys(scenes) as SceneId[]).map((id) => {
                  const item = scenes[id];
                  const Icon = item.icon;
                  const active = scene === id;
                  return (
                    <button
                      key={id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => setScene(id)}
                      className={`flex w-full cursor-pointer items-start gap-3 border p-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] ${active ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)]" : "border-[var(--border)] bg-[var(--bg-card)] hover:border-[var(--border-light)] active:bg-[var(--bg-secondary)]"}`}
                    >
                      <Icon size={18} className="mt-0.5 shrink-0 text-[var(--accent-strong)]" />
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center justify-between gap-2"><span className="text-sm font-bold">{item[locale].name}</span><span className="font-mono text-[10px] text-[var(--text-dim)]">{item.number}</span></span>
                        <span className="mt-1 block text-xs leading-5 text-[var(--text-muted)]">{item[locale].summary}</span>
                      </span>
                    </button>
                  );
                })}
              </div>
              {scene === "busqueda" && <p className="mt-3 flex gap-2 text-xs leading-5 text-[var(--text-muted)]"><CircleHelp size={15} className="mt-0.5 shrink-0" />{c.searchNote}</p>}
              {scene === "ensamble" && <p className="mt-3 flex gap-2 text-xs leading-5 text-[var(--text-muted)]"><CircleHelp size={15} className="mt-0.5 shrink-0" />{c.ensembleNote}</p>}
            </section>
          </aside>

          <section aria-labelledby="molcy-preview-title" className="min-w-0 border border-[var(--border)] bg-[var(--bg-card)]">
            <div className="flex items-center justify-between gap-3 border-b border-[var(--border)] px-5 py-4">
              <div className="flex items-center gap-2"><MonitorPlay size={16} className="text-[var(--accent-strong)]" /><h2 id="molcy-preview-title" className="font-mono text-xs font-bold tracking-[0.16em]">{c.preview}</h2></div>
              <span className="hidden font-mono text-[10px] text-[var(--text-dim)] sm:block">{c.previewHint}</span>
            </div>
            <div className="flex min-h-[440px] items-center justify-center overflow-hidden bg-[var(--bg-alt)] px-6 py-8">
              <div className={`relative flex max-h-[480px] w-full flex-col overflow-hidden border border-[var(--border-light)] bg-[var(--bg-secondary)] transition-[aspect-ratio] duration-300 ${format === "vertical" ? "aspect-[9/16] max-w-[270px]" : "aspect-video max-w-[470px]"}`}>
                <div className="absolute inset-0 opacity-50" style={{ backgroundImage: "radial-gradient(var(--border-light) 0.7px, transparent 0.7px)", backgroundSize: "22px 22px" }} />
                <div className="relative z-10 flex items-start justify-between p-4 font-mono text-[10px] uppercase tracking-[0.13em] text-[var(--text-muted)]">
                  <span>Molcy / {scenes[scene].number}</span><span>{format === "vertical" ? "9:16" : "16:9"}</span>
                </div>
                <div className="relative z-10 flex flex-1 items-center justify-center p-5">
                  <div className="relative flex size-44 max-w-full items-center justify-center rounded-full border border-[var(--border-light)] sm:size-52">
                    <div className="absolute inset-5 rounded-full border border-dashed border-[var(--border-light)]" />
                    <div className="absolute inset-12 rounded-full border border-[var(--accent)] opacity-70" />
                    <Aperture size={32} strokeWidth={1} className="text-[var(--accent-strong)]" aria-hidden="true" />
                  </div>
                </div>
                <div className="relative z-10 border-t border-[var(--border)] bg-[var(--bg-card)] p-4">
                  <p className="font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--accent-strong)]">{c.playback}</p>
                  <p className="mt-1 text-xs leading-5 text-[var(--text-secondary)]">{c.previewEmpty}</p>
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3 border-t border-[var(--border)] px-5 py-4 text-[var(--text-dim)]">
              <Play size={13} /><span className="h-1 flex-1 bg-[var(--border)]"><span className="block h-1 w-1/3 bg-[var(--accent)]" /></span><Pause size={13} />
            </div>
            <div className="border-t border-[var(--border)] p-5">
              <p className="mb-4 font-mono text-[10px] tracking-[0.18em] text-[var(--text-dim)]">{c.storyboard}</p>
              <ol className="grid gap-2 sm:grid-cols-3">
                {selected.phase.map((phase, index) => <li key={phase} className="min-w-0 border-l-2 border-[var(--accent)] bg-[var(--bg-secondary)] px-3 py-3"><span className="font-mono text-[10px] text-[var(--text-dim)]">0{index + 1}</span><p className="mt-1 text-xs font-semibold leading-5">{phase}</p></li>)}
              </ol>
            </div>
          </section>

          <aside className="space-y-7">
            <section aria-labelledby="molcy-output-title">
              <p className="mb-2 font-mono text-[10px] tracking-[0.18em] text-[var(--accent-strong)]">{c.output}</p>
              <h2 id="molcy-output-title" className="font-display text-xl font-bold">{c.outputTitle}</h2>
              <div className="mt-4 grid grid-cols-2 gap-2" role="group" aria-label={c.outputTitle}>
                {(["vertical", "horizontal"] as FormatId[]).map((id) => <button key={id} type="button" aria-pressed={format === id} onClick={() => setFormat(id)} className={`cursor-pointer border px-3 py-4 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] ${format === id ? "border-[var(--accent-strong)] bg-[var(--bg-secondary)]" : "border-[var(--border)] hover:border-[var(--border-light)] active:bg-[var(--bg-secondary)]"}`}>{id === "vertical" ? <Smartphone size={16} className="mb-3 text-[var(--accent-strong)]" /> : <Monitor size={16} className="mb-3 text-[var(--accent-strong)]" />}<span className="block text-xs font-bold">{c[id]}</span><span className="mt-1 block font-mono text-[10px] text-[var(--text-dim)]">{id === "vertical" ? "9:16" : "16:9"}</span></button>)}
              </div>
              <p className="mt-3 text-xs leading-5 text-[var(--text-muted)]">{c.formatHint}</p>
            </section>
            <section className="border-t border-[var(--border)] pt-6">
              <div className="flex items-center gap-2"><Check size={17} className="text-[var(--categoria-hallazgo)]" /><h2 className="text-sm font-bold">{c.evidence}</h2></div>
              <p className="mt-3 text-xs leading-6 text-[var(--text-muted)]">{c.evidenceText}</p>
            </section>
            <section className="border-t border-[var(--border)] pt-6">
              <button type="button" disabled aria-describedby="molcy-disabled" className="flex w-full cursor-not-allowed items-center justify-between bg-[var(--border)] px-4 py-4 text-sm font-bold text-[var(--text-muted)] opacity-70"><span className="flex items-center gap-2"><WandSparkles size={17} />{c.generate}</span><ArrowRight size={16} /></button>
              <p id="molcy-disabled" className="mt-3 text-xs leading-5 text-[var(--text-dim)]">{c.disabled}</p>
              <p className="mt-5 border-t border-[var(--border)] pt-4 font-mono text-[10px] uppercase tracking-[0.11em] text-[var(--text-dim)]">{c.noBackend}</p>
            </section>
          </aside>
        </div>
      </div>
    </main>
  );
}
