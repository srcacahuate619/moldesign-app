"use client";

import { useId, type ReactNode } from "react";
import { useResultReading } from "./ResultReadingPresentation";
import readingStyles from "./ResultReadingPresentation.module.css";
import { useLanguage } from "@/context/LanguageContext";

export interface ResultArea { id: string; label: string; description: string; badge?: number }

/** A single, stable side index keeps navigation predictable across the result. */
export function ResultAreaLayout({ areas, active, onSelect, children }: {
  areas: readonly ResultArea[]; active: string; onSelect: (id: string) => void; children: ReactNode;
}) {
  const uid = useId();
  const reading = useResultReading();
  const { t } = useLanguage();
  const selected = areas.find(area => area.id === active)!;
  const navigate = (event: React.KeyboardEvent, index: number) => {
    const next = event.key === "ArrowRight" || event.key === "ArrowDown" ? (index + 1) % areas.length
      : event.key === "ArrowLeft" || event.key === "ArrowUp" ? (index - 1 + areas.length) % areas.length
      : event.key === "Home" ? 0 : event.key === "End" ? areas.length - 1 : -1;
    if (next < 0) return;
    event.preventDefault();
    onSelect(areas[next].id);
    document.getElementById(uid + "-" + areas[next].id)?.focus();
  };
  const navigation = (
    <div role="tablist" aria-label={t("rx_areas")} aria-orientation="vertical" className="flex flex-col gap-1">
      {areas.map((area, index) => {
        const activeArea = active === area.id;
        const badgeId = uid + "-" + area.id + "-badge";
        const descriptionId = uid + "-" + area.id + "-description";
        return <button key={area.id} type="button" role="tab" id={uid + "-" + area.id}
          aria-selected={activeArea} aria-controls={uid + "-panel"} tabIndex={activeArea ? 0 : -1}
          aria-label={area.label}
          aria-describedby={[area.badge ? badgeId : null, activeArea ? descriptionId : null].filter(Boolean).join(" ") || undefined}
          onKeyDown={event => navigate(event, index)} onClick={() => onSelect(area.id)}
          className={["min-h-12 min-w-0 rounded-lg px-4 py-3 text-left transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-400", activeArea ? "bg-brand-500/10 text-brand-300" : "text-zinc-300 hover:bg-white/5"].join(" ")}>
          <span className="flex items-baseline justify-between gap-2 text-sm font-semibold"><span>{area.label}</span>{area.badge ? <span id={badgeId} aria-label={t("rx_avisos", { count: area.badge })} className="shrink-0 whitespace-nowrap font-sans text-xs text-amber-300">{t("ux_alerts_count", {count:area.badge})}</span> : null}</span>
          {activeArea && <span id={descriptionId} className="mt-1 block text-sm leading-5 text-zinc-400">{area.description}</span>}
        </button>;
      })}
    </div>
  );
  return <div className="grid min-w-0 gap-7 lg:grid-cols-[15rem_minmax(0,1fr)]">
    <div data-result-index="true" className={readingStyles.areaIndex + " min-w-0 self-start lg:border-r lg:border-white/10 lg:pr-5"}>
      <div className={readingStyles.desktopArea}>{navigation}</div>
      <label className={readingStyles.mobileArea} htmlFor={uid + "-area-select"}>{t("ux_choose_area")}
        <select id={uid + "-area-select"} aria-label={t("ux_choose_area")} value={active} onChange={event=>onSelect(event.target.value)}>{areas.map(area=><option value={area.id} key={area.id}>{area.label}{area.badge ? " · " + t("ux_alerts_count", {count:area.badge}) : ""}</option>)}</select>
      </label>
    </div>
    <div key="persistent-panel" id={uid + "-panel"} role="tabpanel" aria-labelledby={uid + "-" + active} tabIndex={0} className="min-w-0 space-y-5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-brand-400">
      <header className={reading.enabled ? readingStyles.areaHeader : undefined}><h3 className="font-display text-xl font-semibold text-zinc-100">{selected.label}</h3>{!reading.enabled && <p className="mt-1 text-sm leading-6 text-zinc-400">{selected.description}</p>}</header>
      {children}
    </div>
  </div>;
}