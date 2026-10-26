"use client";


import { useLanguage } from "@/context/LanguageContext";
import React, { useId, useState } from "react";
import { Ayuda } from "../../ui/Ayuda";
import { ChevronRight } from "lucide-react";
import { useResultReading } from "./ResultReadingPresentation";
import readingStyles from "./ResultReadingPresentation.module.css";
import styles from "./ResultPanels.module.css";
import type {PoseComparisonRow} from "@/lib/structuralEvidence";

import type { ReferenceResidues } from "../../../lib/types";

interface DockingPose {
  rank: number;
  affinity: number;
  rmsd_lb: number;
  rmsd_ub: number;
  conformer_index?: number;
}

interface Hotspot {
  name: string;
  importance: number;
}

interface Props {
  poses: DockingPose[] | null | undefined;
  hotspots: Hotspot[] | null | undefined;
  hotspots_hit: string[] | null | undefined;
  /**
   * Los residuos que la corrida USÓ, sellados con ella. Sin esto el panel pintaba los del catálogo
   * como si fueran los usados (QA1-007); `null` es una corrida anterior al sellado.
   */
  referenceResidues?: ReferenceResidues | null;
  activePose?: number;
  onSelectPose?: (rank: number) => void;
  poseDetails?: React.ReactNode;
  /** Disclosure is independent of the selected pose. */
  detailsExpanded?: boolean;
  poseSummary?: PoseComparisonRow[];
}

