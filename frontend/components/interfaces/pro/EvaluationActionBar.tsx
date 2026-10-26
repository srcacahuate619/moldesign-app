"use client";
/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4 · existing MolDesign tokens */
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Download, Eye, FileText, Save, Check, ShieldCheck } from "lucide-react";
import { useLanguage } from "@/context/LanguageContext";
import { useKeepAliveActive } from "@/context/KeepAliveContext";
import styles from "./EvaluationActionBar.module.css";

export const EVALUATION_ACTIONS_OUTLET = "evaluation-actions-outlet";

/** The workspace outlet reserves real space. Standalone previews use a fixed bar plus an equal spacer. */
export function EvaluationActionBar({ onDownloadReport, onViewReport, onDownloadComplex, onSave, isSaved = false, unavailableReason, integrityAction }: {
  onDownloadReport?: () => void | Promise<void>;
  onViewReport?: () => void;
  onDownloadComplex?: () => void | Promise<void>;
  onSave?: () => void | Promise<void>;
  isSaved?: boolean;
  unavailableReason?: string;
  integrityAction?: { onClick: () => void; disabled: boolean; label: string; title: string; state: string };
}) {
  const { t } = useLanguage();
  const active = useKeepAliveActive();
  const [target, setTarget] = useState<HTMLElement | null>(null);
  const barRef = useRef<HTMLElement | null>(null);
  useEffect(() => {
    if (!active) { setTarget(null); return; }
    const outlet = document.getElementById(EVALUATION_ACTIONS_OUTLET);
    // A keep-alive workspace can exist while hidden on another route.
    setTarget(outlet && outlet.getClientRects().length > 0 ? outlet : document.body);
  }, [active]);
  useEffect(() => {
    const bar = barRef.current;
    if (!active || !target || !bar) return;
    const property = "--evaluation-actions-height";
    const previous = document.body.style.getPropertyValue(property);
    const update = () => {
      const height = bar.getBoundingClientRect().height;
      if (height > 0) document.body.style.setProperty(property, `${height}px`);
    };
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(update);
    update(); observer?.observe(bar);
    return () => {
      observer?.disconnect();
      if (previous) document.body.style.setProperty(property, previous);
      else document.body.style.removeProperty(property);
    };
  }, [active, target]);
  if (!active || !target) return null;
  const standalone = target === document.body;
  const actions: { key: string; label: string; short: string; icon: typeof FileText; action?: () => void | Promise<void>; disabled?: boolean; title?: string }[] = [
    { key: "report", label: t("ev_descargar_informe"), short: t("rr_action_download_short"), icon: FileText, action: onDownloadReport },
    { key: "preview", label: t("ev_vista_previa_informe"), short: t("rr_action_view_short"), icon: Eye, action: onViewReport },
    { key: "complex", label: t("ev_descargar_complejo_pdb"), short: t("ev_descargar_complejo_pdb"), icon: Download, action: onDownloadComplex },
    { key: "save", label: isSaved ? t("auto_6edd056bba4f") : t("ev_guardar_en_moldex"), short: isSaved ? t("rr_action_saved_short") : t("rr_action_save_short"), icon: isSaved ? Check : Save, action: onSave },
    { key: "integrity", label: integrityAction?.label ?? t("ev_registrar_integridad_solana"), short: integrityAction?.label ?? t("ev_registrar_integridad_solana"), icon: ShieldCheck, action: integrityAction?.onClick, disabled: integrityAction?.disabled, title: integrityAction?.title },
  ];
  return <>
    {standalone && <div className={styles.spacer} aria-hidden="true"/>}
    {createPortal(<nav ref={barRef} data-evaluation-actions="true" aria-label={t("rr_actions_title")} className={`${styles.bar} ${standalone ? styles.fixed : ""}`}>
      <div className={styles.inner}>{actions.map(({key,label,short,icon:Icon,action,disabled,title}) => <button key={key} type="button" aria-label={label} disabled={!action || disabled}
        aria-haspopup={key === "integrity" && action ? "dialog" : undefined}
        title={title ?? (!action ? unavailableReason : label)} onClick={() => { void action?.(); }} className={styles.action} data-action={key} data-saved={key === "save" && isSaved} data-integrity-state={key === "integrity" ? integrityAction?.state : undefined}>
        <Icon size={17} className={styles.icon} aria-hidden="true"/>
        <span className={styles.fullLabel}>{label.replace(/^✓\s*/, "")}</span><span className={styles.shortLabel}>{short}</span>
      </button>)}</div>
    </nav>,target)}
  </>;
}
