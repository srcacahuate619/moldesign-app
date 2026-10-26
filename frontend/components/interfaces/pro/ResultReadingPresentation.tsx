"use client";
/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4
 * Existing MolDesign tokens · Workbench index retained · no decorative motion */
import { createContext, useContext, type ReactNode } from "react";
import { useLanguage } from "@/context/LanguageContext";
import type { CheckStatus } from "@/lib/evaluationEvidence";
import styles from "./ResultReadingPresentation.module.css";

const ReadingContext = createContext({ enabled: false });
export const useResultReading = () => useContext(ReadingContext);

export function ResultReadingPresentation({ children }: { children: ReactNode }) {
  return <ReadingContext.Provider value={{ enabled: true }}><div className={styles.root} data-reading="balanced">{children}</div></ReadingContext.Provider>;
}

/** Help changes its prominence; the scientific panel stays mounted and keeps its selection. */
export function ReadingHelp({ area }: { area: "overview" | "structure" | "properties" | "advanced" | "provenance" }) {
  const { enabled } = useResultReading();
  const { t } = useLanguage();
  if (!enabled) return null;
  return <aside className={styles.help} aria-label={t("rr_help")}>
    {area !== "overview" && <p className={styles.helpBrief}>{t(`rr_help_${area}_brief`)}</p>}
    <details className={styles.helpDetails}>
      <summary>{t("rr_help")}</summary><p>{t(`rr_help_${area}_detail`)}</p>
    </details>
  </aside>;
}

export interface ReadingReservation { id: string; label: string; detail: string; status: CheckStatus; code?: string }
const NOTICE_KEYS: Record<string, string> = {
  RECEPTOR_PROTONACION_DECLARADA: "rr_notice_protonation",
  CAJA_BUSQUEDA_AMPLIA: "rr_notice_box",
  ESPECIE_ACOPLADA_DISTINTA: "rr_notice_species",
};
const DIMENSION_KEYS: Record<string, string> = {
  sampling: "rr_reservation_sampling", reproducibility: "rr_reservation_trace",
  system: "rr_reservation_system", model: "rr_reservation_model", physicochemical: "rr_reservation_properties",
  selectivity: "rr_reservation_selectivity", physical: "rr_reservation_physical",
};

export function ReadingReservations({ items, legacy, onOpenPhysicalControls }: {
  items: ReadingReservation[]; legacy: ReadingReservation[]; onOpenPhysicalControls?: () => void;
}) {
  const { t } = useLanguage();
  const title = (item: ReadingReservation) => {
    const key = item.code ? NOTICE_KEYS[item.code] : DIMENSION_KEYS[item.id];
    // Unknown producer codes remain literal. No severity or scientific conclusion is inferred from prose.
    return key ? t(key) : `${item.label}${item.code ? ` · ${item.code}` : ""}`;
  };
  return <div className={styles.reservations}>
    <h3>{t("rr_review")}</h3>
    <ul className={styles.reservationList}>{items.map(item => <li key={item.id}>
      <details className={styles.reservation} data-critical={item.status === "missing"}>
        <summary><span className={styles.reservationTitle}>{item.status === "missing" && <span className={styles.critical}>{t("rr_important")} · </span>}{title(item)}</span>{" "}<span className={styles.detailAffordance}>{t("rr_detail")}</span></summary>
        <div className={styles.reservationDetail}><p><strong>{item.label}: </strong>{item.detail}</p>{item.code && <p className={styles.technicalCode}>{item.code}</p>}{item.id === "physical" && onOpenPhysicalControls && <button type="button" onClick={onOpenPhysicalControls} className={styles.secondary}>{t("pn_revisar_controles")}</button>}</div>
      </details>
    </li>)}</ul>
    {legacy.length > 0 && <details className={styles.legacy}>
      <summary>{t(legacy.length === 1 ? "rx_heredados_one" : "rx_heredados_count", { count: legacy.length })}</summary>
      <p>{t("rx_heredados_desc")}</p><ul>{legacy.map(item => <li key={item.id}>{item.detail}</li>)}</ul>
    </details>}
  </div>;
}