export function ProDockingTab({
  poses,
  hotspots,
  hotspots_hit,
  referenceResidues,
  activePose,
  onSelectPose,
  poseDetails,
  detailsExpanded,
  poseSummary,
}: Props) {
  const { t } = useLanguage();
  const reading = useResultReading();
  const [internalPose, setInternalPose] = useState<number | undefined>(undefined);
  const active = activePose ?? internalPose;
  const detailId = useId();
  const [internalExpanded, setInternalExpanded] = useState(true);
  const expanded = detailsExpanded ?? internalExpanded;
  const hitList = hotspots_hit ?? [];
  const rmsdHelp = (
    <Ayuda
      titulo={t("ux_rmsd")}
      etiqueta={`${t("c_que_significa")}: ${t("ux_rmsd")}`}
    >
      {t("ux_rmsd_help")}
    </Ayuda>
  );

  // Lo que se muestra es el catálogo MÁS lo que la persona eligió fuera de él, y cada residuo dice si se usó.
  // Sin `referenceResidues` (corrida anterior al sellado) no se sabe: se enseña el catálogo y se dice.
  const usados = referenceResidues ? new Set(referenceResidues.residues) : null;
  const catalogo = hotspots ?? [];
  const delCatalogo = new Set(catalogo.map((h) => h.name));
  const extras: Hotspot[] = referenceResidues
    ? referenceResidues.residues.filter((name) => !delCatalogo.has(name)).map((name) => ({ name, importance: 1 }))
    : [];
  const listaDeResiduos = [...catalogo, ...extras];
  const cuantosUsados = referenceResidues ? referenceResidues.count : catalogo.length;
  const estadoDeLosResiduos = !referenceResidues
    ? t("pn_residuos_usados_desconocido")
    : referenceResidues.source === "none"
      ? t("pn_residuos_usados_ninguno")
      : referenceResidues.source === "selected"
        ? t("pn_residuos_usados_elegidos", { n: referenceResidues.count, total: referenceResidues.catalog_count })
        : t("pn_residuos_usados_catalogo", { n: referenceResidues.count });

  const selectPose = (rank: number) => {
    setInternalExpanded(rank !== active || !expanded);
    if (onSelectPose) onSelectPose(rank);
    else setInternalPose(rank);
  };

  return <div className="space-y-6">
    <section aria-labelledby={`${detailId}-poses`}>
      <div className={styles.sectionHeader}><h4 id={`${detailId}-poses`}>{t("ux_pose_list")}</h4><span className={styles.source}>{poses?.length ?? "—"} {t("pr_ev_protocol_pose_many")}</span></div>
      <p className={styles.intro}>{t("ux_pose_intro")}</p>
      {poses?.length?<div className={styles.poseList}>
        <div className={styles.poseColumns}>
          <span>{t("ux_pose_rank")}</span>
          <span>{t("ux_vina_score")} · kcal/mol</span>
          <span className={styles.rmsdHeading}>{t("ux_rmsd")} · Å{rmsdHelp}</span>
          <span>{t("ux_checks")}</span>
          <span />
        </div>
        <div className={styles.poseRmsdMobileHelp}>
          <span>{t("ux_rmsd")} · Å</span>{rmsdHelp}
        </div>
        {poses.map(p=>{
          const isActive=active===p.rank,isExpanded=isActive&&expanded;
          const physical=poseSummary?.find(item=>item.rank===p.rank)?.physicalStatus??"not_evaluated";
          return <React.Fragment key={p.rank}>
            <button type="button" className={styles.poseButton} onClick={()=>selectPose(p.rank)} aria-pressed={isActive}
              aria-expanded={poseDetails?isExpanded:undefined} aria-controls={poseDetails?`${detailId}-pose-${p.rank}`:undefined}
              aria-label={t("z_ver_controles_pose",{rank:p.rank})}>
              <span className={styles.poseNumber}>#{p.rank}</span>
              <span className={styles.poseValue}><span className={styles.cellCaption}>{t("ux_vina_score")}</span>{p.affinity.toFixed(reading.enabled?2:1)} <span className={styles.source}>kcal/mol</span></span>
              <span className={styles.poseValue}><span className={styles.cellCaption}>RMSD</span>{p.rmsd_lb.toFixed(1)} / {p.rmsd_ub.toFixed(1)} <span className={styles.source}>Å</span>
                {typeof p.conformer_index==="number"&&<span className={styles.poseSource}>{t("ux_conformer",{index:p.conformer_index})}</span>}
              </span>
              <span className={styles.poseStatus} data-status={physical}><span className={styles.cellCaption}>{t("ux_checks")}</span>{t(`ux_checks_${physical}`)}</span>
              <ChevronRight className={styles.poseChevron} aria-hidden="true"/>
            </button>
            {poseDetails&&<div id={`${detailId}-pose-${p.rank}`} hidden={!isExpanded} className={styles.poseDetail}>{isActive?poseDetails:null}</div>}
          </React.Fragment>;
        })}
      </div>:<p className={styles.note}>{t("pn_sin_poses_aun")}</p>}

    </section>
    <details className={styles.details} data-site-residues="true">
      <summary>{t("ux_site_residues")} · {reading.enabled?t("ux_site_count",{count:listaDeResiduos.length}):t("pr_docking_pose_counts",{poses:poses?.length??0,hotspots:cuantosUsados})}</summary>
      <div className={styles.detailBody}>
        <p className={styles.intro}>{t("ux_site_help")}</p>
        <p data-testid="residuos-usados" className={styles.note}>{estadoDeLosResiduos}</p>
        {listaDeResiduos.length?<div className={styles.residueList}>{listaDeResiduos.map(h=>{
          const usado=!usados||usados.has(h.name),isHit=usado&&hitList.includes(h.name);
          return <div key={h.name} className={styles.residue} data-contact={isHit} data-usado={usado?"si":"no"} data-reading-residue="true">
            <code>{h.name}</code><span>{usado?t(isHit?"pn_residuo_contactado":Array.isArray(hotspots_hit)?"pn_residuo_sin_contacto":"pn_residuo_contacto_no_registrado"):t("pn_residuo_no_usado")}</span>
            <span className={styles.residueImportance} data-residue-importance="true">{t("ux_importance")}: {h.importance.toFixed(1)}</span>
          </div>;
        })}</div>:<p className={styles.note}>{t("pn_sin_hotspots")}</p>}
      </div>
    </details>
  </div>;
}
