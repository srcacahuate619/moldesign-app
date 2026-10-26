"use client";
/* Hallmark · pre-emit critique: P5 H4 E4 S5 R5 V4 */
import { useId } from "react";
import { useLanguage } from "@/context/LanguageContext";
import type { MolcyPresentacion, MolcyEscena } from "@/lib/molcy";

export const AUTO_PRESENTATION: MolcyPresentacion = { schema: "moldesign.presentacion/1", titulo: null, color_receptor: null, color_residuos: null, colores_lineas: { polar: null, apolar: null }, receptor: "automatico", muestra_anterior: true, etiquetas: true, contactos: true };
export type EnsembleVariant = "referencia" | "lenta" | "detallada";

export function PresentationControls({ value, onChange, scene, disabled, ensembleVariant, onEnsembleVariant }: {
  value: MolcyPresentacion; onChange: (value: MolcyPresentacion) => void; scene: MolcyEscena; disabled: boolean;
  ensembleVariant: EnsembleVariant; onEnsembleVariant: (value: EnsembleVariant) => void;
}) {
  const { t } = useLanguage();
  const uid = useId();
  const update = <K extends keyof MolcyPresentacion>(key: K, next: MolcyPresentacion[K]) => onChange({ ...value, [key]: next });
  const color = (key: string, label: string, current: string | null, next: (value: string | null) => void) => <fieldset key={key} className="min-w-0 space-y-2 border-t border-[var(--border)] py-3">
    <legend className="text-sm font-medium">{label}</legend>
    <div className="flex flex-wrap items-center gap-3"><label htmlFor={`${uid}-${key}`} className="sr-only">{label}</label><input type="color" id={`${uid}-${key}`} value={current ?? "#A78BFA"} disabled={disabled || current === null} onChange={e => next(e.target.value.toUpperCase())} className="h-11 w-14 cursor-pointer rounded border border-[var(--border)] bg-transparent disabled:cursor-default disabled:opacity-40"/>
      <label className="flex min-h-11 items-center gap-2 text-sm"><input type="checkbox" checked={current === null} onChange={e => next(e.target.checked ? null : "#A78BFA")} disabled={disabled}/>{t("cy_pres_automatic")}</label>{current && <span className="font-mono text-sm text-[var(--text-muted)]">{current}</span>}
    </div>
  </fieldset>;
  return <details className="mt-6 border-t border-[var(--border)] pt-3">
    <summary className="min-h-12 cursor-pointer py-3 text-sm font-semibold focus-visible:outline focus-visible:outline-2 focus-visible:outline-[var(--accent-strong)]">{t("cy_pres_customize_presentation")}</summary>
    <p className="mb-4 text-sm leading-6 text-[var(--text-muted)]">{t("cy_pres_visual_changes_are_saved_with_this_job_the_scientifi")}</p>
    <fieldset disabled={disabled} className="min-w-0 space-y-4 disabled:opacity-60">
      <label className="grid gap-2 text-sm">{t("cy_pres_display_title")}<input type="text" maxLength={80} value={value.titulo ?? ""} onChange={e => update("titulo", e.target.value || null)} placeholder={t("cy_pres_automatic_scientific_name")} className="min-h-11 min-w-0 rounded border border-[var(--border)] bg-[var(--bg)] px-3"/></label>
      <label className="grid gap-2 text-sm">{t("cy_pres_receptor")}<select value={value.receptor} onChange={e => update("receptor", e.target.value as MolcyPresentacion["receptor"])} className="min-h-11 min-w-0 rounded border border-[var(--border)] bg-[var(--bg)] px-3"><option value="automatico">{t("cy_pres_automatic_visibility")}</option><option value="visible">{t("cy_pres_show_receptor")}</option><option value="oculto">{t("cy_pres_hide_receptor")}</option></select></label>
      {color("receptor", t("cy_pres_receptor_color"), value.color_receptor, next => update("color_receptor", next))}
      {color("residuos", t("cy_pres_highlighted_residue_color"), value.color_residuos, next => update("color_residuos", next))}
      {color("polar", t("cy_pres_polar_interaction_lines"), value.colores_lineas.polar, next => update("colores_lineas", { ...value.colores_lineas, polar: next }))}
      {color("apolar", t("cy_pres_apolar_interaction_lines"), value.colores_lineas.apolar, next => update("colores_lineas", { ...value.colores_lineas, apolar: next }))}
      {(["etiquetas", "contactos", "muestra_anterior"] as const).map(key => key === "muestra_anterior" && scene !== "busqueda" ? null : <label key={key} className="flex min-h-11 items-center gap-3 text-sm"><input type="checkbox" checked={value[key]} onChange={e => update(key, e.target.checked)}/>{key === "etiquetas" ? t("cy_pres_show_labels") : key === "contactos" ? t("cy_pres_show_contacts") : t("cy_pres_show_previous_sample")}</label>)}
      <button type="button" onClick={() => onChange({ ...AUTO_PRESENTATION, colores_lineas: { ...AUTO_PRESENTATION.colores_lineas } })} className="min-h-11 rounded border border-[var(--border)] px-3 text-sm font-semibold">{t("cy_pres_restore_automatic")}</button>
    </fieldset>
    {scene === "ensamble" && <fieldset disabled={disabled} className="mt-5 border-t border-[var(--border)] pt-4"><legend className="text-sm font-semibold">{t("cy_pres_ensemble_motion_trial")}</legend><div className="mt-2 grid gap-2">{(["lenta", "detallada", "referencia"] as const).map((variant, index) => <label key={variant} className="flex min-h-11 items-center gap-3 text-sm"><input type="radio" name={`${uid}-ensemble`} checked={ensembleVariant === variant} onChange={() => onEnsembleVariant(variant)}/>{index === 0 ? t("cy_pres_1_uniform_continuous_motion") : index === 1 ? t("cy_pres_2_torsion_emphasis") : t("cy_pres_reference_previous_recorded_scene")}</label>)}</div><p className="mt-3 text-sm leading-6 text-[var(--text-muted)]">{t("cy_pres_both_trials_combine_internal_torsions_and_spatial_or")}</p></fieldset>}
  </details>;
}
